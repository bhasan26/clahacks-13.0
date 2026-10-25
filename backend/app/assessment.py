"""Compare assumed-valid prescription facts with retrieved policy requirements.

Results describe a policy test, never an insurer's live authorization decision.
"""
import re
from datetime import date


def diabetes_check(source: dict, prescription_text: str, card: dict) -> dict | None:
    criteria = source.get('criteria_excerpt', '')
    # Recognize the retrieved criteria, not a drug name or a cached assumed rule.
    normalized = re.sub(r'\s+', ' ', criteria)
    required = (
        r'Submission of medical records', r'diagnosis of type 2 diabetes',
        r'A1C greater than or equal to 6\.5%',
        r'Fasting plasma glucose.*?greater than or equal to 126 mg/dL',
        r'diagnosed greater than 2 years ago',
    )
    if not all(re.search(pattern, normalized, re.I) for pattern in required):
        return None
    if re.search(r'medicare|medicaid', card.get('plan_name') or '', re.I):
        return {'outcome': 'unknown', 'reason': 'This commercial policy does not establish the rules for the uploaded plan.'}
    # Inspect only stated diagnosis/indication fields, not disclaimers or policy text.
    diagnosis = re.search(r'(?im)^\s*(?:diagnosis|indication|ICD[- ]?10)\s*[:=]\s*([^\n]+)', prescription_text)
    diagnosis = diagnosis.group(1).strip() if diagnosis else ''
    compact = re.sub(r'\s+', '', diagnosis).casefold()
    type2 = bool(re.search(r'\bE11(?:\.|\b)', diagnosis, re.I) or 'type2diabetes' in compact or 'type2dm' in compact)
    negated = bool(re.search(r'(?:no|without|not)type2(?:diabetes|dm)', compact))
    if not diagnosis:
        return {'outcome': 'unknown', 'reason': 'Policy requires a type 2 diabetes diagnosis and qualifying clinical information.'}
    if negated or (not type2 and re.search(r'E10\b|type\s*1\s*(?:diabetes|dm)|obesity|weight\s*loss', diagnosis, re.I)):
        return {'outcome': 'not_matched', 'reason': f'Prescription diagnosis “{diagnosis}” does not meet this policy’s type 2 diabetes requirement.'}
    if not type2:
        return {'outcome': 'unknown', 'reason': 'The stated diagnosis does not confirm the policy’s type 2 diabetes requirement.'}
    # The recognized policy has alternative pathways. A single low test is not a
    # rejection because another qualifying test or ongoing-treatment pathway may apply.
    tests = [
        (r'(?im)^\s*(?:HbA1c|A1c)\s*[:=]\s*(\d+(?:\.\d+)?)\s*%', 6.5, 'A1C'),
        (r'(?im)^\s*(?:fasting (?:plasma )?glucose|FPG)\s*[:=]\s*(\d+(?:\.\d+)?)\s*mg/dL', 126, 'fasting glucose'),
        (r'(?im)^\s*(?:2[- ]hour (?:plasma )?glucose|2h PG)\s*[:=]\s*(\d+(?:\.\d+)?)\s*mg/dL', 200, '2-hour glucose'),
    ]
    for pattern, threshold, label in tests:
        match = re.search(pattern, prescription_text, re.I)
        if match and float(match.group(1)) >= threshold:
            return {'outcome': 'matched', 'reason': f'Type 2 diabetes and the stated {label} meet this policy’s clinical criteria.'}
    duration = re.search(r'(?im)^\s*(?:diabetes|diagnosis)\s*duration\s*[:=]\s*(\d+(?:\.\d+)?)\s*years?\b', prescription_text)
    if duration and float(duration.group(1)) > 2:
        return {'outcome': 'matched', 'reason': 'The stated type 2 diabetes history meets this policy’s ongoing-treatment criteria.'}
    return {'outcome': 'unknown', 'reason': 'Diagnosis matches. Policy also requires qualifying test results or a documented diabetes history longer than 2 years.'}


def assess_policies(card: dict, treatment: str, prescription_text: str, sources: list) -> list:
    findings = []
    for source in sources:
        outcome = None
        effective = source.get('effective_date')
        future = bool(effective and date.fromisoformat(effective) > date.today())
        if source.get('exclusion_verified'):
            outcome = {'outcome': 'upcoming' if future else 'not_matched', 'reason': f'This plan excludes {treatment} starting {effective}.'}
        elif source.get('coverage_verified') and not future:
            outcome = {'outcome': 'matched', 'reason': f'This plan’s policy lists {treatment} as covered.'}
        elif not future:
            outcome = diabetes_check(source, prescription_text, card)
        if outcome is None:
            outcome = {'outcome': 'unknown', 'reason': 'The retrieved information does not establish whether this prescription meets the policy.'}
        findings.append({
            **outcome, 'policy_title': source['title'], 'policy_id': source.get('policy_id'),
            'source_url': source['url'], 'effective_date': effective,
        })
    return findings
