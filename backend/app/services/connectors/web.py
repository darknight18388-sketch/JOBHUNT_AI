"""Safe, polite web access for user/company-supplied URLs: SSRF guard, robots.txt, size cap, same-host redirects."""
import ipaddress
import socket
import urllib.robotparser
from urllib.parse import urljoin, urlparse

import httpx

UA = "JOBHUNT-AI/1.0 (personal job-search assistant)"
MAX_BYTES = 2_000_000


def assert_public_url(url: str) -> None:
    """Reject non-http(s) links and any host that resolves to a private/loopback/link-local address."""
    u = urlparse(url)
    if u.scheme not in ("http", "https") or not u.hostname:
        raise ValueError("Enter a full http(s) link.")
    try:
        infos = socket.getaddrinfo(u.hostname, None)
    except socket.gaierror:
        raise ValueError("That address could not be found.")
    for info in infos:
        if not ipaddress.ip_address(info[4][0]).is_global:
            raise ValueError("That address is not allowed.")


def robots_allows(url: str) -> bool:
    u = urlparse(url)
    rp = urllib.robotparser.RobotFileParser()
    try:
        r = httpx.get(f"{u.scheme}://{u.netloc}/robots.txt", headers={"User-Agent": UA}, timeout=10)
        if r.status_code in (401, 403):
            return False
        if r.status_code >= 400:
            return True  # no robots.txt = no restriction
        rp.parse(r.text.splitlines())
    except httpx.HTTPError:
        return True
    return rp.can_fetch(UA, url)


def safe_get(url: str, accept: str = "text/html,application/xhtml+xml") -> str:
    """GET a public page: SSRF-checked, robots-checked, max 3 same-host redirects, 2 MB cap."""
    host = urlparse(url).netloc
    for _ in range(4):
        assert_public_url(url)
        if not robots_allows(url):
            raise PermissionError("This site's robots.txt does not allow automated reading.")
        with httpx.stream("GET", url, headers={"User-Agent": UA, "Accept": accept}, timeout=20,
                          follow_redirects=False) as r:
            if r.status_code in (301, 302, 303, 307, 308) and r.headers.get("location"):
                url = urljoin(url, r.headers["location"])
                if urlparse(url).netloc != host:
                    raise ValueError("The page redirects to another site, so it was not opened.")
                continue
            r.raise_for_status()
            buf = b""
            for chunk in r.iter_bytes():
                buf += chunk
                if len(buf) > MAX_BYTES:
                    raise ValueError("Page is too large.")
            return buf.decode(r.encoding or "utf-8", errors="replace")
    raise ValueError("Too many redirects.")
