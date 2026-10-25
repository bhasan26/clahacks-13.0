"""
Local-only synthetic clinical intake.
Selectable text is parsed locally; scanned images require manual structured entry.
Clinical files, member references and identifiers are never sent to external AI.
"""

import os
import re
import json
import base64
from typing import Optional, Dict, Any, List
import httpx


def get_gemini_api_key() -> Optional[str]:
    from app.intelligence.policy_extractor import get_gemini_api_key as shared_key
    return shared_key()


def extract_base64_and_mime(data_uri_or_b64: str) -> tuple[str, str]:
    """Parse data URI or raw base64 and return (clean_b64, mime_type)."""
    if len(data_uri_or_b64) > 14 * 1024 * 1024:
        raise ValueError("Uploaded file exceeds size limit.")
    if data_uri_or_b64.startswith("data:"):
        match = re.match(r"data:([^;]+);base64,(.*)", data_uri_or_b64)
        if match:
            clean, mime = match.group(2), match.group(1)
            decoded = base64.b64decode(clean, validate=True)
            if len(decoded) > 10 * 1024 * 1024:
                raise ValueError("Uploaded file exceeds 10 MB limit.")
            if mime not in {"application/pdf", "image/png", "image/jpeg", "image/webp", "text/plain"}:
                raise ValueError("Unsupported intake file type.")
            return clean, mime
    # Default to image/jpeg if raw base64
    decoded = base64.b64decode(data_uri_or_b64, validate=True)
    if len(decoded) > 10 * 1024 * 1024:
        raise ValueError("Uploaded file exceeds 10 MB limit.")
    return data_uri_or_b64, "application/pdf" if decoded.startswith(b"%PDF-") else "image/jpeg"


def get_fallback_sample(sample_id: str) -> Dict[str, Any]:
    """Provides instant verified sample presets for 1-click testing."""
    if sample_id == "bcbs_ozempic":
        return {
            "card": {
                "insurer_name": "Blue Cross Blue Shield",
                "insurer_id": "bcbs",
                "member_ref": "FEP-4029108",
                "group_number": "GRP-005890",
                "plan_id": "BCBS-FEP-PPO",
                "plan_name": "Federal Employee Program (FEP PPO)",
                "copay": "$35 Specialist",
                "confidence": 0.98,
            },
            "clinical": {
                "patient_name": "Robert Hayes",
                "specialty": "Gastroenterology",
                "service_date": "2026-11-05",
                "diagnosis_code": "E66.01",
                "diagnosis_desc": "Morbid Obesity without Type 2 Diabetes",
                "items": [
                    {
                        "type": "drug",
                        "code": "OZEMPIC",
                        "name": "Ozempic (Semaglutide) 1mg/dose subcutaneous pen",
                        "quantity": 1,
                    }
                ],
                "documents": ["Encounter Note"],
                "prior_approval_ref": None,
                "confidence": 0.97,
            },
        }
    elif sample_id == "uhc_ortho":
        return {
            "card": {
                "insurer_name": "UnitedHealthcare",
                "insurer_id": "uhc",
                "member_ref": "UHC-902837110",
                "group_number": "GRP-710294",
                "plan_id": "UHC-CHOICE-PLUS",
                "plan_name": "UnitedHealthcare Choice Plus PPO",
                "copay": "$50 Hospital",
                "confidence": 0.98,
            },
            "clinical": {
                "patient_name": "Marcus Brody",
                "specialty": "Orthopedics",
                "service_date": "2026-11-15",
                "diagnosis_code": "M17.11",
                "diagnosis_desc": "Unilateral Primary Osteoarthritis Right Knee",
                "items": [
                    {
                        "type": "procedure",
                        "code": "PROC-1",
                        "name": "Total Knee Arthroplasty (PROC-1 / CPT 27447)",
                        "quantity": 1,
                    }
                ],
                "documents": ["Orthopedic Consult Notes", "Pre-Op Clearance"],
                "prior_approval_ref": "PA-UHC-88219",
                "confidence": 0.96,
            },
        }
    elif sample_id == "aetna_keytruda":
        return {
            "card": {
                "insurer_name": "Aetna Health",
                "insurer_id": "aetna",
                "member_ref": "W92837482",
                "group_number": "GRP-881290-001",
                "plan_id": "AETNA-POS-II",
                "plan_name": "Open Choice POS II (Commercial)",
                "copay": "$25 Specialist",
                "confidence": 0.99,
            },
            "clinical": {
                "patient_name": "Eleanor Vance",
                "specialty": "Oncology",
                "service_date": "2026-11-10",
                "diagnosis_code": "C34.90",
                "diagnosis_desc": "Non-Small Cell Lung Carcinoma (Stage IV)",
                "items": [
                    {
                        "type": "drug",
                        "code": "KEYTRUDA",
                        "name": "Keytruda (Pembrolizumab) 200mg IV Infusion",
                        "quantity": 1,
                    }
                ],
                "documents": ["Oncology Clinical Summary"],
                "prior_approval_ref": None,
                "confidence": 0.98,
            },
        }


    raise ValueError("Unknown synthetic sample preset.")

