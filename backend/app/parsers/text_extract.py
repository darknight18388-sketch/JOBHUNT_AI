"""Extract plain text from PDF/DOCX. Pure-Python (pypdf + stdlib zip/xml)."""
import zipfile
from pathlib import Path

from defusedxml import ElementTree as ET

MAX_TEXT_CHARS = 200_000
MAX_PDF_PAGES = 15
MAX_DOCX_XML_BYTES = 10 * 1024 * 1024
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


class CVParseError(Exception):
    """Raised with a safe, user-facing message."""


def _pdf_text(path: Path) -> str:
    from pypdf import PdfReader

    try:
        reader = PdfReader(str(path))
        if reader.is_encrypted:
            raise CVParseError("Password-protected PDFs are not supported")
        parts = [(p.extract_text() or "") for p in reader.pages[:MAX_PDF_PAGES]]
    except CVParseError:
        raise
    except Exception:
        raise CVParseError("Could not read this PDF file")
    return "\n".join(parts)


def _docx_text(path: Path) -> str:
    try:
        with zipfile.ZipFile(path) as z:
            info = z.getinfo("word/document.xml")
            if info.file_size > MAX_DOCX_XML_BYTES:
                raise CVParseError("DOCX content is too large")
            root = ET.fromstring(z.read("word/document.xml"))
    except CVParseError:
        raise
    except Exception:
        raise CVParseError("Could not read this DOCX file")
    paragraphs = []
    for p in root.iter(f"{W}p"):
        buf = []
        for el in p.iter():
            if el.tag == f"{W}t" and el.text:
                buf.append(el.text)
            elif el.tag in (f"{W}tab", f"{W}br"):
                buf.append(" ")
        paragraphs.append("".join(buf))
    return "\n".join(paragraphs)


def extract_text(path: Path, ext: str) -> str:
    text = _pdf_text(path) if ext == ".pdf" else _docx_text(path)
    text = text.replace("\x00", "").strip()[:MAX_TEXT_CHARS]
    if len(text) < 20:
        raise CVParseError(
            "No readable text found (scanned/image-only files are not supported yet)")
    return text
