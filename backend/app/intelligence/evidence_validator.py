"""
Evidence Validator for CoverageGuard Policy Intelligence.
Enforces strict quote verification against source document text:
- Requires the full normalized quotation to match source text.
- Rejects partial prefix matches from being marked as verified.
- Distinguishes machine-verified citations from unverified or visual evidence.
- Flags missing mandatory fields (insurer, code, effective date, coverage effect).
"""

import re
from typing import List, Dict, Any, Tuple, Optional


def normalize_text_for_search(text: str) -> str:
    """Collapses whitespace and lowercases text for exact quote comparison."""
    if not text:
        return ""
    # Replace line breaks and multiple spaces with a single space
    cleaned = re.sub(r"[\r\n\t]+", " ", text)
    cleaned = re.sub(r"\s+", " ", cleaned)
    # Remove smart quotes and dashes to plain ASCII
    cleaned = cleaned.replace("“", '"').replace("”", '"').replace("’", "'").replace("‘", "'")
    cleaned = cleaned.replace("—", "-").replace("–", "-")
    return cleaned.strip().lower()


def verify_evidence_in_document(
    quote: Optional[str],
    pages_text: List[Dict[str, Any]],
    raw_document_text: str,
    is_scanned_doc: bool = False,
) -> Tuple[bool, int, Optional[str], str]:
    """
    Checks if the FULL normalized quotation exists in the source text.
    Returns: (is_verified, page_number, verified_snippet, status_label)
    """
    if not quote or not quote.strip():
        return False, 1, None, "No evidence quote provided"

    clean_quote = normalize_text_for_search(quote)
    if len(clean_quote) < 8:
        return False, 1, None, "Quotation too short to verify"

    # If document has no selectable text (scanned PDF / photo image)
    if is_scanned_doc or not raw_document_text.strip():
        return False, 1, None, "Visual evidence — reviewer verification required"

    # 1. Exact match on individual pages (preserves verified page number)
    for page_entry in pages_text:
        p_num = page_entry.get("page", 1)
        p_text = normalize_text_for_search(page_entry.get("text", ""))
        if clean_quote in p_text:
            return True, p_num, quote.strip(), "Verified against source text"

    # 2. Exact match across full document text (e.g. quote spanned a line break)
    norm_doc = normalize_text_for_search(raw_document_text)
    if clean_quote in norm_doc:
        # Determine which page contains the majority of the quote
        for page_entry in pages_text:
            p_num = page_entry.get("page", 1)
            p_text = normalize_text_for_search(page_entry.get("text", ""))
            first_words = " ".join(clean_quote.split()[:5])
            if first_words and first_words in p_text:
                return True, p_num, quote.strip(), "Verified against source text"
        return True, 1, quote.strip(), "Verified against source text"

    # STRICT: Do not accept partial prefix matches as verified
    return False, 1, None, "Evidence not fully verified"


def validate_extracted_policy(
    proposal: Dict[str, Any],
    pages_text: List[Dict[str, Any]],
    raw_document_text: str,
    is_scanned_doc: bool = False,
) -> List[str]:
    """
    Validates extracted policy fields against source document and healthcare rules.
    Populates:
    - proposal['validation_warnings']: List[str]
    - proposal['missing_fields']: List[str]
    - proposal['is_complete']: bool
    - proposal['requires_code_mapping']: bool
    - proposal['source_page']: int
    """
    warnings: List[str] = []
    missing_fields: List[str] = []

    # 1. Evidence Quote Verification
    quote = proposal.get("supporting_quote")
    is_verified, found_page, _, status_label = verify_evidence_in_document(
        quote, pages_text, raw_document_text, is_scanned_doc=is_scanned_doc
    )

    if is_verified:
        proposal["source_page"] = found_page
    else:
        warnings.append(f"{status_label}.")

    # 2. Insurer Identity
    insurer_id = proposal.get("insurer_id")
    if not insurer_id or str(insurer_id).lower() in ["none", "unknown", ""]:
        missing_fields.append("insurer_id")
        warnings.append("Insurer identity not verified — reviewer must specify insurer before approval.")

    # 3. Target Item & Code Verification
    code = proposal.get("target_code")
    name = proposal.get("target_name")
    if not code or str(code).lower() in ["none", "unknown", "not verified", "item-unlisted", ""]:
        missing_fields.append("target_code")
        proposal["target_code"] = None
        if name:
            proposal["requires_code_mapping"] = True
            warnings.append(
                f"Target '{name}' has no verified standard billing code — human code mapping required before adjudication."
            )
        else:
            warnings.append("Target item code and name missing — reviewer must specify clinical item.")
    else:
        proposal["requires_code_mapping"] = False

    # 4. Effective Date Verification
    if not proposal.get("effective_from"):
        missing_fields.append("effective_from")
        warnings.append("Missing effective date — reviewer must set effective date before approval.")

    # 5. Proposed Coverage Effect
    effect = proposal.get("proposed_effect")
    if not effect or str(effect).lower() in ["none", "unknown", ""]:
        missing_fields.append("proposed_effect")
        warnings.append("Coverage effect unspecified (covered, excluded, or prior approval).")

    # 6. Plan Verification
    plans = proposal.get("plan_ids") or []
    if not plans:
        warnings.append("No insurance plan specified — requires confirmation of applicable plans.")

    # 7. Overall Completeness Check
    is_complete = len(missing_fields) == 0 and is_verified
    proposal["is_complete"] = is_complete
    proposal["missing_fields"] = missing_fields
    proposal["validation_warnings"] = warnings

    if not is_complete:
        proposal["review_state"] = "needs_correction"
    else:
        proposal["review_state"] = "pending_review"

    return warnings
