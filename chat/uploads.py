"""Disk-backed multipart uploads for local Study Agent PDFs."""
from django.conf import settings
from django.core.files.uploadhandler import FileUploadHandler, StopUpload

class SizeLimitedUploadHandler(FileUploadHandler):
    def __init__(self, request=None):
        super().__init__(request)
        self.received=0
    def receive_data_chunk(self, raw_data, start):
        self.received+=len(raw_data)
        limit=settings.STUDY_MAX_UPLOAD_BYTES if self.request.path=='/api/study' else 2*1024*1024
        if self.received>limit:
            self.request.coex_upload_too_large=True
            raise StopUpload(connection_reset=False)
        return raw_data
    def file_complete(self, file_size):
        return None

def read_study_pdf(upload):
    from pypdf import PdfReader
    if not upload.size or upload.size>settings.STUDY_MAX_UPLOAD_BYTES:
        raise ValueError(f'Choose a nonempty PDF up to {settings.STUDY_MAX_UPLOAD_BYTES//(1024*1024)} MB.')
    if upload.read(5)!=b'%PDF-': raise ValueError('This is not a valid PDF.')
    upload.seek(0)
    try:
        reader=PdfReader(upload)
        if reader.is_encrypted: raise ValueError('Please upload an unlocked PDF.')
        total=len(reader.pages)
        if total>3000: raise ValueError('Upload a PDF with 3,000 pages or fewer.')
        parts=[];used=0;processed=0;truncated=False
        for page in reader.pages:
            if used>=3000000:
                truncated=True;break
            contents=page.get_contents()
            if contents and len(contents.get_data())>4000000:
                raise ValueError('A PDF page is too complex. Export a simpler PDF.')
            raw=page.extract_text() or ''
            text=raw[:min(20000,3000000-used)]
            truncated=truncated or len(text)<len(raw)
            parts.append(text);used+=len(text);processed+=1
        return {'text':'\n'.join(parts),'pages':total,'pages_read':processed,'truncated':truncated,
                'notice':('Only part of this PDF fits the 3,000,000-character analysis limit. Split the PDF into relevant sections for complete coverage.' if truncated else '')}
    except ValueError:
        raise
    except Exception:
        raise ValueError('This PDF could not be read. Try exporting it again.')
