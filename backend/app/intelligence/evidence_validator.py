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
    # Ground identifiers and dates independently of quote matching. A genuine
    # quotation does not prove that other structured fields were present.
    from datetime import date
    from app.engine.matcher import INSURER_ALIASES, normalize_insurer_id
    corpus = normalize_text_for_search(raw_document_text + " " + " ".join(p.get("text", "") for p in pages_text))
    meaningful_text = re.sub(r"---\s*\[Page \d+\]\s*---", "", corpus, flags=re.I).strip()
    visual_only = not meaningful_text or (pages_text and all(p.get("is_scanned") and len(p.get("text", "").strip()) < 40 for p in pages_text))
    def contains(value):
        return visual_only or bool(value and re.search(r"(?<![\w-])" + re.escape(str(value).lower()) + r"(?![\w-])", corpus))
    insurer = proposal.get("insurer_id")
    if insurer:
        aliases = INSURER_ALIASES.get(normalize_insurer_id(insurer), {insurer})
        if not any(contains(alias) for alias in aliases):
            proposal["insurer_id"] = None
            warnings.append("Extracted insurer does not occur in source text; reviewer clarification required.")
    code = proposal.get("target_code")
    if code and not contains(code):
        proposal["target_code"] = None
        warnings.append("Extracted billing code does not occur exactly in source text.")
    plans = proposal.get("plan_ids") or []
    if not visual_only and any((plan == "*" and not re.search(r"\ball (?:insurance |benefit )?plans\b", corpus)) or
           (plan != "*" and not contains(plan)) for plan in plans):
        proposal["plan_ids"] = []
        warnings.append("Extracted plan scope is unsupported by source text; reviewer confirmation required.")
    effective = proposal.get("effective_from")
    if isinstance(effective, date) and not visual_only:
        alternatives = [effective.isoformat(), effective.strftime("%m/%d/%Y"),
                        effective.strftime("%B %-d, %Y"), effective.strftime("%B %-d %Y"),
                        effective.strftime("%b %-d, %Y"), effective.strftime("%d %B %Y")]
        if not any(normalize_text_for_search(value) in corpus for value in alternatives):
            proposal["effective_from"] = None
            warnings.append("Extracted effective date is not stated in supported source text date formats.")
    quote = proposal.get("supporting_quote")
    effect = proposal.get("proposed_effect")
    effect_value = getattr(effect, "value", effect)
    evidence_text = normalize_text_for_search(quote or "")
    effect_patterns = {"excluded": r"exclu|not cover|no longer cover|non.cover|will not cover",
                       "requires_prior_approval": r"prior auth|prior approval|pre.authoriz|requires pa\b",
                       "requires_documents": r"document|report|record|attachment",
                       "covered": r"\bcovered\b|will cover|covers\b"}
    if effect_value in effect_patterns and not visual_only:
        if not re.search(effect_patterns[effect_value], evidence_text) or (effect_value == "covered" and re.search(effect_patterns["excluded"], evidence_text)):
            proposal["proposed_effect"] = None
            warnings.append("Coverage effect is not supported by the quoted source statement.")
    is_verified, found_page, _, status_label = verify_evidence_in_document(
        quote, pages_text, raw_document_text, is_scanned_doc=is_scanned_doc
    )

    if is_verified:
        proposal["source_page"] = found_page
    else:
        warnings.append(f"{status_label}.")
    proposal["evidence_verified"] = is_verified

    # 2. Insurer Identity
    insurer_id = proposal.get("insurer_id")
    if not insurer_id or str(insurer_id).lower() in ["none", "unknown", "", "*"]:
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
        missing_fields.append("plan_ids")
        warnings.append("No insurance plan specified — requires confirmation of applicable plans.")
    if not proposal.get("target_type"):
        missing_fields.append("target_type")
        warnings.append("Target type unspecified — reviewer must identify drug, procedure, or service.")

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
