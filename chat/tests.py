import base64
import io
import json
from unittest.mock import patch
from django.contrib.auth.models import User
from django.test import TestCase, Client, override_settings
from django.utils import timezone
from reportlab.pdfgen.canvas import Canvas
from PIL import Image
from .models import Conversation, Message

@override_settings(GOOGLE_GENERATIVE_AI_API_KEY='test-key-not-real',STORAGES={'default':{'BACKEND':'django.core.files.storage.FileSystemStorage'},'staticfiles':{'BACKEND':'django.contrib.staticfiles.storage.StaticFilesStorage'}},PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class FlowTests(TestCase):
    def setUp(self):
        self.alice=User.objects.create_user('alice',password='test-password')
        self.bob=User.objects.create_user('bob',password='test-password')
        self.client.force_login(self.alice)
    def post(self,path,body):
        return self.client.post(path,json.dumps(body),content_type='application/json')
    def consume(self,response):
        self.assertEqual(response.status_code,200)
        return [json.loads(line) for line in b''.join(response.streaming_content).splitlines()]
    def pdf(self):
        stream=io.BytesIO();canvas=Canvas(stream);canvas.drawString(30,800,'The launch code is ORBIT-42.');canvas.save()
        return {'name':'test.pdf','mediaType':'application/pdf','data':base64.b64encode(stream.getvalue()).decode()}
    def test_signup_login_logout_real_forms(self):
        self.client.logout()
        signup=self.client.post('/signup/',{'username':'charlie','password1':'Copper-River-923!','password2':'Copper-River-923!'})
        self.assertEqual(signup.status_code,302)
        self.assertTrue(User.objects.get(username='charlie').check_password('Copper-River-923!'))
        self.assertEqual(self.client.get('/').status_code,200)
        self.assertEqual(self.client.get('/logout/').status_code,405)
        self.client.post('/logout/')
        self.assertEqual(self.client.get('/api/conversations').status_code,401)
        self.assertEqual(self.client.post('/login/',{'username':'charlie','password':'Copper-River-923!'}).status_code,302)
    def test_csrf_enforced(self):
        client=Client(enforce_csrf_checks=True);client.force_login(self.alice)
        self.assertEqual(client.post('/api/chat','{"text":"hello"}',content_type='application/json').status_code,403)
        self.assertEqual(client.get('/').status_code,200)
        token=client.cookies['csrftoken'].value
        self.assertEqual(client.post('/api/media','{"action":"inspect","data":""}',content_type='application/json',HTTP_X_CSRFTOKEN=token).status_code,400)
    @patch('chat.views.stream_reply',return_value=iter(['Hello ','Abhay']))
    def test_stream_and_saved_history(self,model):
        events=self.consume(self.post('/api/chat',{'text':'Hello'}))
        self.assertTrue(events[-1]['done'])
        item=Conversation.objects.get()
        self.assertEqual(item.owner,self.alice)
        self.assertEqual(list(item.messages.values_list('text',flat=True)),['Hello','Hello Abhay'])
        self.assertIsNone(item.busy_until)
        self.assertEqual(self.client.get(f'/api/conversations/{item.id}').json()['messages'][1]['text'],'Hello Abhay')
    @patch('chat.views.stream_reply')
    def test_owner_isolation(self,model):
        item=Conversation.objects.create(owner=self.bob,title='private')
        Message.objects.create(conversation=item,role='user',text='private data')
        self.assertEqual(self.client.get(f'/api/conversations/{item.id}').status_code,404)
        self.assertEqual(self.post('/api/chat',{'text':'read it','conversationId':str(item.id)}).status_code,404)
        self.assertEqual(self.client.get('/api/conversations').json()['conversations'],[])
        model.assert_not_called()
    def test_pdf_inspection_and_export(self):
        self.assertIn('ORBIT-42',self.post('/api/media',{'action':'inspect',**self.pdf()}).json()['text'])
        exported=self.post('/api/media',{'action':'create_pdf','text':'Roundtrip check','title':'Test'}).json()
        self.assertIn('Roundtrip check',self.post('/api/media',{'action':'inspect',**exported}).json()['text'])
    @patch('chat.views.stream_reply',return_value=iter(['ORBIT-42']))
    def test_pdf_to_model(self,model):
        self.consume(self.post('/api/chat',{'text':'What code?','attachment':self.pdf()}))
        self.assertEqual(model.call_args.args[0][0]['attachment']['mediaType'],'application/pdf')
    def test_image_and_invalid_file(self):
        stream=io.BytesIO();Image.new('RGB',(100,80),'blue').save(stream,format='PNG')
        body={'action':'inspect','mediaType':'image/png','data':base64.b64encode(stream.getvalue()).decode()}
        self.assertEqual(self.post('/api/media',body).json()['width'],100)
        body['data']='invalid!';self.assertEqual(self.post('/api/media',body).status_code,400)
    @override_settings(DAILY_USER_MESSAGES=0)
    @patch('chat.views.stream_reply')
    def test_quota(self,model):
        self.assertEqual(self.post('/api/chat',{'text':'hello'}).status_code,429)
        model.assert_not_called()
    @override_settings(GOOGLE_GENERATIVE_AI_API_KEY='')
    def test_missing_key(self):
        self.assertEqual(self.post('/api/chat',{'text':'hello'}).status_code,503)
    @patch('chat.views.stream_reply',side_effect=RuntimeError('secret provider details'))
    def test_failure_sanitized_and_unlocks(self,model):
        events=self.consume(self.post('/api/chat',{'text':'hello'}))
        self.assertNotIn('secret provider details',str(events))
        self.assertIn('error',events[-1]);item=Conversation.objects.get()
        self.assertIsNone(item.busy_until);self.assertEqual(item.messages.last().status,'failed')
    def test_anonymous_rejected(self):
        self.client.logout()
        self.assertEqual(self.post('/api/media',{'action':'create_pdf','text':'hello'}).status_code,401)
        self.assertEqual(self.post('/api/chat',{'text':'hello'}).status_code,401)
    @patch('chat.views.stream_reply')
    def test_parallel_turn_rejected(self,model):
        from datetime import timedelta
        item=Conversation.objects.create(owner=self.alice,title='Busy',busy_until=timezone.now()+timedelta(minutes=1))
        self.assertEqual(self.post('/api/chat',{'text':'hello','conversationId':str(item.id)}).status_code,409)
        model.assert_not_called()
    @patch('chat.views.stream_reply',side_effect=[iter(['First']),iter(['Second'])])
    def test_resend_preserves_context(self,model):
        self.consume(self.post('/api/chat',{'text':'Original question'}));item=Conversation.objects.get()
        self.consume(self.post('/api/chat',{'text':'Edited question','conversationId':str(item.id)}))
        self.assertEqual(list(item.messages.values_list('text',flat=True)),['Original question','First','Edited question','Second'])
        self.assertEqual(len(model.call_args.args[0]),3)
