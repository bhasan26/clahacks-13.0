"""Read-only bounded HTTP for fixed official policy origins. No claim payload input."""

import re
import threading
import time
from urllib.parse import urlparse, urljoin
import httpx
from app.connectors.base import SourceError, SourceAccessError

USER_AGENT = (
    "CoverageGuard/2.0 (public insurance policy synchronization; no patient data)"
)
MAX_BYTES = 10 * 1024 * 1024
_ROBOTS = {}
_CACHE = {}
_LOCK = threading.RLock()
_LAST_REQUEST = {}


def robots_allowed(text, url, agent=USER_AGENT):
    """Honor wildcard/end-anchor rules as well as the longest matching path."""
    groups = []
    agents = []
    rules = []
    for line in text.replace("\\r\\n", "\n").splitlines() + ["User-agent: __end__"]:
        line = line.split("#", 1)[0].strip()
        if ":" not in line:
            continue
        key, value = [x.strip() for x in line.split(":", 1)]
        if key.lower() == "user-agent":
            if rules:
                groups.append((agents, rules))
                agents = []
                rules = []
            agents.append(value.lower())
        elif key.lower() in {"allow", "disallow"} and value:
            rules.append((key.lower(), value))
    specific = [g for g in groups if any(a != "*" and a in agent.lower() for a in g[0])]
    selected = specific or [g for g in groups if "*" in g[0]]
    path = urlparse(url).path + (
        "?" + urlparse(url).query if urlparse(url).query else ""
    )
    matched = []
    for _, group_rules in selected:
        for kind, pattern in group_rules:
            anchored = pattern.endswith("$")
            pattern = pattern[:-1] if anchored else pattern
            regex = (
                "^"
                + re.escape(pattern).replace(r"\*", ".*")
                + ("$" if anchored else "")
            )
            if re.search(regex, path):
                matched.append((len(pattern.replace("*", "")), kind == "allow"))
    return max(matched)[1] if matched else True


def validate_url(url, hosts):
    try:
        p = urlparse(url)
        valid = (
            p.scheme == "https"
            and p.hostname in hosts
            and p.port in {None, 443}
            and not p.username
            and not p.password
            and not p.fragment
        )
    except ValueError:
        valid = False
    if not valid:
        raise SourceAccessError(
            "URL is outside this connector's approved HTTPS origins."
        )
    return url


class PolicyHTTP:
    def __init__(self, hosts, api_hosts=()):
        self.hosts, self.api_hosts = set(hosts), set(api_hosts)
        self.requests = 0

    def _allowed(self, client, url):
        host = urlparse(url).hostname
        if host in self.api_hosts:
            return  # Documented API endpoints are explicitly intended for programmatic access.
        cached = _ROBOTS.get(host)
        if cached and time.monotonic() - cached[0] < 86400:
            parser = cached[1]
        else:
            r = client.get(
                f"https://{host}/robots.txt",
                headers={"User-Agent": USER_AGENT},
                follow_redirects=False,
            )
            if r.status_code == 404:
                parser = None
            elif r.status_code == 200:
                parser = r.text
            else:
                raise SourceAccessError(
                    "Unable to verify robots.txt; automated crawling paused."
                )
            _ROBOTS[host] = (time.monotonic(), parser)
        if parser and not robots_allowed(parser, url):
            raise SourceAccessError(
                "Automated access is disallowed by the publisher's robots.txt."
            )

    def get(self, url, *, headers=None, use_cache=True):
        validate_url(url, self.hosts)
        original_host = urlparse(url).hostname
        with (
            _LOCK,
            httpx.Client(
                timeout=httpx.Timeout(20, connect=10),
                follow_redirects=False,
                trust_env=False,
            ) as client,
        ):
            for hop in range(6):
                validate_url(url, self.hosts)
                self._allowed(client, url)
                cache = _CACHE.get(url)
                if use_cache and cache and time.monotonic() - cache[0] < 300:
                    return cache[1]
                host = urlparse(url).hostname
                pause = max(0, 0.3 - (time.monotonic() - _LAST_REQUEST.get(host, 0)))
                if pause:
                    time.sleep(pause)
                for attempt in range(3):
                    self.requests += 1
                    try:
                        with client.stream(
                            "GET",
                            url,
                            headers={
                                "User-Agent": USER_AGENT,
                                **((headers or {}) if host == original_host else {}),
                            },
                        ) as response:
                            status, response_headers = (
                                response.status_code,
                                dict(response.headers),
                            )
                            if status in {301, 302, 303, 307, 308}:
                                destination = response.headers.get("location")
                                if not destination:
                                    raise SourceError("Redirect has no destination.")
                                url = urljoin(url, destination)
                                validate_url(url, self.hosts)
                                break
                            if status in {429, 500, 502, 503, 504} and attempt < 2:
                                delay = min(3, 2**attempt)
                                retry = response.headers.get("retry-after", "")
                                # Do not retry sooner than a server's long Retry-After.
                                if retry.isdigit() and int(retry) > 3:
                                    raise SourceError(
                                        "Publisher requested a later retry; sync deferred."
                                    )
                                time.sleep(
                                    max(delay, int(retry) if retry.isdigit() else 0)
                                )
                                continue
                            if status != 200:
                                raise SourceAccessError(
                                    f"Official policy request returned HTTP {status}; no bypass attempted."
                                )
                            content = bytearray()
                            for chunk in response.iter_bytes():
                                content.extend(chunk)
                                if len(content) > MAX_BYTES:
                                    raise SourceError(
                                        "Official response exceeds 10 MB limit."
                                    )
                            if not content:
                                raise SourceError("Official policy response was empty.")
                            _LAST_REQUEST[host] = time.monotonic()
                            result = (bytes(content), response_headers, url)
                            _CACHE[url] = (time.monotonic(), result)
                            return result
                    except (httpx.TimeoutException, httpx.NetworkError):
                        if attempt == 2:
                            raise SourceError(
                                "Official source unavailable after bounded retries."
                            ) from None
                        time.sleep(2**attempt)
                else:
                    raise SourceError("Official source retry limit reached.")
            raise SourceError("Official source redirect limit reached.")
