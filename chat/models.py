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
    metadata = models.JSONField(default=dict)
    class Meta:
        ordering = ['id']
class Quota(models.Model):
    key = models.CharField(max_length=180,primary_key=True)
    count = models.PositiveIntegerField(default=0)
    expires_at = models.DateTimeField()

class StudyRun(models.Model):
    conversation = models.ForeignKey(Conversation,on_delete=models.SET_NULL,null=True)
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    goal = models.TextField()
    filename = models.CharField(max_length=160)
    source = models.TextField()
    status = models.CharField(max_length=20, default='running')
    state = models.JSONField(default=dict)
    trace = models.JSONField(default=list)
    output = models.TextField(default='')
    artifact = models.JSONField(null=True)
    busy_until = models.DateTimeField(null=True)
    token = models.UUIDField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)

class UserPreferences(models.Model):
    owner = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    memory_enabled = models.BooleanField(default=True)

class Memory(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    key = models.CharField(max_length=120)
    value = models.CharField(max_length=500)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['owner','key'],name='unique_user_memory')]

class Feedback(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    message = models.ForeignKey(Message,on_delete=models.CASCADE)
    rating = models.SmallIntegerField()
    class Meta:
        constraints = [models.UniqueConstraint(fields=['owner','message'],name='unique_user_feedback')]

class QuizSession(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    id = models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE)
    run = models.ForeignKey(StudyRun,on_delete=models.CASCADE)
    questions = models.JSONField(default=list)
    answers = models.JSONField(default=list)
    busy_until = models.DateTimeField(null=True)
    token = models.UUIDField(null=True)
