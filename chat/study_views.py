import uuid
from datetime import timedelta
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST
from django.db.models import Q
from .models import StudyRun
from .views import api, data, quota
from .media import process
from .study import advance


def snapshot(run):
    return {'id':str(run.id),'goal':run.goal,'filename':run.filename,'status':run.status,
            'plan':run.state.get('plan',[]),'trace':run.trace,'output':run.output,'artifact':run.artifact}

@login_required
def page(request):
    return render(request,'study.html')

@require_GET
@api
def history(request):
    return JsonResponse({'runs':list(StudyRun.objects.filter(owner=request.user).order_by('-created_at').values('id','goal','status')[:30])})

@require_GET
@api
def detail(request,run_id):
    return JsonResponse(snapshot(get_object_or_404(StudyRun,id=run_id,owner=request.user)))

@require_POST
@api
def create(request):
    try:
        body=data(request); goal=body.get('goal'); attachment=body.get('attachment')
        if not isinstance(goal,str) or not goal.strip() or len(goal)>2000: raise ValueError('Enter a goal up to 2,000 characters.')
        if not isinstance(attachment,dict) or attachment.get('mediaType')!='application/pdf': raise ValueError('Upload a PDF for this study goal.')
        document=process({'action':'inspect','data':attachment.get('data'),'mediaType':'application/pdf'})
    except (ValueError,TypeError) as exc:
        return JsonResponse({'error':str(exc)},status=400)
    if not settings.GOOGLE_GENERATIVE_AI_API_KEY:
        return JsonResponse({'error':'Add the Gemini API key before starting the Study Agent.'},status=503)
    if not quota(f'study-runs:{request.user.pk}',5,86400):
        return JsonResponse({'error':'Daily limit of five study runs reached.'},status=429)
    run=StudyRun.objects.create(owner=request.user,goal=goal.strip(),filename=str(attachment.get('name','source.pdf'))[:160],source=document['text'])
    return JsonResponse(snapshot(run),status=201)

@require_POST
@api
def step(request,run_id):
    run=get_object_or_404(StudyRun,id=run_id,owner=request.user)
    if run.status!='running': return JsonResponse(snapshot(run))
    token=uuid.uuid4(); now=timezone.now()
    acquired=StudyRun.objects.filter(id=run.id,status='running').filter(Q(busy_until__isnull=True)|Q(busy_until__lt=now)).update(token=token,busy_until=now+timedelta(seconds=120))
    if not acquired: return JsonResponse({'error':'A step is already running. Wait before retrying.'},status=409)
    # Refresh after acquiring lease so a stale caller cannot overwrite completed steps.
    run.refresh_from_db()
    try:
        # One step may use two model calls (action plus optional review).
        if not quota(f'study-steps:{request.user.pk}',60,86400) or not quota('study-site',250,86400):
            run.status='limit'; run.trace.append({'action':'limit','summary':'Daily agent budget reached. Try tomorrow.'})
        else:
            advance(run)
    except Exception:
        run.status='failed'
        run.trace.append({'action':'error','summary':'The model or tool could not complete this step. Start a new run or check your API configuration.'})
    saved=StudyRun.objects.filter(id=run.id,token=token).update(status=run.status,state=run.state,trace=run.trace,output=run.output,artifact=run.artifact,token=None,busy_until=None)
    if not saved: return JsonResponse({'error':'Step lease expired. Reload the run.'},status=409)
    return JsonResponse(snapshot(run))
