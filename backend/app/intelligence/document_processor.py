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
    "text/html": "txt",
    "application/xhtml+xml": "txt",
}


class DocumentProcessingError(Exception):
    pass


def detect_file_type(filename: str, mime_type: Optional[str] = None) -> str:
    """Returns normalized extension: 'pdf', 'png', 'jpeg', 'webp', or 'txt'."""
    ext = os.path.splitext(filename.lower())[1].lstrip(".")
    if ext in ["pdf", "png", "jpeg", "jpg", "webp", "txt", "html", "htm"]:
        if ext == "jpg":
            return "jpeg"
        if ext in ["html", "htm"]:
            return "txt"
        return ext

    if mime_type:
        clean_mime = mime_type.split(";")[0].strip().lower()
        if clean_mime in SUPPORTED_MIME_TYPES:
            return SUPPORTED_MIME_TYPES[clean_mime]

    raise DocumentProcessingError(
        f"Unsupported file format '{filename}'. Allowed formats: PDF, PNG, JPG, WebP, TXT, HTML."
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

    # If HTML document, strip tags to extract clean readable policy text
    if filename.lower().endswith((".html", ".htm")) or "<html" in text.lower():
        text = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<(br|p|div|h[1-6]|li)[^>]*>", "\n", text, flags=re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n\s*\n+", "\n\n", text).strip()

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


MAX_PDF_PAGES = 10


def _process_pdf(file_bytes: bytes, filename: str, doc_id: str) -> Dict[str, Any]:
    """
    Extracts text and page previews from PDF using fitz (PyMuPDF) if available,
    or pypdf as robust native fallback.
    Detects scanned pages and extracts embedded images or rendered previews for Gemini vision.
    Supports up to MAX_PDF_PAGES with warnings if truncated.
    """
    try:
        import fitz  # PyMuPDF
        return _process_pdf_with_fitz(file_bytes, filename, doc_id)
    except ImportError:
        return _process_pdf_with_pypdf(file_bytes, filename, doc_id)


def _process_pdf_with_fitz(file_bytes: bytes, filename: str, doc_id: str) -> Dict[str, Any]:
    import fitz
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
    except Exception as e:
        raise DocumentProcessingError(f"Corrupted or invalid PDF document: {e}")

    total_pages = len(doc)
    if total_pages == 0:
        raise DocumentProcessingError("PDF contains 0 pages.")

    pages_to_process = min(total_pages, MAX_PDF_PAGES)
    warnings: List[str] = []
    if total_pages > MAX_PDF_PAGES:
        warnings.append(
            f"Document contains {total_pages} pages. Processing was bounded to the first {MAX_PDF_PAGES} pages."
        )

    pages_data: List[Dict[str, Any]] = []
    full_text_parts: List[str] = []
    scanned_images: List[Dict[str, Any]] = []
    first_image_b64: Optional[str] = None
    first_image_mime: Optional[str] = None

    for page_idx in range(pages_to_process):
        page = doc[page_idx]
        page_num = page_idx + 1

        page_text = page.get_text("text").strip()
        full_text_parts.append(f"--- [Page {page_num}] ---\n{page_text}")

        spans: List[Dict[str, Any]] = []
        try:
            words = page.get_text("words")
            for w in words[:150]:
                spans.append({
                    "word": w[4],
                    "bbox": [round(w[0], 1), round(w[1], 1), round(w[2], 1), round(w[3], 1)],
                })
        except Exception:
            pass

        preview_uri = None
        is_scanned = len(page_text) < 40
        try:
            pix = page.get_pixmap(dpi=130)
            img_bytes = pix.tobytes("png")
            img_b64 = base64.b64encode(img_bytes).decode("utf-8")
            preview_uri = f"data:image/png;base64,{img_b64}"
            if not first_image_b64:
                first_image_b64 = img_b64
                first_image_mime = "image/png"
            if is_scanned and len(scanned_images) < 5:
                scanned_images.append({
                    "page": page_num,
                    "mime": "image/png",
                    "b64": img_b64,
                })
        except Exception:
            pass

        pages_data.append({
            "page": page_num,
            "text": page_text,
            "preview_image": preview_uri,
            "is_scanned": is_scanned,
            "spans": spans,
        })

    return {
        "document_id": doc_id,
        "filename": filename,
        "file_type": "pdf",
        "page_count": pages_to_process,
        "total_pages": total_pages,
        "pages": pages_data,
        "raw_text": "\n\n".join(full_text_parts),
        "primary_image_b64": first_image_b64,
        "primary_mime": first_image_mime,
        "scanned_page_images": scanned_images,
        "warnings": warnings,
    }


