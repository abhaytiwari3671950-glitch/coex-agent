import base64
from django.http import JsonResponse, HttpResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET, require_POST
from .models import Memory, UserPreferences, Feedback, Message
from .views import api, data
from .memory import enabled

@require_GET
@api
def memories(request):
    return JsonResponse({'enabled':enabled(request.user),'memories':list(Memory.objects.filter(owner=request.user).values('id','key','value'))})

@require_POST
@api
def update_memory(request):
    try:
        body=data(request)
        if 'enabled' in body:
            if type(body['enabled'])is not bool:raise ValueError('Invalid memory setting.')
            UserPreferences.objects.update_or_create(owner=request.user,defaults={'memory_enabled':body['enabled']})
        elif body.get('action')=='clear':Memory.objects.filter(owner=request.user).delete()
        else:
            row=get_object_or_404(Memory,id=body.get('id'),owner=request.user)
            if body.get('action')=='delete':row.delete()
            else:
                value=body.get('value')
                if not isinstance(value,str) or not value.strip() or len(value)>500:raise ValueError('Memory must be 1-500 characters.')
                row.value=value.strip();row.save()
        return JsonResponse({'ok':True})
    except (ValueError,TypeError):return JsonResponse({'error':'Invalid memory update.'},status=400)

@require_POST
@api
def feedback(request,message_id):
    message=get_object_or_404(Message,id=message_id,conversation__owner=request.user,role='assistant')
    try:
        rating=data(request).get('rating')
        if type(rating)is not int or rating not in (-1,1):raise ValueError()
    except (ValueError,TypeError):return JsonResponse({'error':'Choose thumbs up or thumbs down.'},status=400)
    Feedback.objects.update_or_create(owner=request.user,message=message,defaults={'rating':rating})
    return JsonResponse({'ok':True})

@require_GET
@api
def generated_image(request,message_id):
    message=get_object_or_404(Message,id=message_id,conversation__owner=request.user)
    if message.metadata.get('kind')!='image':return HttpResponse(status=404)
    response=HttpResponse(base64.b64decode(message.metadata['data']),content_type='image/jpeg')
    response['Content-Disposition']='inline; filename="coex-generated.jpg"'
    return response

@require_GET
@api
def search_widget(request,message_id):
    message=get_object_or_404(Message,id=message_id,conversation__owner=request.user)
    return HttpResponse(message.metadata.get('search_suggestions',''),content_type='text/html')
