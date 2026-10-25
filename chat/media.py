"""PDF and image processing shared with the previous deployment."""
import base64
import io
from xml.sax.saxutils import escape
MAX_FILE = 2 * 1024 * 1024

def process(body):
    action = body.get("action")
    if action == "create_pdf":
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        text = body.get("text", "")
        title = body.get("title", "coex document")
        if not isinstance(text, str) or not text.strip() or len(text) > 60000 or not isinstance(title, str) or len(title) > 160:
            raise ValueError("Enter a title up to 160 characters and text up to 60,000 characters.")
        # Explicit limitation instead of silently emitting missing Unicode glyphs.
        try:
            (text + title).encode("cp1252")
        except UnicodeEncodeError:
            raise ValueError("PDF export currently supports Latin-script text. Hindi and other scripts need a Unicode font integration.")
        styles = getSampleStyleSheet()
        stream = io.BytesIO()
        story = [Paragraph(escape(title), styles["Title"]), Spacer(1, 18)]
        story.extend(Paragraph(escape(line) or "&#160;", styles["BodyText"]) for line in text.splitlines())
        SimpleDocTemplate(stream, title=title, author="coex", leftMargin=48, rightMargin=48, topMargin=48, bottomMargin=48).build(story)
        return {"data": base64.b64encode(stream.getvalue()).decode(), "mediaType": "application/pdf"}
    if action != "inspect":
        raise ValueError("Unsupported media action.")
    encoded = body.get("data", "")
    if not isinstance(encoded, str) or len(encoded) > 2800000:
        raise ValueError("Choose a file smaller than 2 MB.")
    try:
        data = base64.b64decode(encoded, validate=True)
    except Exception:
        raise ValueError("The uploaded file could not be decoded.")
    if not data or len(data) > MAX_FILE:
        raise ValueError("Choose a nonempty file smaller than 2 MB.")
    if body.get("mediaType") == "application/pdf":
        from pypdf import PdfReader
        if not data.startswith(b"%PDF-"):
            raise ValueError("This is not a valid PDF.")
        try:
            reader = PdfReader(io.BytesIO(data))
            if reader.is_encrypted:
                raise ValueError("Please upload an unlocked PDF.")
            if len(reader.pages) > 40:
                raise ValueError("Upload a PDF with 40 pages or fewer.")
            excerpts = []
            for page in reader.pages:
                contents = page.get_contents()
                if contents and len(contents.get_data()) > 4000000:
                    raise ValueError("This PDF page is too complex. Export a smaller PDF.")
                excerpts.append((page.extract_text() or "")[:12000])
            text = "\n\n".join(excerpts)[:60000]
            return {"mediaType": "application/pdf", "pages": len(reader.pages), "text": text, "scanned": not bool(text.strip())}
        except ValueError:
            raise
        except Exception:
            raise ValueError("This PDF could not be read. Try exporting it again.")
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = 12000000
    try:
        with Image.open(io.BytesIO(data)) as image:
            if image.format not in ("PNG", "JPEG", "WEBP") or image.width * image.height > 12000000:
                raise ValueError()
            media_type = Image.MIME[image.format]
            width, height = image.size
            image.verify()
        return {"mediaType": media_type, "width": width, "height": height}
    except Exception:
        raise ValueError("Upload a valid PNG, JPEG or WebP image up to 12 megapixels.")

