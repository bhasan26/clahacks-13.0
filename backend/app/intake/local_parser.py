"""Conservative local extraction of explicit synthetic claim labels, never benefit inference."""

import re
from datetime import datetime
from app.engine.matcher import normalize_insurer_id

INSURER_NAMES = {
    "uhc": "UnitedHealthcare",
    "aetna": "Aetna",
    "bcbs": "Blue Cross Blue Shield",
    "bcbs-anthem-ca": "Anthem Blue Cross California",
    "cms": "Original Medicare",
    "cigna": "Cigna",
    "demo-insurer": "Demo Insurance Co. (SIMULATED)",
}
LABELS = {
    "insurer_id": r"insurer[ _-]*id|payer[ _-]*id",
    "insurer_name": r"insurance company|primary insurer|insurance provider|insurer(?: name)?|payer(?: name)?",
    "plan_id": r"plan[ _-]*(?:id|identifier|number)|policy plan id",
    "plan_name": r"plan name|insurance plan",
    "member_ref": r"(?:member|subscriber)[ _-]*(?:id|ref(?:erence)?|number)|member|subscriber",
    "group_number": r"group(?:[ _-]*(?:number|id|no\.?))?",
    "jurisdiction": r"state|jurisdiction|service state",
    "service_date": r"service[ _-]*date|date of service|scheduled service date|encounter date",
    "prior_approval_ref": r"prior[ _-]*(?:authorization|approval)(?:[ _-]*(?:ref(?:erence)?|number|id))?|authorization(?: number| ref(?:erence)?| id)|pa(?: ref(?:erence)?| number)?",
    "patient_name": r"patient name",
    "specialty": r"specialty",
    "diagnosis_code": r"diagnosis code|icd[ -]?10(?: code)?",
    "diagnosis_desc": r"diagnosis(?: description)?",
    "documents": r"attached document(?:ation|s)?|documents",
    "procedure_name": r"procedure(?: name)?|treatment|requested service",
    "drug_name": r"drug name|medication(?: name)?",
    "cpt": r"cpt(?:[ _-]*code)?",
    "hcpcs": r"hcpcs(?:[ _-]*code)?",
    "ndc": r"ndc(?:[ _-]*code)?",
    "item_code": r"procedure[ _-]*code|drug[ _-]*code|item[ _-]*code|billing[ _-]*code|service[ _-]*code",
    "item_type": r"item[ _-]*type",
    "code_system": r"code[ _-]*system",
}
LABEL_RE = re.compile(
    r"(?<![\w])(?:"
    + "|".join(f"(?P<{key}>{value})" for key, value in LABELS.items())
    + r")[\t ]*(?::|=|#|\r?\n)[\t ]*(?:\r?\n[\t ]*)?",
    re.I,
)
EMPTY = {
    "",
    "unknown",
    "none",
    "n/a",
    "not provided",
    "not specified",
    "unavailable",
    "null",
    "blank",
}


def clean_value(value):
    value = value.strip(" \t\r\n•|;")
    return None if value.lower() in EMPTY else value


def normalize_date(value):
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y", "%B %d, %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(value.strip(), fmt).date().isoformat()
        except ValueError:
            continue
    return None