def call_gemini_extraction(
    parts: List[Dict[str, Any]],
    system_instruction: str,
) -> Optional[Dict[str, Any]]:
    """Clinical AI transmission is disabled; extraction stays local in this prototype."""
    return None


def analyze_insurance_card(
    image_b64: Optional[str] = None,
    text_content: Optional[str] = None,
) -> Dict[str, Any]:
    """Extracts insurer name, member ID, group number, and plan from card (if provided)."""
    # If no card was uploaded, return empty dictionary immediately without calling LLM
    if not image_b64 and not (text_content and text_content.strip()):
        return {
            "insurer_name": "",
            "insurer_id": "",
            "member_ref": "",
            "group_number": "",
            "plan_name": "",
            "plan_id": "",
            "copay": "",
            "confidence": 0.0,
        }

    if text_content and not image_b64:
        from app.intelligence.policy_extractor import _deterministic_fallback_extractor
        # Reuse explicit identity recognition, without guessing a plan from the payer.
        extracted = _deterministic_fallback_extractor({"raw_text": "Insurance policy card\n" + text_content})
        payer = extracted[0] if extracted else None
        def field(pattern):
            match = re.search(pattern, text_content, re.I)
            return match.group(1).strip() if match else None
        return {"insurer_id": payer.insurer_id if payer else None,
                "insurer_name": payer.insurer_name if payer else None,
                "plan_id": field(r"Plan(?: ID)?\s*[:#]\s*([^\n]+)"),
                "plan_name": field(r"Plan Name\s*[:#]\s*([^\n]+)"),
                "member_ref": field(r"(?:Member|Subscriber)(?: ID)?\s*[:#]\s*([A-Z0-9-]+)"),
                "group_number": field(r"Group(?: Number)?\s*[:#]\s*([A-Z0-9-]+)"),
                "confidence": None,
                "validation_warnings": ["Review extracted identifiers; absent fields remain unknown."]}

    parts = []
    if image_b64:
        clean_b64, mime = extract_base64_and_mime(image_b64)
        parts.append({"inlineData": {"mimeType": mime, "data": clean_b64}})

    prompt = (
        "Inspect this health insurance card (front/back or text). "
        "Extract the exact details into JSON with keys: "
        "insurer_name (e.g. Aetna, Blue Cross Blue Shield, UnitedHealthcare, Cigna, Medicare), "
        "insurer_id ('aetna' | 'bcbs' | 'uhc' | 'cigna' | 'cms' | 'demo-insurer'), "
        "member_ref (member or subscriber ID), "
        "group_number (group ID), "
        "plan_name (e.g. Open Choice POS II, Federal Employee Program, PPO), "
        "plan_id (short identifier like 'AETNA-POS' or 'PLAN-GOLD'), "
        "copay (e.g. '$25 Specialist'), "
        "rx_bin (if present)."
    )
    if text_content:
        text_content, _ = redact_sensitive_identifiers(text_content)
        prompt += f"\n\nCard Text Content:\n{text_content}"

    parts.append({"text": prompt})

    sys_instr = (
        "You are an expert healthcare insurance claim intake assistant. "
        "Analyze synthetic insurance card images or text. Missing fields must be null; never guess plans or identifiers. Output strict JSON only."
    )

    result = call_gemini_extraction(parts, sys_instr)
    if result:
        return result

    return {"insurer_name": None, "insurer_id": None, "member_ref": None,
            "group_number": None, "plan_name": None, "plan_id": None, "copay": None,
            "confidence": None, "validation_warnings": ["Insurance card could not be extracted. Supply verified payer and plan."]}


