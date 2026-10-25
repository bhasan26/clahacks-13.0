"""
Local-only synthetic clinical intake.
Selectable text is parsed locally; scanned images require manual structured entry.
Clinical files, member references and identifiers are never sent to external AI.
"""

import re
import base64
from typing import Optional, Dict, Any, List


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
            if mime not in {
                "application/pdf",
                "image/png",
                "image/jpeg",
                "image/webp",
                "text/plain",
            }:
                raise ValueError("Unsupported intake file type.")
            return clean, mime
    # Default to image/jpeg if raw base64
    decoded = base64.b64decode(data_uri_or_b64, validate=True)
    if len(decoded) > 10 * 1024 * 1024:
        raise ValueError("Uploaded file exceeds 10 MB limit.")
    return data_uri_or_b64, "application/pdf" if decoded.startswith(
        b"%PDF-"
    ) else "image/jpeg"


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


def _local_document_text(encoded=None, text_content=None):
    from app.intelligence.document_processor import process_uploaded_document

    warnings = []
    text = text_content or ""
    if encoded:
        clean, mime = extract_base64_and_mime(encoded)
        document = process_uploaded_document(
            base64.b64decode(clean), "patient-intake", mime
        )
        extracted = document["raw_text"].strip()
        text = "\n".join(part for part in (text, extracted) if part)
        warnings.extend(document.get("warnings", []))
        if document["file_type"] in {"png", "jpeg", "webp"} or any(
            page.get("is_scanned") for page in document["pages"]
        ):
            warnings.append(
                "Scanned image text was not read: local OCR is unavailable. Enter or paste the missing details manually; no image was sent to external AI."
            )
    return text, warnings


def analyze_insurance_card(image_b64=None, text_content=None):
    from app.intake.local_parser import parse_claim_text

    text, warnings = _local_document_text(image_b64, text_content)
    result = parse_claim_text(text)
    result["validation_warnings"].extend(warnings)
    return result


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


def analyze_clinical_document(doc_b64=None, text_content=None):
    """Parse selectable PDF/typed text locally; images remain manual entry without OCR."""
    from app.intake.local_parser import parse_claim_text

    text, warnings = _local_document_text(doc_b64, text_content)
    result = parse_claim_text(text)
    result["validation_warnings"].extend(warnings)
    if not result["items"]:
        result["validation_warnings"].append("No procedure, medication or billing code was recognized. Enter the requested item manually.")
    result.update(pii_redacted=False, images_deidentified=False)
    return result
