"""
CoverageGuard Multimodal AI Policy Intelligence Module.
"""

from app.intelligence.document_processor import process_uploaded_document, DocumentProcessingError
from app.intelligence.policy_extractor import extract_policies_with_gemini
from app.intelligence.evidence_validator import validate_extracted_policy
from app.intelligence.policy_diff import compute_policy_diff
from app.intelligence.impact_previewer import preview_claim_impact

__all__ = [
    "process_uploaded_document",
    "DocumentProcessingError",
    "extract_policies_with_gemini",
    "validate_extracted_policy",
    "compute_policy_diff",
    "preview_claim_impact",
]
