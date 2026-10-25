"""
Policy Extractor for CoverageGuard Multimodal Policy Intelligence.
Invokes Gemini multimodal models to extract proposed policy rules from
scanned documents, images, and text letters into structured ProposedPolicyChange models.
"""

import os
import re
import json
import uuid
from datetime import datetime, date
from typing import Dict, Any, List, Optional, Tuple
import httpx

from app.domain.models import ProposedPolicyChange, RuleEffect, utc_now
from app.intelligence.evidence_validator import validate_extracted_policy


def get_gemini_api_key() -> Optional[str]:
    """Retrieves GEMINI_API_KEY from environment or .env files."""
    if os.environ.get("COVERAGEGUARD_DISABLE_AI") == "true":
        return None
    key = os.environ.get("GEMINI_API_KEY")
    if key and key.strip():
        return key.strip().strip('"').strip("'")

    env_paths = [
        os.path.join(os.path.dirname(__file__), "..", "..", ".env"),
        os.path.join(os.getcwd(), "backend", ".env"),
        os.path.join(os.getcwd(), ".env"),
    ]
    for p in env_paths:
        if os.path.exists(p):
            try:
                content = open(p).read()
                for line in content.splitlines():
                    if line.startswith("GEMINI_API_KEY="):
                        k = line.split("=", 1)[1].strip().strip('"').strip("'")
                        if k:
                            return k
            except Exception:
                pass
    return None


def gemini_endpoint() -> str:
    model = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")
    if not re.fullmatch(r"[A-Za-z0-9.-]+", model):
        raise ValueError("Invalid GEMINI_MODEL identifier.")
    return f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


SYSTEM_PROMPT = """You are CoverageGuard Policy Intelligence Engine.
Your job is to read an insurance policy notice, letter, or circular, and extract PROPOSED coverage rule changes into a strict JSON object with a "policy_changes" array.

CRITICAL HEALTHCARE ADJUDICATION RULES:
1. AI extracts. Code decides. Humans approve.
2. Extract ONLY what is explicitly written in the document. NEVER invent codes, effective dates, insurers, or policy references.
3. If a billing code is NOT mentioned in the text (e.g. a drug like 'Ozempic' is named but no HCPCS/CPT code is given), set target_code to null.
4. If an effective date is NOT explicitly stated in the document, set effective_from to null. NEVER guess an effective date.
5. If the insurer name or ID is NOT stated in the document, set insurer_id to null and insurer_name to null.
6. If a specific insurance plan is not explicitly stated, return an empty array [] for plan_ids. DO NOT assume wildcard ["*"] unless the document explicitly states all plans.
7. For each policy change in "policy_changes", return:
   - insurer_id: string (e.g. 'uhc', 'aetna', 'bcbs', 'cms') or null
   - insurer_name: string (e.g. 'UnitedHealthcare', 'Aetna Health', 'Blue Cross Blue Shield', 'CMS Medicare') or null
   - plan_ids: array of string plan IDs (e.g. ["PLAN-GOLD"]) or [] if unspecified
   - policy_title: descriptive title of the policy or null
   - policy_reference: official circular / bulletin ID or null
   - target_type: 'drug' | 'procedure' | 'service' or null
   - target_code: standard billing code or reference (e.g. 'J9271', 'DRUG-A', 'PROC-1') or null if not verified
   - target_name: commercial or generic name (e.g. 'Ozempic', 'Keytruda', 'Drug A') or null
   - previous_effect: 'covered' | 'excluded' | null
   - proposed_effect: 'covered' | 'excluded' | 'requires_prior_approval' | 'requires_documents' or null
   - effective_from: ISO YYYY-MM-DD or null
   - effective_to: ISO YYYY-MM-DD or null
   - change_type: 'new_rule' | 'modification' | 'delayed' | 'cancelled'
   - conditions: object with required criteria or null (e.g. {"requires_prior_approval": true, "required_documents": ["Genetics Panel Report"]})
   - supporting_quote: EXACT verbatim quotation from the document text
   - source_page: integer page number (1-indexed) where the quotation appears
8. If the document postpones or delays an earlier exclusion (e.g. 'Effective date delayed from Nov 1 to Dec 1'), set change_type='delayed', effective_from='YYYY-MM-DD'.
9. If multiple rule changes are announced, extract each change separately.
"""


