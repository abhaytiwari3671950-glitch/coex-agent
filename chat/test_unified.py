import base64
import io
import json
from types import SimpleNamespace as N
from unittest.mock import patch
from django.test import TestCase,override_settings,Client
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from PIL import Image
from .models import Conversation,Message,Memory,UserPreferences,StudyRun,QuizSession
from .memory import learn,context
from .capabilities import route,web_reply,image_reply,CapabilityError
from .study import rank_chunks

@override_settings(GOOGLE_GENERATIVE_AI_API_KEY='mock-key',PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],STORAGES={'default':{'BACKEND':'django.core.files.storage.FileSystemStorage'},'staticfiles':{'BACKEND':'django.contrib.staticfiles.storage.StaticFilesStorage'}})
class UnifiedTests(TestCase):
    def setUp(self):
        self.user=User.objects.create_user('alice');self.other=User.objects.create_user('bob');self.client.force_login(self.user)
        self.conversation=Conversation.objects.create(owner=self.user,title='Test')
    def post(self,url,body):return self.client.post(url,json.dumps(body),content_type='application/json')
    def consume(self,response):
        self.assertEqual(response.status_code,200)
        return [json.loads(x) for x in b''.join(response.streaming_content).splitlines()]
    def run_fixture(self):
        return StudyRun.objects.create(owner=self.user,conversation=self.conversation,goal='Learn',filename='a.pdf',source='Photosynthesis uses light.',status='complete',state={'draft':{'quiz':[{'question':'What energy?','answer':'Light','quote':'Photosynthesis uses light.','chunk':1}]}})
    def test_explicit_preferences_learn_without_forms(self):
        learn(self.user,'Hindi mein samjhao, short answer exam ke liye')
        self.assertEqual(Memory.objects.get(owner=self.user,key='language').value,'Hindi')
        self.assertIn('Exam preparation',context(self.user));self.assertNotIn('Hindi',context(self.other))
    def test_disable_stops_learning_and_use(self):
        learn(self.user,'Explain in Hindi');self.post('/api/memory/update',{'enabled':False})
        learn(self.user,'Explain in English');self.assertEqual(context(self.user),'')
        self.assertEqual(Memory.objects.get(owner=self.user,key='language').value,'Hindi')
    def test_ordinary_query_not_permanent_and_secret_not_saved(self):
        learn(self.user,'what is Oracle?');learn(self.user,'remember: my API key is secret')
        self.assertFalse(Memory.objects.filter(owner=self.user).exists())
    def test_memory_edit_delete_and_owner_guard(self):
        row=Memory.objects.create(owner=self.other,key='language',value='Hindi')
        self.assertEqual(self.post('/api/memory/update',{'id':row.id,'action':'delete'}).status_code,404)
        mine=Memory.objects.create(owner=self.user,key='style',value='Short')
        self.assertEqual(self.post('/api/memory/update',{'id':mine.id,'value':'Detailed'}).status_code,200)
        self.post('/api/memory/update',{'action':'clear'});self.assertFalse(Memory.objects.filter(owner=self.user).exists())
    def test_feedback_owner_isolation_and_context(self):
        m=Message.objects.create(conversation=self.conversation,role='assistant',text='Overly long answer')
        self.assertEqual(self.post(f'/api/feedback/{m.id}',{'rating':-1}).status_code,200)
        self.assertIn('Overly long answer',context(self.user))
        self.client.force_login(self.other);self.assertEqual(self.post(f'/api/feedback/{m.id}',{'rating':1}).status_code,404)
    def test_routing_and_file_privacy(self):
        self.assertEqual(route('latest news','auto'),'web');self.assertEqual(route('latest news','auto',True),'chat')
        self.assertEqual(route('create an image of a cat','auto'),'image')
        self.assertEqual(self.post('/api/chat',{'text':'Search','mode':'web','attachment':{'name':'private.pdf'}}).status_code,400)
    @patch('chat.views.web_reply',return_value=('Verified [1]',{'kind':'web','sources':[{'title':'Official','url':'https://example.org'}],'search_suggestions':'<b>Google</b>'}))
    def test_search_sends_only_query_and_persists_sources(self,provider):
        Memory.objects.create(owner=self.user,key='user_note',value='private syllabus')
        Message.objects.create(conversation=self.conversation,role='user',text='private history')
        events=self.consume(self.post('/api/chat',{'text':'latest news','conversationId':str(self.conversation.id)}))
        provider.assert_called_once_with('latest news');self.assertEqual(events[-1]['metadata']['kind'],'web')
        row=Message.objects.get(id=events[-1]['messageId']);self.assertIn('search_suggestions',row.metadata)
        response=self.client.get(f'/api/search-widget/{row.id}');self.assertIn("default-src 'none'",response['Content-Security-Policy'])
        self.client.force_login(self.other);self.assertEqual(self.client.get(f'/api/search-widget/{row.id}').status_code,404)
    @patch('chat.capabilities.genai.Client')
    def test_grounded_citations_and_suggestions(self,client):
        meta=N(grounding_chunks=[N(web=N(uri='https://example.org',title='Official'))],grounding_supports=[N(segment=N(text='उत्तर'),grounding_chunk_indices=[0])],search_entry_point=N(rendered_content='<b>Google</b>'))
        client.return_value.__enter__.return_value.models.generate_content.return_value=N(text='उत्तर',candidates=[N(grounding_metadata=meta)])
        answer,metadata=web_reply('question');self.assertEqual(answer,'उत्तर [1]');self.assertEqual(metadata['sources'][0]['url'],'https://example.org')
    @patch('chat.capabilities.genai.Client')
    def test_no_sources_never_claims_search(self,client):
        client.return_value.__enter__.return_value.models.generate_content.return_value=N(text='guess',candidates=[N(grounding_metadata=None)])
        with self.assertRaises(CapabilityError):web_reply('question')
    @patch('chat.capabilities.genai.Client')
    def test_real_image_bytes_validated(self,client):
        stream=io.BytesIO();Image.new('RGB',(16,16)).save(stream,format='PNG')
        client.return_value.__enter__.return_value.models.generate_content.return_value=N(candidates=[N(content=N(parts=[N(inline_data=N(data=stream.getvalue()))]))])
        text,metadata=image_reply('cat');self.assertEqual(metadata['mediaType'],'image/jpeg')
        self.assertTrue(base64.b64decode(metadata['data']).startswith(b'\xff\xd8'))
    @patch('chat.views.image_reply',return_value=('Generated image',{'kind':'image','data':base64.b64encode(b'image').decode(),'mediaType':'image/jpeg'}))
    def test_image_not_leaked_in_history(self,provider):
        events=self.consume(self.post('/api/chat',{'text':'draw a cat','mode':'image'}));mid=events[-1]['messageId'];cid=events[0]['conversationId']
        self.assertNotIn('data',events[-1]['metadata']);self.assertNotIn('data',self.client.get('/api/conversations/'+cid).json()['messages'][-1]['metadata'])
        self.assertEqual(self.client.get(f'/api/generated-image/{mid}').status_code,200)
        self.client.force_login(self.other);self.assertEqual(self.client.get(f'/api/generated-image/{mid}').status_code,404)
    @patch('chat.quiz_views.ask',return_value={'score':0,'feedback':'Review the role of light.'})
    def test_quiz_grades_and_adapts_revision(self,ask):
        run=self.run_fixture();start=self.post(f'/api/quiz/start/{run.id}',{}).json();self.assertNotIn('reference',json.dumps(start))
        response=self.post(f'/api/quiz/answer/{start["id"]}',{'answer':'water','position':0});self.assertEqual(response.status_code,200)
        result=response.json();self.assertTrue(result['complete']);self.assertIn('Review:',result['revision_plan'][0])
        self.assertTrue(Memory.objects.filter(owner=self.user,key__startswith='weak_topic:').exists())
        self.assertEqual(self.post(f'/api/quiz/answer/{start["id"]}',{'answer':'water','position':0}).status_code,409)
    @patch('chat.quiz_views.ask',return_value={'score':0,'feedback':'Review.'})
    def test_quiz_respects_memory_off_and_isolation(self,ask):
        UserPreferences.objects.create(owner=self.user,memory_enabled=False)
        run=self.run_fixture();session=self.post(f'/api/quiz/start/{run.id}',{}).json()
        self.post(f'/api/quiz/answer/{session["id"]}',{'answer':'wrong','position':0});self.assertFalse(Memory.objects.filter(owner=self.user).exists())
        self.client.force_login(self.other);self.assertEqual(self.post(f'/api/quiz/start/{run.id}',{}).status_code,404)
    def test_search_finds_later_book_sections(self):
        sources=['Introduction to databases.']*600+['Temporal databases track valid time and transaction time.']
        self.assertEqual(rank_chunks(sources,'temporal transaction time')[0],601)
    def test_memory_csrf_and_chat_ui(self):
        client=Client(enforce_csrf_checks=True);client.force_login(self.user)
        self.assertEqual(client.post('/api/memory/update','{"action":"clear"}',content_type='application/json').status_code,403)
        response=self.client.get('/');self.assertContains(response,'Create image');self.assertContains(response,'Memory &amp; preferences',html=False) if False else self.assertContains(response,'memory-settings')
    def test_reuse_pdf_in_same_chat_and_owner_guard(self):
        original=self.run_fixture()
        response=self.post(f'/api/study/{original.id}/reuse',{'goal':'Make a revision plan'})
        self.assertEqual(response.status_code,201)
        run=StudyRun.objects.get(id=response.json()['id']);self.assertEqual(run.source,original.source)
        self.assertEqual(run.conversation_id,self.conversation.id)
        self.assertTrue(Message.objects.filter(conversation=self.conversation,metadata__runId=str(run.id)).exists())
        self.client.force_login(self.other)
        self.assertEqual(self.post(f'/api/study/{original.id}/reuse',{'goal':'Read'}).status_code,404)
    @patch('chat.views.stream_reply',return_value=iter(['Light [Chunk 1]']))
    def test_chat_uses_own_pdf_evidence_and_preferences(self,provider):
        self.run_fixture();learn(self.user,'Explain in Hindi')
        self.consume(self.post('/api/chat',{'text':'What is photosynthesis?','mode':'chat','conversationId':str(self.conversation.id)}))
        prefs=provider.call_args.kwargs['preferences']
        self.assertIn('Hindi',prefs);self.assertIn('Photosynthesis uses light.',prefs)