def redact_sensitive_identifiers(text: str) -> tuple[str, bool]:
    """Redacts real SSNs, phone numbers, and email addresses from clinical text before LLM calls."""
    redacted = False
    ssn_pattern = r"\b\d{3}-\d{2}-\d{4}\b"
    if re.search(ssn_pattern, text):
        text = re.sub(ssn_pattern, "[REDACTED_SSN]", text)
        redacted = True
    phone_pattern = r"\b(?:\+?1[-. ]?)?\(?\d{3}\)?[-. ]?\d{3}[-. ]?\d{4}\b"
    if re.search(phone_pattern, text):
        text = re.sub(phone_pattern, "[REDACTED_PHONE]", text)
        redacted = True
    email_pattern = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
    if re.search(email_pattern, text):
        text = re.sub(email_pattern, "[REDACTED_EMAIL]", text)
        redacted = True
    return text, redacted


def analyze_clinical_document(
    doc_b64: Optional[str] = None,
    text_content: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Extracts diagnosis, specialty, prescribed items, attached documents, and primary insurer.
    Supports selectable PDFs, scanned docs, images, and text notes.
    """
    # If PDF is uploaded as base64, extract text via pypdf
    if doc_b64:
        clean_b64, mime = extract_base64_and_mime(doc_b64)
        if mime == "application/pdf" or clean_b64.startswith("JVBERi0"):  # %PDF-
            try:
                import io
                from pypdf import PdfReader
                pdf_bytes = base64.b64decode(clean_b64)
                reader = PdfReader(io.BytesIO(pdf_bytes))
                pdf_text_pages = [p.extract_text() for p in reader.pages if p.extract_text()]
                if pdf_text_pages:
                    extracted_pdf_text = "\n".join(pdf_text_pages)
                    text_content = (text_content + "\n" + extracted_pdf_text) if text_content else extracted_pdf_text
                    doc_b64 = None
            except Exception as e:
                pass
        elif mime.startswith("text/") or mime in ("application/json", "application/octet-stream"):
            try:
                decoded = base64.b64decode(clean_b64).decode("utf-8")
                if len(decoded.strip()) > 0 and "\x00" not in decoded[:100]:
                    text_content = (text_content + "\n" + decoded) if text_content else decoded
                    doc_b64 = None
            except Exception:
                pass

    # Privacy redaction before model invocation
    pii_redacted = False
    if text_content:
        text_content, pii_redacted = redact_sensitive_identifiers(text_content)

    # Narrow text extraction uses only explicit billing codes and labelled fields.
    if text_content and not doc_b64:
        card = analyze_insurance_card(text_content=text_content)
        code_matches = re.findall(r"\b(?:[A-Z]\d{4}|\d{5}|(?:DRUG|PROC|SVC)-[A-Z0-9]+)\b", text_content)
        items = [{"type": "drug" if code.startswith(("J", "DRUG-")) else "procedure" if code.isdigit() or code.startswith("PROC-") else "service",
                  "code": code, "name": code, "quantity": 1, "source_text": code} for code in dict.fromkeys(code_matches)]
        def field(pattern):
            match = re.search(pattern, text_content, re.I)
            return match.group(1).strip() if match else None
        service = field(r"(?:Service Date|Date of Service)\s*:\s*(\d{4}-\d{2}-\d{2})")
        return {**card, "patient_name": None, "specialty": field(r"Specialty\s*:\s*([^\n]+)") or "General Medicine",
                "service_date": service, "diagnosis_code": field(r"(?:Diagnosis|ICD-10)(?: Code)?\s*:\s*([A-Z]\d{2}(?:\.\d+)?)"),
                "diagnosis_desc": None, "items": items, "documents": [],
                "prior_approval_ref": field(r"(?:Prior Authorization|Prior Approval|PA)(?: Ref| Reference)?\s*:\s*([A-Z0-9-]+)"),
                "confidence": None, "pii_redacted": pii_redacted, "images_deidentified": False,
                "validation_warnings": (["No explicit billing code detected; reviewer code mapping is required."] if not items else []) +
                    (["Service date not specified in clinical note."] if not service else [])}

    parts = []
    if doc_b64:
        clean_b64, mime = extract_base64_and_mime(doc_b64)
        if mime.startswith("image/"):
            parts.append({"inlineData": {"mimeType": mime, "data": clean_b64}})

    prompt = (
        "Inspect this medical chart / clinical encounter / prescription note. "
        "Extract clinical details and payer coverage information into JSON with keys: "
        "patient_name, "
        "specialty ('Cardiology' | 'Oncology' | 'Orthopedics' | 'Neurology' | 'Gastroenterology' | 'Rheumatology'), "
        "service_date ('YYYY-MM-DD' or null if unstated), "
        "insurer_name (primary health insurance provider mentioned, or null), "
        "insurer_id ('uhc' | 'aetna' | 'bcbs' | 'cigna' | 'cms' | null), "
        "plan_name (e.g. 'Choice Plus PPO', or null), "
        "member_ref (member/subscriber ID if present, or null), "
        "group_number (group ID if present, or null), "
        "diagnosis_code (ICD-10 code like 'C34.90', 'E11.9', 'M17.11', 'M05.79' or null), "
        "diagnosis_desc, "
        "items (list of objects with: type ('drug' | 'procedure' | 'service'), "
        "code (e.g. 'KEYTRUDA', 'OZEMPIC', 'PROC-1', 'DRUG-A', 'HUMIRA'), name, quantity, source_text), "
        "documents (list of strings for attached docs like 'Genetics Panel Report', 'Pathology Report'), "
        "prior_approval_ref (prior auth authorization number if present, else null)."
    )
    if text_content:
        prompt += f"\n\nClinical Document Text:\n{text_content}"

    parts.append({"text": prompt})

    sys_instr = (
        "You are an expert clinical documentation specialist. "
        "Extract synthetic diagnosis, billing items, and attached paperwork. Absent fields must be null. Output strict JSON only. "
        "Do not invent drugs or codes if they do not appear in the source."
    )

    result = call_gemini_extraction(parts, sys_instr)
    if result:
        result["pii_redacted"] = pii_redacted
        result["confidence"] = None
        warnings = []
        if not result.get("items"):
            warnings.append("Could not detect specific prescribed drug or procedure. Please specify item before filing.")
            result["items"] = []
        if not result.get("service_date"):
            warnings.append("Service date not specified in clinical note.")
        result["validation_warnings"] = warnings
        return result

    # When no model or keywords match: do not invent a fake drug. Return clean unfilled schema with warning
    warnings = []
    if not text_content and not doc_b64:
        warnings.append("No clinical note or file uploaded.")
    else:
        warnings.append("Could not detect specific prescribed drug or procedure. Please specify item before filing.")

    return {
        "patient_name": "Clinical Patient",
        "specialty": "General Medicine",
        "service_date": None,
        "diagnosis_code": None,
        "diagnosis_desc": "Clinical documentation attached",
        "insurer_name": None,
        "insurer_id": None,
        "plan_name": None,
        "member_ref": None,
        "group_number": None,
        "items": [],
        "documents": [],
        "prior_approval_ref": None,
        "confidence": None,
        "pii_redacted": pii_redacted, "images_deidentified": False,
        "validation_warnings": warnings,
    }