def _deduplicate_proposals(proposals: List[ProposedPolicyChange]) -> List[ProposedPolicyChange]:
    """Deduplicates extracted proposals across document pages."""
    seen = set()
    deduped: List[ProposedPolicyChange] = []
    for p in proposals:
        key = (
            (p.insurer_id or "").lower(),
            (p.target_code or p.target_name or "").upper(),
            p.proposed_effect.value if p.proposed_effect else "",
            str(p.effective_from) if p.effective_from else "",
            tuple(sorted(p.plan_ids)), p.target_type, p.change_type,
        )
        if key not in seen:
            seen.add(key)
            deduped.append(p)
    return deduped


def extract_policies_with_gemini(
    document_data: Dict[str, Any],
) -> Tuple[List[ProposedPolicyChange], bool, Optional[str]]:
    """
    Executes multimodal policy extraction via Gemini.
    Passes all document pages with text and scanned page images.
    Returns: (proposals, used_live_ai, error_message)
    """
    api_key = get_gemini_api_key()
    raw_text = document_data.get("raw_text", "").strip()
    primary_image_b64 = document_data.get("primary_image_b64")
    primary_mime = document_data.get("primary_mime")
    scanned_page_images = document_data.get("scanned_page_images", [])
    filename = document_data.get("filename", "policy_document.pdf")
    doc_id = document_data.get("document_id", f"DOC-{uuid.uuid4().hex[:6].upper()}")
    pages = document_data.get("pages", [])

    if not api_key:
        fallback_proposals = _deterministic_fallback_extractor(document_data)
        for p in fallback_proposals:
            p.validation_warnings.append("Gemini API key not configured — extracted via deterministic parser.")
        return fallback_proposals, False, "GEMINI_API_KEY is not configured. Deterministic parser applied."

    parts: List[Dict[str, Any]] = []

    # Attach up to 5 scanned page images for multimodal extraction
    if scanned_page_images:
        for s_img in scanned_page_images[:5]:
            parts.append({
                "inlineData": {
                    "mimeType": s_img.get("mime", "image/png"),
                    "data": s_img.get("b64"),
                }
            })
    elif primary_image_b64 and primary_mime:
        parts.append({
            "inlineData": {
                "mimeType": primary_mime,
                "data": primary_image_b64,
            }
        })

    prompt_content = (
        f"Filename: {filename}\n"
        f"Document Content by Page:\n{raw_text}\n\n"
        "Analyze ALL pages of the document above. Extract all proposed policy changes in strict JSON format. "
        "Make sure to identify the correct source_page for each rule."
    )
    parts.append({"text": prompt_content})

    url = gemini_endpoint()
    payload = {
        "contents": [{"parts": parts}],
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "generationConfig": {"responseMimeType": "application/json"},
    }

    failure_reason = "AI service temporarily unavailable."
    try:
        with httpx.Client(timeout=float(os.environ.get("GEMINI_TIMEOUT_SECONDS", "60"))) as client:
            resp = client.post(url, json=payload, headers={"x-goog-api-key": api_key})
            if resp.status_code == 200:
                raw_json = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
                parsed = json.loads(raw_json)
                changes = parsed if isinstance(parsed, list) else parsed.get("policy_changes", [])

                proposals = []
                for item in changes:
                    proposal = _map_dict_to_proposal(item, doc_id, filename, pages, raw_text)
                    proposal.extraction_method = "gemini"
                    proposal.is_synthetic = "synthetic" in raw_text.lower()
                    proposal.source_url = document_data.get("source_url")
                    proposals.append(proposal)

                deduped = _deduplicate_proposals(proposals)
                if deduped:
                    return deduped, True, None
            else:
                failure_reason = f"Gemini returned HTTP {resp.status_code}. Check the configured model and API access."
    except Exception as exc:
        failure_reason = f"Gemini extraction failed ({type(exc).__name__})."

    # Fallback to deterministic extraction if Gemini fails or times out
    fallback_proposals = _deterministic_fallback_extractor(document_data)
    for p in fallback_proposals:
        p.validation_warnings.append("AI service temporarily unavailable — extracted via deterministic fallback.")
    return _deduplicate_proposals(fallback_proposals), False, f"{failure_reason} Deterministic fallback applied."


def _parse_iso_date(val: Any) -> Optional[date]:
    if not val:
        return None
    val_str = str(val).strip()
    try:
        return datetime.strptime(val_str, "%Y-%m-%d").date()
    except Exception:
        pass
    for fmt in ["%B %d, %Y", "%b %d, %Y", "%d %b %Y", "%d %B %Y", "%m/%d/%Y", "%m-%d-%Y"]:
        try:
            return datetime.strptime(val_str, fmt).date()
        except Exception:
            continue
    return None


