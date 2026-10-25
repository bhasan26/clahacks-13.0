"""Bounded public-policy retrieval. Coverage claims require an exact source excerpt."""
import asyncio
import re
import time
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import PurePosixPath
from urllib.parse import urlparse

import httpx
import pymupdf
from bs4 import BeautifulSoup

from app.documents import INSURERS, search_treatment

_cache: dict[tuple, tuple] = {}
MAX_SOURCE_BYTES = 3 * 1024 * 1024


def official_domains(insurer: str) -> tuple:
    for name, (pattern, domains) in INSURERS.items():
        if name.lower() == insurer.lower() or re.search(pattern, insurer, re.I):
            return domains
    return ()


def safe_source(url: str, domains: tuple) -> bool:
    try:
        parsed = urlparse(url)
        if parsed.port not in (None, 443):
            return False
    except ValueError:
        return False
    return parsed.scheme == 'https' and not parsed.username and parsed.port in (None, 443) and any(parsed.hostname == d or (parsed.hostname or '').endswith('.' + d) for d in domains)


def source_date(text: str) -> str | None:
    # Only an explicit effective date, never a publication date or a generated date.
    match = re.search(r'(?i)\b(?:effective(?:\s+(?:date|from|on))?|starting|beginning|as of)\s*[:\-]?\s*((?:20\d{2}-\d{2}-\d{2})|(?:\d{1,2}/\d{1,2}/20\d{2})|(?:[A-Za-z]{3,9}\.?\s+\d{1,2},?\s+20\d{2}))', text)
    if not match:
        return None
    from datetime import datetime
    raw = match.group(1).replace('.', '').replace(',', '')
    for fmt in ('%Y-%m-%d', '%m/%d/%Y', '%B %d %Y', '%b %d %Y'):
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def evidence_from_text(url: str, text: str, insurer: str, treatment: str, plan_id: str | None, title: str = '') -> dict | None:
    if not safe_source(url, official_domains(insurer)):
        return None
    # Keep source text intact: don't let search snippets or model output become evidence.
    term = search_treatment(treatment)
    pattern = re.escape(term).replace(r'\ ', r'\s+')
    lines = [re.sub(r'\s+', ' ', line).strip() for line in text.splitlines() if line.strip()]
    section = re.search(r'\b2\.\s*Coverage Criteria.*?(?=\b3\.\s*Additional Clinical Programs|$)', text, re.I | re.S)
    criteria = re.sub(r'\s+', ' ', section.group(0)).strip() if section else ''
    policy_id = re.search(r'Program Number\s+([0-9]{4}\s+P\s+[0-9-]+)', text, re.I)
    candidates = []
    for line in lines:
        if not term or not re.search(rf'(?i)(?<!\w){pattern}(?!\w)', line) or len(line) > 700:
            continue
        effective = source_date(line) or source_date(text[:2000])
        # A simple, unconditional plan statement is safe to compare automatically.
        # A general drug mention or a conditional statement never establishes acceptance.
        plan_prefix = rf'(?:Plan(?: ID)?[ :#-]+)?{re.escape(plan_id)}[: ,;–—-]+' if plan_id else r'(?!)'
        date_suffix = r'(?:20\d{2}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/20\d{2}|[A-Za-z]{3,9}\.?\s+\d{1,2},?\s+20\d{2})\.?'
        rule_prefix = rf'(?i){plan_prefix}{pattern}[®™]?\s+'
        exclusion = bool(effective and re.fullmatch(
            rule_prefix + r'(?:will no longer be covered|is no longer covered|is excluded from coverage)\s+'
            r'(?:starting|effective(?: from| on)?|beginning)\s+' + date_suffix, line,
        ))
        coverage = bool(effective and re.fullmatch(
            rule_prefix + r'is covered\s+(?:starting|effective(?: from| on)?|beginning)\s+' + date_suffix, line,
        ))
        candidates.append({
            'url': url, 'title': title[:200] or 'Insurance policy', 'insurer_name': insurer,
            'treatment_name': treatment, 'effective_date': effective,
            'excerpt': line, 'exclusion_verified': exclusion, 'coverage_verified': coverage,
            'criteria_excerpt': criteria[:5000],
            'policy_id': policy_id.group(1) if policy_id else None,
            'checked_at': date.today().isoformat(),
        })
    if not candidates:
        return None
    source = next((candidate for candidate in candidates if candidate['exclusion_verified'] or candidate['coverage_verified']), candidates[0])
    if criteria and not (source['exclusion_verified'] or source['coverage_verified']):
        source['excerpt'] = criteria[:1200] + ('…' if len(criteria) > 1200 else '')
    return source


