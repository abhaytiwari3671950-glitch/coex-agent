import hashlib
import json
import time
import uuid
from datetime import timedelta
from functools import wraps
from django.conf import settings
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.db import transaction
from django.db.models import F
from django.http import JsonResponse, StreamingHttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST, require_GET
from .models import Conversation, Message, Quota
from .provider import stream_reply
from .media import process


def quota(key, limit, seconds):
    now = timezone.now()
    bucket = int(time.time()) // seconds
    name = f'{key}:{bucket}'
    Quota.objects.get_or_create(key=name,defaults={'expires_at':now+timedelta(seconds=seconds*2)})
    return bool(Quota.objects.filter(key=name,count__lt=limit).update(count=F('count')+1))


def api(view):
    @wraps(view)
    def wrapped(request,*args,**kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'error':'Please sign in again.'},status=401)
        return view(request,*args,**kwargs)
    return wrapped


def data(request):
    value = json.loads(request.body)
    if not isinstance(value,dict):
        raise ValueError('Expected a JSON object.')
    return value


def auth_budget(request):
    # Use the server's trusted peer address, never a client-supplied forwarded header.
    peer = hashlib.sha256(request.META.get('REMOTE_ADDR','unknown').encode()).hexdigest()
    username = hashlib.sha256(request.POST.get('username','').casefold().encode()).hexdigest()
    return quota(f'login-ip:{peer}',30,300) and quota(f'login-user:{username}',10,300)


def sign_in(request):
    form = AuthenticationForm(request,data=request.POST if request.method=='POST' else None)
    if request.method=='POST':
        if not auth_budget(request):
            return render(request,'auth.html',{'form':form,'error':'Too many attempts. Try again in five minutes.'},status=429)
        if form.is_valid():
            login(request,form.get_user())
            return redirect('/')
    return render(request,'auth.html',{'form':form})


def sign_up(request):
    form = UserCreationForm(request.POST if request.method=='POST' else None)
    if request.method=='POST':
        if not auth_budget(request) or not quota('signup-site',100,86400):
            return render(request,'auth.html',{'form':form,'signup':True,'error':'Registration limit reached. Please try later.'},status=429)
        if form.is_valid():
            login(request,form.save())
            return redirect('/')
    return render(request,'auth.html',{'form':form,'signup':True})


@require_POST
def sign_out(request):
    logout(request)
    return redirect('/login/')


@login_required
def home(request):
    return render(request,'chat.html')


@require_GET
@api
def conversations(request):
    rows = Conversation.objects.filter(owner=request.user).order_by('-updated_at').values('id','title')[:100]
    return JsonResponse({'conversations':list(rows)})


@require_GET
@api
def conversation(request,conversation_id):
    item = get_object_or_404(Conversation,id=conversation_id,owner=request.user)
    return JsonResponse({'id':item.id,'messages':list(item.messages.values('id','role','text','attachment','status'))})


@require_POST
@api
def media(request):
    if not quota(f'media:{request.user.pk}',20,60):
        return JsonResponse({'error':'Too many file requests. Wait a minute.'},status=429)
    try:
        return JsonResponse(process(data(request)))
    except (ValueError,TypeError) as exc:
        return JsonResponse({'error':str(exc)},status=400)
    except Exception:
        return JsonResponse({'error':'File processing failed. Please try again.'},status=500)


@require_POST
@api
def chat(request):
    if not settings.GOOGLE_GENERATIVE_AI_API_KEY:
        return JsonResponse({'error':'Chat is not configured. The administrator must add the model API key.'},status=503)
    try:
        body = data(request)
        text = body.get('text','')
        if not isinstance(text,str) or not text.strip() or len(text)>12000:
            raise ValueError('Enter a message between 1 and 12,000 characters.')
        attachment = body.get('attachment')
        if attachment is not None:
            if not isinstance(attachment,dict):
                raise ValueError('Invalid attachment.')
            inspected = process({'action':'inspect',**{k:attachment.get(k) for k in ('data','mediaType')}})
            attachment = {'data':attachment['data'],'mediaType':inspected['mediaType'],'name':str(attachment.get('name','attachment'))[:160]}
        conversation_id = uuid.UUID(body['conversationId']) if body.get('conversationId') else None
    except (ValueError,TypeError,KeyError,AttributeError) as exc:
        return JsonResponse({'error':str(exc)},status=400)
    if conversation_id and not Conversation.objects.filter(id=conversation_id,owner=request.user).exists():
        return JsonResponse({'error':'Conversation not found.'},status=404)
    if not quota(f'chat:{request.user.pk}',settings.DAILY_USER_MESSAGES,86400) or not quota('chat-site',settings.DAILY_SITE_MESSAGES,86400):
        return JsonResponse({'error':'Daily chat limit reached. Please try tomorrow.'},status=429)
    token = uuid.uuid4()
    with transaction.atomic():
        item = Conversation.objects.select_for_update().get(id=conversation_id,owner=request.user) if conversation_id else Conversation.objects.create(owner=request.user,title=text[:80])
        if item.busy_until and item.busy_until>timezone.now():
            return JsonResponse({'error':'This conversation is still responding. Please wait.'},status=409)
        if item.messages.count()>=100:
            return JsonResponse({'error':'Start a new chat to keep this conversation manageable.'},status=400)
        item.turn_token = token
        item.busy_until = timezone.now()+timedelta(minutes=3)
        item.save()
        Message.objects.create(conversation=item,role='user',text=text,attachment=attachment)
    # Bound provider history size as well as message count.
    history, size = [], 0
    for message in item.messages.order_by('-id')[:20]:
        entry={'role':message.role,'text':message.text,'attachment':message.attachment}
        size += len(json.dumps(entry))
        if size>4_000_000 and history:
            break
        history.insert(0,entry)
    def events():
        reply = ''
        status = 'interrupted'
        try:
            yield json.dumps({'conversationId':str(item.id)})+'\n'
            for chunk in stream_reply(history):
                reply += chunk
                yield json.dumps({'delta':chunk})+'\n'
            if not reply:
                raise ValueError('Empty model response')
            status = 'complete'
        except GeneratorExit:
            raise
        except Exception:
            status = 'failed'
            yield json.dumps({'error':'The model could not complete this response. Please try again.'})+'\n'
        finally:
            with transaction.atomic():
                current=Conversation.objects.select_for_update().get(id=item.id)
                if current.turn_token==token:
                    Message.objects.create(conversation=current,role='assistant',text=reply,status=status)
                    current.busy_until=None
                    current.turn_token=None
                    current.save()
        if status=='complete':
            yield json.dumps({'done':True})+'\n'
    response=StreamingHttpResponse(events(),content_type='application/x-ndjson')
    response['X-Accel-Buffering']='no'
    return response
