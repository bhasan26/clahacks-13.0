"""
Document Processing Service for CoverageGuard Policy Intelligence.
Supports:
- Selectable-text PDF documents
- Scanned PDF documents (with page rendering for Gemini vision)
- Multimodal image formats: PNG, JPEG, JPG, WebP
- Raw pasted text
Enforces 10MB file limit and extracts page-level text and previews.
"""

import os
import re
import base64
import uuid
from typing import Dict, Any, List, Optional, Tuple

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB

SUPPORTED_MIME_TYPES = {
    "application/pdf": "pdf",
    "image/png": "png",
    "image/jpeg": "jpeg",
    "image/jpg": "jpeg",
    "image/webp": "webp",
    "text/plain": "txt",
}


class DocumentProcessingError(Exception):
    pass


def detect_file_type(filename: str, mime_type: Optional[str] = None) -> str:
    """Returns normalized extension: 'pdf', 'png', 'jpeg', 'webp', or 'txt'."""
    ext = os.path.splitext(filename.lower())[1].lstrip(".")
    if ext in ["pdf", "png", "jpeg", "jpg", "webp", "txt"]:
        return "jpeg" if ext == "jpg" else ext

    if mime_type:
        clean_mime = mime_type.split(";")[0].strip().lower()
        if clean_mime in SUPPORTED_MIME_TYPES:
            return SUPPORTED_MIME_TYPES[clean_mime]

    raise DocumentProcessingError(
        f"Unsupported file format '{filename}'. Allowed formats: PDF, PNG, JPG, WebP, TXT."
    )


