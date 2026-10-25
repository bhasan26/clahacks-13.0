"""
Evidence Validator for CoverageGuard Policy Intelligence.
Verifies that model-extracted quotes actually appear in the source document.
Assigns validation warnings and identifies the source page and text span.
"""

import re
from typing import List, Dict, Any, Tuple, Optional


def normalize_text_for_search(text: str) -> str:
    """Collapses whitespace and lowercases text for fuzzy quote matching."""
    return re.sub(r"\s+", " ", text).strip().lower()


def verify_evidence_in_document(
    quote: Optional[str],
    pages_text: List[Dict[str, Any]],
    raw_document_text: str,
) -> Tuple[bool, int, Optional[str]]:
    """
    Checks if quote exists in the document text.
    Returns: (is_verified, page_number, verified_snippet)
    """
    if not quote or not quote.strip():
        return False, 1, None

    clean_quote = normalize_text_for_search(quote)
    if len(clean_quote) < 8:
        return False, 1, None

    # Check page by page first
    for page_entry in pages_text:
        p_num = page_entry.get("page", 1)
        p_text = normalize_text_for_search(page_entry.get("text", ""))
        if clean_quote in p_text:
            return True, p_num, quote.strip()

    # Check whole document
    norm_doc = normalize_text_for_search(raw_document_text)
    if clean_quote in norm_doc:
        return True, 1, quote.strip()

    # Fuzzy partial match (first 30 characters)
    short_quote = clean_quote[:40].strip()
    if len(short_quote) > 15:
        for page_entry in pages_text:
            p_num = page_entry.get("page", 1)
            p_text = normalize_text_for_search(page_entry.get("text", ""))
            if short_quote in p_text:
                return True, p_num, quote.strip()

    return False, 1, None


def validate_extracted_policy(
    proposal: Dict[str, Any],
    pages_text: List[Dict[str, Any]],
    raw_document_text: str,
) -> List[str]:
    """
    Validates extracted policy fields against source document and healthcare rules.
    Returns list of human-actionable warnings.
    """
    warnings: List[str] = []

    # 1. Evidence Verification
    quote = proposal.get("supporting_quote")
    is_verified, found_page, _ = verify_evidence_in_document(quote, pages_text, raw_document_text)
    if not is_verified:
        warnings.append("Supporting quotation not verified in source text — requires human review.")
    else:
        proposal["source_page"] = found_page

    # 2. Date Verification
    if not proposal.get("effective_from"):
        warnings.append("Missing effective date — reviewer must set effective date before approval.")

    # 3. Plan Verification
    plans = proposal.get("plan_ids") or []
    if not plans:
        warnings.append("No insurance plan specified — applies to all commercial plans (*) or requires verification.")

    # 4. Target Item & Code Verification
    code = proposal.get("target_code")
    name = proposal.get("target_name")
    if not code and not name:
        warnings.append("Missing target item code and name — reviewer must specify clinical target.")
    elif not code:
        warnings.append(f"Target '{name}' has no standard procedure/billing code — code needed for automated adjudication.")

    # 5. Proposed Effect
    effect = proposal.get("proposed_effect")
    if not effect:
        warnings.append("Coverage effect unspecified (covered, excluded, or prior_approval).")

    return warnings