async def fetch_source(client: httpx.AsyncClient, url: str, domains: tuple) -> tuple[str, str, str] | None:
    # Revalidate every redirect; never fetch arbitrary URLs from uploads.
    for _ in range(3):
        if not safe_source(url, domains):
            return None
        try:
            async with client.stream('GET', url) as response:
                if response.is_redirect:
                    from urllib.parse import urljoin
                    url = urljoin(url, response.headers.get('location', ''))
                    continue
                response.raise_for_status()
                parts, size = [], 0
                async for part in response.aiter_bytes():
                    size += len(part)
                    if size > MAX_SOURCE_BYTES:
                        return None
                    parts.append(part)
                body = b''.join(parts)
                if body.startswith(b'%PDF'):
                    with pymupdf.open(stream=body, filetype='pdf') as doc:
                        return url, '\n'.join(p.get_text() for p in list(doc)[:25]), doc.metadata.get('title') or PurePosixPath(urlparse(url).path).stem.replace('-', ' ')
                soup = BeautifulSoup(body, 'html.parser')
                for el in soup(['script', 'style', 'nav', 'footer']):
                    el.decompose()
                return url, soup.get_text('\n', strip=True), soup.title.get_text(strip=True) if soup.title else 'Insurance policy'
        except (httpx.HTTPError, ValueError, RuntimeError):
            return None
    return None


async def lookup_policies(insurer: str, treatment: str, plan_id: str | None) -> tuple[list, str]:
    key = (insurer, treatment, plan_id)
    cached = _cache.get(key)
    if cached and time.monotonic() - cached[0] < 900:
        return cached[1], cached[2]
    domains = official_domains(insurer)
    if not domains:
        return [], 'No verified public source found for this insurer.'
    sources = []
    status = 'No matching policy could be verified.'
    try:
        async with asyncio.timeout(7):
            async with httpx.AsyncClient(timeout=2.5, follow_redirects=False, headers={'User-Agent': 'CoverageGuard/3.0 public-policy-reader'}) as client:
                query = f'{insurer} {search_treatment(treatment)} coverage policy effective site:{domains[0]}'
                urls = []
                # A stable official policy is a retrieval fallback, never a seeded decision.
                if 'uhcprovider.com' in domains and re.search(r'(?i)\b(?:Ozempic|Mounjaro|Rybelsus|Trulicity|Victoza|Byetta|Bydureon)\b', treatment):
                    urls.append('https://www.uhcprovider.com/content/dam/provider/docs/public/prior-auth/drugs-pharmacy/commercial/a-g/PA-Notification-Diabetes-Agents-GLP1-Receptor-Agonists.pdf')
                try:
                    response = await client.get('https://www.bing.com/search', params={'q': query, 'format': 'rss'})
                    response.raise_for_status()
                    root = ET.fromstring(response.content[:300000])
                    for item in root.findall('.//item'):
                        url = item.findtext('link', '')
                        if safe_source(url, domains) and url not in urls:
                            urls.append(url)
                except (httpx.HTTPError, ET.ParseError):
                    status = 'Policy search unavailable. Coverage is not verified.'
                results = await asyncio.gather(*(fetch_source(client, url, domains) for url in urls[:3]), return_exceptions=True)
                for result in results:
                    if not isinstance(result, tuple):
                        continue
                    url, text, title = result
                    source = evidence_from_text(url, text, insurer, treatment, plan_id, title)
                    if source:
                        sources.append(source)
                if sources:
                    status = 'Public policy found. Patient-specific coverage is not confirmed.'
    except (TimeoutError, httpx.HTTPError, ET.ParseError, ValueError):
        status = 'Policy search unavailable. Coverage is not verified.'
    if len(_cache) >= 256:
        _cache.pop(next(iter(_cache)))
    _cache[key] = (time.monotonic(), sources, status)
    return sources, status