def process_uploaded_document(
    file_bytes: bytes,
    filename: str,
    mime_type: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Validates, extracts, and parses document contents.
    Returns:
    {
        "document_id": str,
        "filename": str,
        "file_type": str,
        "page_count": int,
        "pages": [
            {
                "page": int,
                "text": str,
                "preview_image": Optional[str],  # data URI
                "is_scanned": bool,
                "spans": List[Dict[str, Any]],
            }
        ],
        "raw_text": str,
        "primary_image_b64": Optional[str],
        "primary_mime": Optional[str],
    }
    """
    if len(file_bytes) == 0:
        raise DocumentProcessingError(f"Document '{filename}' is empty (0 bytes).")

    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        size_mb = len(file_bytes) / (1024 * 1024)
        raise DocumentProcessingError(
            f"Document exceeds 10 MB limit ({size_mb:.1f} MB uploaded). Please upload a smaller file."
        )

    file_type = detect_file_type(filename, mime_type)
    doc_id = f"DOC-{uuid.uuid4().hex[:8].upper()}"

    if file_type == "txt":
        return _process_text(file_bytes, filename, doc_id)
    elif file_type in ["png", "jpeg", "webp"]:
        return _process_image(file_bytes, filename, file_type, doc_id)
    elif file_type == "pdf":
        return _process_pdf(file_bytes, filename, doc_id)
    else:
        raise DocumentProcessingError(f"Unhandled file type '{file_type}'.")


def _process_text(file_bytes: bytes, filename: str, doc_id: str) -> Dict[str, Any]:
    """Handles plain text / pasted policy letters."""
    try:
        text = file_bytes.decode("utf-8")
    except UnicodeDecodeError:
        text = file_bytes.decode("latin-1", errors="replace")

    return {
        "document_id": doc_id,
        "filename": filename,
        "file_type": "txt",
        "page_count": 1,
        "pages": [
            {
                "page": 1,
                "text": text,
                "preview_image": None,
                "is_scanned": False,
                "spans": [],
            }
        ],
        "raw_text": text,
        "primary_image_b64": None,
        "primary_mime": "text/plain",
    }


def _process_image(file_bytes: bytes, filename: str, file_type: str, doc_id: str) -> Dict[str, Any]:
    """Handles scanned policy images and photos."""
    mime = f"image/{'jpeg' if file_type == 'jpeg' else file_type}"
    b64 = base64.b64encode(file_bytes).decode("utf-8")
    preview_uri = f"data:{mime};base64,{b64}"

    return {
        "document_id": doc_id,
        "filename": filename,
        "file_type": file_type,
        "page_count": 1,
        "pages": [
            {
                "page": 1,
                "text": "",  # To be extracted via Gemini Vision
                "preview_image": preview_uri,
                "is_scanned": True,
                "spans": [],
            }
        ],
        "raw_text": "",
        "primary_image_b64": b64,
        "primary_mime": mime,
    }


def _process_pdf(file_bytes: bytes, filename: str, doc_id: str) -> Dict[str, Any]:
    """
    Extracts text and page previews from PDF using PyMuPDF (fitz).
    Detects scanned pages and renders high-res PNG previews for Gemini vision.
    """
    try:
        import fitz  # PyMuPDF
    except ImportError:
        # Graceful fallback if fitz is not installed
        return _fallback_pdf_processor(file_bytes, filename, doc_id)

    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
    except Exception as e:
        raise DocumentProcessingError(f"Corrupted or invalid PDF document: {e}")

    page_count = len(doc)
    if page_count == 0:
        raise DocumentProcessingError("PDF contains 0 pages.")

    pages_data: List[Dict[str, Any]] = []
    full_text_parts: List[str] = []
    first_page_image_b64: Optional[str] = None

    for page_idx in range(page_count):
        page = doc[page_idx]
        page_num = page_idx + 1

        # Extract text and words with coordinates
        page_text = page.get_text("text").strip()
        full_text_parts.append(f"--- [Page {page_num}] ---\n{page_text}")

        # Extract word spans for evidence highlighting
        spans: List[Dict[str, Any]] = []
        try:
            words = page.get_text("words")  # (x0, y0, x1, y1, word, block_no, line_no, word_no)
            for w in words[:150]:
                spans.append({
                    "word": w[4],
                    "bbox": [round(w[0], 1), round(w[1], 1), round(w[2], 1), round(w[3], 1)],
                })
        except Exception:
            pass

        # Render page to PNG preview image
        try:
            pix = page.get_pixmap(dpi=130)
            img_bytes = pix.tobytes("png")
            img_b64 = base64.b64encode(img_bytes).decode("utf-8")
            preview_uri = f"data:image/png;base64,{img_b64}"
            if page_idx == 0:
                first_page_image_b64 = img_b64
        except Exception:
            preview_uri = None

        is_scanned = len(page_text) < 40  # Less than 40 characters indicates a scanned image page

        pages_data.append({
            "page": page_num,
            "text": page_text,
            "preview_image": preview_uri,
            "is_scanned": is_scanned,
            "spans": spans,
        })

    raw_text = "\n\n".join(full_text_parts)

    return {
        "document_id": doc_id,
        "filename": filename,
        "file_type": "pdf",
        "page_count": page_count,
        "pages": pages_data,
        "raw_text": raw_text,
        "primary_image_b64": first_page_image_b64,
        "primary_mime": "image/png" if first_page_image_b64 else None,
    }


def _fallback_pdf_processor(file_bytes: bytes, filename: str, doc_id: str) -> Dict[str, Any]:
    """Extracts text per page using pypdf with stream fallback."""
    import io
    pages_data: List[Dict[str, Any]] = []
    full_text_parts: List[str] = []

    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(file_bytes))
        page_count = len(reader.pages)
        for idx, page in enumerate(reader.pages):
            p_text = (page.extract_text() or "").strip()
            p_num = idx + 1
            full_text_parts.append(f"--- [Page {p_num}] ---\n{p_text}")
            pages_data.append({
                "page": p_num,
                "text": p_text,
                "preview_image": None,
                "is_scanned": len(p_text) < 40,
                "spans": [],
            })
        if page_count > 0:
            return {
                "document_id": doc_id,
                "filename": filename,
                "file_type": "pdf",
                "page_count": page_count,
                "pages": pages_data,
                "raw_text": "\n\n".join(full_text_parts),
                "primary_image_b64": None,
                "primary_mime": None,
            }
    except Exception as e:
        print(f"pypdf extraction notice: {e}")

    # Raw ASCII stream parser as last-mile resilience
    text_content = ""
    try:
        raw_str = file_bytes.decode("latin-1", errors="ignore")
        stream_matches = re.findall(r"stream[\r\n]+(.*?)[\r\n]+endstream", raw_str, re.DOTALL)
        extracted = []
        for s in stream_matches:
            printable = re.sub(r"[^\x20-\x7E\n\r\t]", " ", s)
            cleaned = " ".join(printable.split())
            if len(cleaned) > 20:
                extracted.append(cleaned)
        text_content = "\n".join(extracted)
    except Exception:
        pass

    if not text_content.strip():
        text_content = "PDF document uploaded."

    return {
        "document_id": doc_id,
        "filename": filename,
        "file_type": "pdf",
        "page_count": 1,
        "pages": [
            {
                "page": 1,
                "text": text_content,
                "preview_image": None,
                "is_scanned": True,
                "spans": [],
            }
        ],
        "raw_text": text_content,
        "primary_image_b64": None,
        "primary_mime": None,
    }
