import io
from unittest.mock import patch
from django.test import TestCase, override_settings, RequestFactory
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile, TemporaryUploadedFile
from django.core.files.uploadhandler import StopUpload
from reportlab.pdfgen.canvas import Canvas
from .uploads import SizeLimitedUploadHandler, read_study_pdf
from .models import StudyRun

@override_settings(GOOGLE_GENERATIVE_AI_API_KEY='mock-key',PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class UploadTests(TestCase):
    def setUp(self):
        self.client.force_login(User.objects.create_user('uploader'))
    def pdf(self):
        f=io.BytesIO();c=Canvas(f);c.drawString(30,800,'Photosynthesis uses sunlight to produce chemical energy.');c.save();return f.getvalue()
    def upload(self,raw):
        return self.client.post('/api/study',{'goal':'Study photosynthesis','file':SimpleUploadedFile('notes.pdf',raw,'application/pdf')})
    def test_exact_100_mib_disk_upload_and_real_pdf_parsing(self):
        # Keep xref offsets intact, insert a large legal PDF comment before startxref.
        raw=self.pdf();position=raw.rindex(b'startxref');padding=100*1024*1024-len(raw)
        raw=raw[:position]+b'%'+b'x'*(padding-2)+b'\n'+raw[position:]
        self.assertEqual(len(raw),100*1024*1024)
        with patch('chat.study_views.read_study_pdf',wraps=read_study_pdf) as parser:
            result=self.upload(raw)
        self.assertEqual(result.status_code,201,result.content)
        self.assertIsInstance(parser.call_args.args[0],TemporaryUploadedFile)
        self.assertIn('Photosynthesis',StudyRun.objects.get(id=result.json()['id']).source)
    @override_settings(STUDY_MAX_UPLOAD_BYTES=1024)
    def test_oversize_multipart_rejected(self):
        self.assertEqual(self.upload(b'%PDF-'+b'x'*1024).status_code,413)
        self.assertFalse(StudyRun.objects.exists())
    def test_exact_boundary_and_one_byte_over_in_stream_handler(self):
        request=RequestFactory().post('/api/study');handler=SizeLimitedUploadHandler(request)
        handler.received=100*1024*1024-1
        self.assertEqual(handler.receive_data_chunk(b'x',0),b'x')
        with self.assertRaises(StopUpload):handler.receive_data_chunk(b'x',1)
        self.assertTrue(request.coex_upload_too_large)
    def test_fake_pdf_rejected(self):
        self.assertEqual(self.upload(b'not a pdf').status_code,400)
    def test_more_than_forty_pages_supported_and_truncation_disclosed(self):
        f=io.BytesIO();c=Canvas(f)
        for _ in range(45):
            text=c.beginText(20,800);text.textLines(('Source information about photosynthesis. '*50+'\n')*2);c.drawText(text);c.showPage()
        c.save();result=self.upload(f.getvalue());self.assertEqual(result.status_code,201)
        run=StudyRun.objects.get(id=result.json()['id'])
        self.assertTrue(run.state['source_limits']['truncated'])
        self.assertEqual(run.trace[0]['action'],'source_limit')
    def test_small_multipart_with_csrf(self):
        from django.test import Client
        client=Client(enforce_csrf_checks=True);client.force_login(User.objects.get(username='uploader'))
        self.assertEqual(client.post('/api/study',{'goal':'Study','file':SimpleUploadedFile('a.pdf',self.pdf())}).status_code,403)