def _process_pdf_with_pypdf(file_bytes: bytes, filename: str, doc_id: str) -> Dict[str, Any]:
    """Extracts text and embedded images per page using pypdf."""
    import io
    try:
        from pypdf import PdfReader
    except ImportError:
        return _fallback_raw_pdf_processor(file_bytes, filename, doc_id)

    try:
        reader = PdfReader(io.BytesIO(file_bytes))
    except Exception as e:
        raise DocumentProcessingError(f"Corrupted or invalid PDF document: {e}")

    total_pages = len(reader.pages)
    if total_pages == 0:
        raise DocumentProcessingError("PDF contains 0 pages.")

    pages_to_process = min(total_pages, MAX_PDF_PAGES)
    warnings: List[str] = []
    if total_pages > MAX_PDF_PAGES:
        warnings.append(
            f"Document contains {total_pages} pages. Processing was bounded to the first {MAX_PDF_PAGES} pages."
        )

    pages_data: List[Dict[str, Any]] = []
    full_text_parts: List[str] = []
    scanned_images: List[Dict[str, Any]] = []
    first_image_b64: Optional[str] = None
    first_image_mime: Optional[str] = None

    for page_idx in range(pages_to_process):
        page = reader.pages[page_idx]
        page_num = page_idx + 1

        try:
            page_text = (page.extract_text() or "").strip()
        except Exception:
            page_text = ""

        full_text_parts.append(f"--- [Page {page_num}] ---\n{page_text}")
        is_scanned = len(page_text) < 40

        preview_uri = None
        # Extract embedded images if scanned or available
        try:
            if hasattr(page, "images") and len(page.images) > 0:
                # Get the largest image on the page
                img_obj = sorted(page.images, key=lambda img: len(img.data), reverse=True)[0]
                img_data = img_obj.data
                img_name = getattr(img_obj, "name", "image.png").lower()
                mime = "image/jpeg" if img_name.endswith((".jpg", ".jpeg")) else "image/png"
                img_b64 = base64.b64encode(img_data).decode("utf-8")
                preview_uri = f"data:{mime};base64,{img_b64}"
                if not first_image_b64:
                    first_image_b64 = img_b64
                    first_image_mime = mime
                if len(scanned_images) < 5:
                    scanned_images.append({
                        "page": page_num,
                        "mime": mime,
                        "b64": img_b64,
                    })
        except Exception as img_err:
            pass

        pages_data.append({
            "page": page_num,
            "text": page_text,
            "preview_image": preview_uri,
            "is_scanned": is_scanned,
            "spans": [],
        })

    return {
        "document_id": doc_id,
        "filename": filename,
        "file_type": "pdf",
        "page_count": pages_to_process,
        "total_pages": total_pages,
        "pages": pages_data,
        "raw_text": "\n\n".join(full_text_parts),
        "primary_image_b64": first_image_b64,
        "primary_mime": first_image_mime,
        "scanned_page_images": scanned_images,
        "warnings": warnings,
    }


def _fallback_raw_pdf_processor(file_bytes: bytes, filename: str, doc_id: str) -> Dict[str, Any]:
    """Raw stream regex parser as last-mile resilience if pypdf fails."""
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
        "total_pages": 1,
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
        "scanned_page_images": [],
        "warnings": [],
    }