def parse_claim_text(text):
    text = text.replace("\r\n", "\n").replace("\u00a0", " ")
    matches = list(LABEL_RE.finditer(text))
    fields, records, warnings = {}, [], []
    for index, match in enumerate(matches):
        key = match.lastgroup
        tail = text[
            match.end() : matches[index + 1].start()
            if index + 1 < len(matches)
            else len(text)
        ]
        value = clean_value(re.split(r"[\n|;]", tail, maxsplit=1)[0])
        if key == "service_date" and normalize_date(value):
            value = normalize_date(value)
        records.append((key, value, match.start()))
        if key not in fields:
            fields[key] = value
        elif (
            value
            and fields[key] != value
            and key
            not in {
                "procedure_name",
                "drug_name",
                "cpt",
                "hcpcs",
                "ndc",
                "item_code",
                "item_type",
                "code_system",
            }
        ):
            warnings.append(
                f"Conflicting values for {key.replace('_', ' ')}; confirm this field manually."
            )
            fields[key] = None
    # Standalone payer branding is supported, without inferring a plan from the brand.
    explicit_id = fields.get("insurer_id")
    name = fields.get("insurer_name")
    identified = normalize_insurer_id(explicit_id or name)
    if name and not explicit_id and identified not in INSURER_NAMES:
        identified = next(
            (
                payer
                for pattern, payer in (
                    (r"\bunited\s*health\s*care\b|\buhc\b", "uhc"),
                    (r"\baetna\b", "aetna"),
                    (r"\banthem blue cross california\b", "bcbs-anthem-ca"),
                    (r"\bblue cross blue shield\b|\bbcbs\b", "bcbs"),
                    (r"\bmedicare\b", "cms"),
                )
                if re.search(pattern, name, re.I)
            ),
            identified,
        )
    if not explicit_id and not name:
        brands = set()
        for brand, payer in (
            (r"united\s*health\s*care|uhc", "uhc"),
            (r"aetna", "aetna"),
            (r"bcbs|blue cross blue shield", "bcbs"),
            (r"medicare", "cms"),
            (r"cigna", "cigna"),
        ):
            if re.search(r"(?im)^[ \t]*(?:" + brand + r")[ \t]*(?:$|[, (])", text):
                brands.add(payer)
        if len(brands) == 1:
            identified = brands.pop()
    fields["insurer_id"] = identified or None
    fields["insurer_name"] = name or INSURER_NAMES.get(identified)
    if fields.get("jurisdiction"):
        fields["jurisdiction"] = fields["jurisdiction"].upper()
    raw_date = fields.get("service_date")
    fields["service_date"] = normalize_date(raw_date)
    if raw_date and not fields["service_date"]:
        warnings.append(
            f"Invalid or ambiguous service date: {raw_date}. Enter YYYY-MM-DD."
        )
    auth = fields.get("prior_approval_ref")
    if auth and re.match(
        r"^(?:pending|not\b|none\b|no\b|missing\b|requested\b|unavailable\b)",
        auth,
        re.I,
    ):
        fields["prior_approval_ref"] = None
        warnings.append(
            "Prior authorization is pending or not supplied; no authorization reference was extracted."
        )

    items = []
    global_system = (fields.get("code_system") or "").upper() or None
    # Recognize explicit code labels/contexts only. Member IDs/NPI/ZIP numbers are not billing codes.
    code_records = [
        (key, value, pos)
        for key, value, pos in records
        if key in {"cpt", "hcpcs", "ndc", "item_code"} and value
    ]
    code_records += [
        (m.group(1).lower(), m.group(2), m.start())
        for m in re.finditer(
            r"\b(CPT|HCPCS|NDC|Procedure)\s+(?!Code\b)([A-Z]\d{4}|\d{5}|\d{4,5}-\d{3,4}-\d{1,2})\b",
            text,
            re.I,
        )
    ]
    for key, value, pos in sorted(code_records, key=lambda row: row[2]):
        code = re.match(r"[A-Z0-9][A-Z0-9.-]*", value.upper())
        if not code:
            continue
        code = code.group()
        system = key.upper() if key in {"cpt", "hcpcs", "ndc"} else global_system
        kind = (fields.get("item_type") or "").lower()
        if kind not in {"drug", "procedure", "service"}:
            kind = (
                "procedure"
                if system == "CPT" or key == "procedure"
                else "drug"
                if system == "NDC"
                or (system == "HCPCS" and code.startswith("J"))
                or fields.get("drug_name")
                else "procedure"
                if fields.get("procedure_name")
                else "service"
            )
        names = [
            (name, namepos)
            for label, name, namepos in records
            if label in {"procedure_name", "drug_name"} and name and namepos <= pos
        ]
        name = (
            names[-1][0]
            if names
            else fields.get("procedure_name") or fields.get("drug_name")
        )
        if not any(i["code"] == code and i["code_system"] == system for i in items):
            items.append(
                {
                    "type": kind,
                    "code": code,
                    "code_system": system,
                    "name": name or code,
                    "quantity": 1,
                }
            )
    if not items and (fields.get("procedure_name") or fields.get("drug_name")):
        items = [
            {
                "type": "procedure" if fields.get("procedure_name") else "drug",
                "code": "",
                "code_system": global_system,
                "name": fields.get("procedure_name") or fields["drug_name"],
                "quantity": 1,
            }
        ]
    documents = re.split(r",|\s*\|\s*", fields.get("documents") or "")
    return {
        **fields,
        "items": items,
        "documents": [d.strip() for d in documents if clean_value(d)],
        "confidence": None,
        "validation_warnings": warnings,
        "extraction_method": "local_structured_text",
    }


def infer_policy_environment(plan_id):
    """Simulated insurer plans are namespaced DEMO-*; every other plan requires official evidence."""
    return "demo" if (plan_id or "").strip().upper().startswith("DEMO-") else "official"


def claim_missing_fields(case):
    """Fields required by this explicit, scoped patient intake workflow."""
    labels = {
        "insurer_id": "Insurer ID",
        "plan_id": "Exact plan ID",
        "member_ref": "Member ID",
        "jurisdiction": "State / jurisdiction",
        "service_date": "Service date",
    }
    missing = [
        {
            "field": key,
            "message": f"{label} is missing. Enter the value from the claim or insurance details.",
        }
        for key, label in labels.items()
        if not getattr(case, key)
    ]
    if not case.items:
        missing.append(
            {
                "field": "items",
                "message": "No procedure, medication or service was recognized. Add the requested item and billing code.",
            }
        )
    for index, item in enumerate(case.items):
        for key, label in [
            ("code", "Billing code"),
            ("code_system", "Code system"),
            ("type", "Item type"),
        ]:
            if not getattr(item, key):
                missing.append(
                    {
                        "field": f"items.{index}.{key}",
                        "message": f"{label} is missing for {item.name or 'requested item'}. Enter it explicitly; no code is inferred from a procedure name.",
                    }
                )
    return missing