def _map_dict_to_proposal(
    item: Dict[str, Any],
    doc_id: str,
    filename: str,
    pages: List[Dict[str, Any]],
    raw_text: str,
) -> ProposedPolicyChange:
    """Maps extracted dictionary into ProposedPolicyChange and validates evidence."""
    eff_date = _parse_iso_date(item.get("effective_from"))
    eff_to = _parse_iso_date(item.get("effective_to"))

    try:
        effect = RuleEffect(item.get("proposed_effect"))
    except (ValueError, TypeError):
        effect = None

    ch_type = item.get("change_type", "new_rule")
    if ch_type not in ["new_rule", "modification", "delayed", "cancelled"]:
        ch_type = "new_rule"

    quote = item.get("supporting_quote") or ""
    page_num = item.get("source_page", 1)
    try:
        page_num = int(page_num)
    except Exception:
        page_num = 1

    # Extract clean insurer and target fields WITHOUT fabricated defaults
    raw_ins = item.get("insurer_id")
    insurer_id = str(raw_ins).strip().lower() if raw_ins and str(raw_ins).strip() and str(raw_ins).strip().lower() not in ["null", "none", "unknown"] else None

    raw_code = item.get("target_code")
    target_code = str(raw_code).strip() if raw_code and str(raw_code).strip() and str(raw_code).strip().lower() not in ["null", "none", "unknown", "not verified", "n/a"] else None

    raw_name = item.get("target_name")
    target_name = str(raw_name).strip() if raw_name and str(raw_name).strip() and str(raw_name).strip().lower() not in ["null", "none"] else None

    plan_ids_val = item.get("plan_ids")
    if isinstance(plan_ids_val, list):
        plan_ids = [str(p).strip() for p in plan_ids_val if str(p).strip()]
    elif isinstance(plan_ids_val, str) and plan_ids_val.strip() and plan_ids_val.strip() != "*":
        plan_ids = [plan_ids_val.strip()]
    else:
        plan_ids = []

    policy_ref = item.get("policy_reference")
    if policy_ref and str(policy_ref).strip() and str(policy_ref).strip().lower() not in ["null", "none"]:
        policy_reference = str(policy_ref).strip()
    else:
        policy_reference = None

    proposal_data: Dict[str, Any] = {
        "proposal_id": f"PROP-{uuid.uuid4().hex[:6].upper()}",
        "document_id": doc_id,
        "document_name": filename,
        "insurer_id": insurer_id,
        "insurer_name": item.get("insurer_name") or (insurer_id.upper() if insurer_id else None),
        "plan_ids": plan_ids,
        "policy_title": item.get("policy_title") or f"Policy Notice ({filename})",
        "policy_reference": policy_reference,
        "target_type": item.get("target_type"),
        "target_code": target_code,
        "target_name": target_name or (target_code if target_code else "Unverified Item"),
        "previous_effect": item.get("previous_effect"),
        "proposed_effect": effect,
        "effective_from": eff_date,
        "effective_to": eff_to,
        "change_type": ch_type,
        "conditions": item.get("conditions"),
        "supporting_quote": quote,
        "source_page": page_num,
        "confidence": item.get("confidence"),
        "validation_warnings": [],
        "review_state": "pending_review",
        "created_at": utc_now(),
    }

    # Validate evidence quote against document and detect missing mandatory fields
    warnings = validate_extracted_policy(proposal_data, pages, raw_text)
    proposal_data["validation_warnings"] = warnings

    return ProposedPolicyChange(**proposal_data)


