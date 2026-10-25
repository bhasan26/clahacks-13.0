"""Read uploaded files without substituting invented patient or treatment details."""
import io
import re
import threading
from pathlib import Path

import pymupdf
from PIL import Image

MAX_FILE_BYTES = 8 * 1024 * 1024
INSURERS = {
    'UnitedHealthcare': (r'united\s*health\s*care|\bUHC\b', ('uhcprovider.com', 'uhc.com')),
    'Aetna': (r'\baetna\b', ('aetna.com',)),
    'Cigna': (r'\bcigna\b', ('cigna.com', 'static.cigna.com')),
    'Kaiser Permanente': (r'kaiser\s+permanente', ('kaiserpermanente.org',)),
    'Humana': (r'\bhumana\b', ('humana.com',)),
    'Blue Cross Blue Shield': (r'blue\s*cross|blue\s*shield|\bBCBS\b', ('bcbs.com',)),
    'Medicare': (r'\bmedicare\b', ('cms.gov', 'medicare.gov')),
}


_ocr = None
_ocr_lock = threading.Lock()


def read_image(data: bytes, mime: str) -> str:
    """Reuse installed local OCR without an API key or remote document processing."""
    global _ocr
    try:
        from rapidocr_onnxruntime import RapidOCR
        with _ocr_lock:
            if _ocr is None:
                _ocr = RapidOCR(intra_op_num_threads=2, inter_op_num_threads=1)
            lines, _ = _ocr(data)
        text = '\n'.join(line[1] for line in (lines or []) if line[2] >= 0.8)
        if text.strip():
            return text
    except (ImportError, RuntimeError, ValueError, OSError):
        pass
    return ''


def read_document(data: bytes, filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    if not data:
        return ''
    if suffix == '.txt':
        return data.decode('utf-8-sig', errors='replace')[:30000]
    if suffix == '.pdf':
        try:
            with pymupdf.open(stream=data, filetype='pdf') as doc:
                if doc.is_encrypted or len(doc) > 5:
                    return ''
                text = '\n'.join(page.get_text() for page in doc)
                if len(text.strip()) > 30:
                    return text[:30000]
                # Scanned PDFs use the same image extraction path, at most two pages.
                return '\n'.join(read_image(page.get_pixmap(matrix=pymupdf.Matrix(1.5, 1.5)).tobytes('png'), 'image/png') for page in list(doc)[:2])
        except (RuntimeError, ValueError, pymupdf.FileDataError):
            return ''
    if suffix in {'.png', '.jpg', '.jpeg', '.webp'}:
        try:
            with Image.open(io.BytesIO(data)) as img:
                if img.width * img.height > 24000000:
                    return ''
                img.thumbnail((2200, 2200))
                out = io.BytesIO()
                img.convert('RGB').save(out, format='JPEG', quality=90)
                return read_image(out.getvalue(), 'image/jpeg')
        except (OSError, ValueError, Image.DecompressionBombError):
            return ''
    return ''


def field(text: str, labels: str) -> str | None:
    match = re.search(rf'(?im)^\s*(?:{labels})\s*[:#\-]\s*([^\n]{{1,140}})', text)
    return match.group(1).strip() if match else None


def card_fields(text: str) -> dict:
    # Only read the card, never infer an insurer from the prescription or filename.
    insurer = field(text, r'insurer|insurance\s*(?:company|provider)|carrier')
    if not insurer:
        matches = [name for name, (pattern, _) in INSURERS.items() if re.search(pattern, text, re.I)]
        insurer = matches[0] if len(matches) == 1 else None
    return {
        'insurer_name': insurer,
        'patient_name': field(text, r'member(?:\s*name)?|patient\s*name|patient|name|insured'),
        'member_id': field(text, r'member\s*(?:id|number|no\.?)|subscriber\s*(?:id|number)|identification\s*(?:id|number)|ID'),
        'plan_id': field(text, r'plan\s*(?:id|number|no\.?)'),
        'plan_name': field(text, r'plan\s*(?:name|type)|benefit\s*plan'),
        'group_number': field(text, r'group\s*(?:number|no\.?|id|#)?'),
        'effective_date': field(text, r'effective\s*(?:date|from)'),
    }


def prescription_fields(text: str) -> dict:
    name = field(text, r'rx|prescription|medication(?:\s*name)?|medicine|drug(?:\s*name)?|procedure(?:\s*name)?|treatment|order|prescribed(?:\s*medication)?')
    if not name:
        match = re.search(r'(?im)^\s*(?:prescribe[ds]?\s+)([^\n]{2,140})', text)
        if match:
            name = match.group(1).strip()
    # Common prescription line without an Rx label. Require a dose on the same line.
    if not name:
        match = re.search(r'(?im)^\s*([A-Za-z][A-Za-z ()/-]{2,70})\s+\d+(?:\.\d+)?\s*(?:mg|mcg|mL|units?)\b[^\n]*', text)
        if match and not re.match(r'sig|take|inject|dose|qty|quantity', match.group(1), re.I):
            name = match.group(0).strip()
    if name and (len(name) < 2 or re.fullmatch(r'\d+|none|unknown|n/?a', name, re.I)):
        name = None
    if name:
        name = re.sub(r'(?<=[A-Za-z])(?=\()|(?<=\))(?=[A-Za-z0-9])|(?<=[A-Za-z])(?=\d+(?:\.\d+)?(?:mg|mcg|mL)\b)', ' ', name)
    patient = field(text, r'patient(?:\s*name)?|name')
    return {'treatment_name': name, 'patient_name': patient, 'member_id': field(text, r'member\s*(?:id|number)|subscriber\s*id')}


def search_treatment(name: str) -> str:
    # Dose and instructions are unnecessary for a public policy search.
    return re.split(r'\s*\(|\s+\d+(?:\.\d+)?\s*(?:mg|mcg|ml|units?|g)\b|\s+(?:take|inject|sig:)\b', name, maxsplit=1, flags=re.I)[0].strip()[:100]
