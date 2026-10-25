import uuid
from django.conf import settings
from django.db import models
class Conversation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    title = models.CharField(max_length=80)
    updated_at = models.DateTimeField(auto_now=True)
    busy_until = models.DateTimeField(null=True)
    turn_token = models.UUIDField(null=True)
class Message(models.Model):
    conversation = models.ForeignKey(Conversation,on_delete=models.CASCADE,related_name='messages')
    role = models.CharField(max_length=12)
    text = models.TextField()
    attachment = models.JSONField(null=True)
    status = models.CharField(max_length=16,default='complete')
    class Meta:
        ordering = ['id']
class Quota(models.Model):
    key = models.CharField(max_length=180,primary_key=True)
    count = models.PositiveIntegerField(default=0)
    expires_at = models.DateTimeField()