def _deterministic_fallback_extractor(document_data: Dict[str, Any]) -> List[ProposedPolicyChange]:
    """Conservative text-only assistance. Every value must occur in this document.

    No drug-name-to-billing-code mapping or implied payer/plan/date. This parser
    intentionally produces incomplete proposals for ambiguous unfamiliar notices.
    """
    raw = document_data.get("raw_text", "")
    if not raw.strip() or not re.search(r"policy|cover|exclu|prior auth|formulary|insurer|medicare", raw, re.I):
        return []
    insurer = None
    insurer_name = None
    identities = [
        ("demo-insurer", "Demo Insurance Co.", r"demo insurance co\.?|demo-insurer"),
        ("uhc", "UnitedHealthcare", r"unitedhealthcare|\buhc\b"),
        ("aetna", "Aetna", r"\baetna\b"),
        ("bcbs", "Blue Cross Blue Shield", r"blue cross blue shield|\bbcbs\b"),
        ("cigna", "Cigna", r"\bcigna\b"),
        ("cms", "CMS Medicare", r"\bcms\b|\bmedicare\b|centers for medicare & medicaid services"),
    ]
    found = [(i, n) for i, n, pattern in identities if re.search(pattern, raw, re.I)]
    if len(found) == 1:
        insurer, insurer_name = found[0]
    plans = list(dict.fromkeys(re.findall(r"\bPLAN-[A-Z0-9-]+\b", raw, re.I)))
    if not plans and re.search(r"\ball (?:insurance |benefit )?plans\b", raw, re.I):
        plans = ["*"]
    code_pattern = r"\b(?:[A-Z]\d{4}|\d{5}|(?:DRUG|PROC|SVC)-[A-Z0-9]+|BIO-TARGET)\b"
    codes = list(dict.fromkeys(re.findall(code_pattern, raw)))
    names = [name for name in ("Ozempic", "Keytruda", "Semaglutide", "Humira", "Adalimumab") if re.search(r"\b"+name+r"\b", raw, re.I)]
    # Code-free notices still need an explicit reviewer code mapping.
    targets = codes or [None]
    dates = r"(?:\d{4}-\d{2}-\d{2}|(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4})"
    sentences = [x.strip() for x in re.split(r"(?<=[.!?])\s+|\n", raw) if x.strip()]
    proposals = []
    for code in targets:
        related = [line for line in sentences if (not code or re.search(r"(?<![A-Z0-9-])"+re.escape(code)+r"(?![A-Z0-9-])", line, re.I))]
        actions = [line for line in related if re.search(r"cover|exclu|prior auth|require|postpon|delay|cancel", line, re.I)]
        # Prefer an operative dated sentence over a subject/title mentioning exclusion.
        quote = max(actions, key=lambda line: (bool(re.search(dates, line, re.I)),
                    bool(re.search(r"postponed|delayed until|cancelled|will no longer|is excluded|requires", line, re.I)))) if actions else (related[0] if related else raw.strip())
        context = quote.lower()
        effect = None
        if re.search(r"exclu|no longer cover|not cover|non.cover", context):
            effect = "excluded"
        elif re.search(r"prior auth|prior approval", context):
            effect = "requires_prior_approval"
        elif re.search(r"require.*document", context):
            effect = "requires_documents"
        elif re.search(r"\bcover(?:ed|age)?\b", context):
            effect = "covered" if re.search(r"\b(?:is|are|remain|will be) covered\b", context) else None
        change = "cancelled" if re.search(r"cancel|withdraw|rescind", context) else "delayed" if re.search(r"postpon|delay", context) else "new_rule"
        explicit_dates = re.findall(dates, quote, re.I)
        if explicit_dates:
            effective = explicit_dates[-1] if change == "delayed" else explicit_dates[0]
        else:
            labelled = re.search(r"(?:New Delayed Effective Date|Effective Date|Effective from|Effective)\s*[: ]\s*("+dates+r")", raw, re.I)
            effective = labelled.group(1) if labelled else None
        target_type = None
        if code and (code.startswith("DRUG-") or code.startswith("J") or code == "BIO-TARGET") or names:
            target_type = "drug"
        elif code and (code.startswith("PROC-") or code.isdigit()):
            target_type = "procedure"
        elif code and code.startswith("SVC-"):
            target_type = "service"
        title = next((line.strip().lstrip("# ") for line in raw.splitlines() if line.strip() and not line.startswith("--- [Page")), None)
        item = dict(insurer_id=insurer, insurer_name=insurer_name, plan_ids=plans,
                    target_type=target_type, target_code=code, target_name=names[0] if names else code,
                    proposed_effect=effect, effective_from=effective, supporting_quote=quote,
                    change_type=change, policy_title=title)
        p = _map_dict_to_proposal(item, document_data.get("document_id", "DOC-TEXT"), document_data.get("filename", "notice.txt"), document_data.get("pages", []), raw)
        p.extraction_method = "deterministic"
        p.is_synthetic = "synthetic" in raw.lower()
        p.source_url = document_data.get("source_url")
        p.validation_warnings.append("Conservative text parser; reviewer must verify every field against the original document.")
        proposals.append(p)
    return _deduplicate_proposals(proposals)
