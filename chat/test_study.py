import base64
import io
import json
from unittest.mock import patch
from django.contrib.auth.models import User
from django.test import TestCase, Client, override_settings
from django.utils import timezone
from datetime import timedelta
from reportlab.pdfgen.canvas import Canvas
from .models import StudyRun
from .study import advance, MAX_STEPS

SOURCE='Photosynthesis converts light energy into chemical energy in plants.'
def action(name,args=None): return {'action':name,'summary':'Perform '+name,'args':args or {}}
def draft(quote=SOURCE): return {'title':'Plant study','schedule':['Day 1: Review photosynthesis'], 'notes':[{'topic':'Photosynthesis','text':SOURCE,'chunk':1,'quote':quote}], 'quiz':[{'question':'What does photosynthesis convert?','answer':'Light energy into chemical energy.','chunk':1,'quote':quote}]}

@override_settings(GOOGLE_GENERATIVE_AI_API_KEY='mock-key', PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],STORAGES={'default':{'BACKEND':'django.core.files.storage.FileSystemStorage'},'staticfiles':{'BACKEND':'django.contrib.staticfiles.storage.StaticFilesStorage'}})
class StudyTests(TestCase):
    def setUp(self):
        self.user=User.objects.create_user('student',password='password')
        self.client.force_login(self.user)
        self.run=StudyRun.objects.create(owner=self.user,goal='One-day study pack about photosynthesis',filename='plants.pdf',source=SOURCE)
    def post(self,path,body=None): return self.client.post(path,json.dumps(body or {}),content_type='application/json')
    def tick(self): return self.post(f'/api/study/{self.run.id}/step')
    @patch('chat.study.ask')
    def test_goal_to_verified_pdf(self,ask):
        ask.side_effect=[action('plan',{'steps':['Read','Draft','Check']}),action('read',{'chunks':[1]}),action('draft',draft()),action('verify'),{'passed':True,'issues':[]},action('export')]
        for _ in range(5): self.assertEqual(self.tick().status_code,200)
        self.run.refresh_from_db();self.assertEqual(self.run.status,'complete')
        self.assertIn('[Chunk 1]',self.run.output)
        self.assertTrue(base64.b64decode(self.run.artifact['data']).startswith(b'%PDF'))
        self.assertEqual(len(self.run.trace),5)
        self.assertEqual(ask.call_count,6)
    @patch('chat.study.ask')
    def test_failed_verification_revises_then_passes(self,ask):
        self.run.state={'plan':['Read','Draft','Check'],'seen':[1],'evidence':{'1':SOURCE},'draft':draft()}
        ask.side_effect=[action('verify'),{'passed':False,'issues':['Revise the answer.']},action('export'),action('draft',draft()),action('verify'),{'passed':True,'issues':[]},action('export')]
        for _ in range(5): advance(self.run)
        self.assertEqual(self.run.status,'complete');self.assertIn('error',self.run.trace[1]['result'])
    @patch('chat.study.ask')
    def test_fabricated_quote_rejected(self,ask):
        self.run.state={'plan':['Read','Draft','Check'],'seen':[1]}
        ask.return_value=action('draft',draft('Plants are powered by petrol.'))
        advance(self.run);self.assertIn('not found',self.run.trace[-1]['result']['error']);self.assertNotIn('draft',self.run.state)
    @patch('chat.study.ask')
    def test_blank_source_requests_input_without_model(self,ask):
        self.run.source=' ';advance(self.run);self.assertEqual(self.run.status,'needs_input');ask.assert_not_called()
    @patch('chat.study.ask')
    def test_missing_topic_clarification(self,ask):
        ask.return_value=action('clarify',{'question':'Upload notes about respiration.'});advance(self.run)
        self.assertEqual(self.run.status,'needs_input')
    @patch('chat.study.ask')
    def test_unknown_tool_is_not_executed(self,ask):
        self.run.state={'plan':['Read','Draft','Check']};ask.return_value=action('shell',{'cmd':'echo bad'})
        advance(self.run);self.assertIn('Unknown tool',self.run.trace[-1]['result']['error'])
    @patch('chat.study.ask')
    def test_step_budget(self,ask):
        self.run.state={'steps':MAX_STEPS};advance(self.run);self.assertEqual(self.run.status,'limit');ask.assert_not_called()
    def test_owner_isolation(self):
        other=User.objects.create_user('other');self.client.force_login(other)
        self.assertEqual(self.tick().status_code,404)
        self.assertEqual(self.client.get(f'/api/study/{self.run.id}').status_code,404)
        self.assertEqual(self.client.get('/api/study/history').json()['runs'],[])
    def test_auth_and_csrf(self):
        client=Client(enforce_csrf_checks=True);client.force_login(self.user)
        self.assertEqual(client.post('/api/study',{},content_type='application/json').status_code,403)
        self.client.logout();self.assertEqual(self.tick().status_code,401)
    @patch('chat.study.ask')
    def test_parallel_step_lease(self,ask):
        self.run.busy_until=timezone.now()+timedelta(seconds=60);self.run.save()
        self.assertEqual(self.tick().status_code,409);ask.assert_not_called()
    @patch('chat.study.ask',side_effect=RuntimeError('secret-provider-details'))
    def test_provider_failure_sanitized_and_unlocked(self,ask):
        result=self.tick().json();self.assertEqual(result['status'],'failed');self.assertNotIn('secret-provider-details',json.dumps(result))
        self.run.refresh_from_db();self.assertIsNone(self.run.busy_until)
    def test_upload_validates_and_page_renders(self):
        stream=io.BytesIO();canvas=Canvas(stream);canvas.drawString(30,800,SOURCE);canvas.save()
        body={'goal':'Study plants','attachment':{'name':'plants.pdf','mediaType':'application/pdf','data':base64.b64encode(stream.getvalue()).decode()}}
        self.assertEqual(self.post('/api/study',body).status_code,201)
        body['attachment']['data']='bad';self.assertEqual(self.post('/api/study',body).status_code,400)
        self.assertContains(self.client.get('/study/'),'Follow the work.')
    @patch('chat.study.ask')
    def test_search_selects_source(self,ask):
        self.run.state={'plan':['Read','Draft','Check']};ask.return_value=action('search',{'query':'photosynthesis'})
        advance(self.run);self.assertEqual(self.run.state['seen'],[1])
    @patch('chat.study.ask')
    def test_new_draft_invalidates_old_verification(self,ask):
        self.run.state={'plan':['Read','Draft','Check'],'seen':[1],'verified':True,'draft':draft()}
        ask.return_value=action('draft',draft());advance(self.run);self.assertFalse(self.run.state['verified'])
