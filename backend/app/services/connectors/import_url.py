"""User-initiated import of ONE vacancy page via its schema.org JobPosting data.
Safeguards: http(s) only, public IPs only (SSRF guard), robots.txt respected, no redirects,
size cap, 20 s timeout. Sites that block automation: use 'Add manually' instead."""
import hashlib
import html as _html
import ipaddress
import json
import re
import socket
import urllib.robotparser
from urllib.parse import urlparse

import httpx

from app.services.connectors.base import NormalizedJob
from app.services.connectors.remotive import html_to_text, parse_date

UA = {"User-Agent": "JOBHUNT-AI/0.1 (personal job-search assistant)"}
MAX_BYTES = 2 * 1024 * 1024


class BadUrl(ValueError):
    pass


class RobotsDisallowed(Exception):
    pass


class NoJobData(Exception):
    pass


def assert_public_url(url: str) -> None:
    u = urlparse(url)
    if u.scheme not in ("http", "https") or not u.hostname:
        raise BadUrl("Enter a full http(s) link.")
    try:
        infos = socket.getaddrinfo(u.hostname, None)
    except socket.gaierror:
        raise BadUrl("Could not find that address.")
    for info in infos:
        if not ipaddress.ip_address(info[4][0]).is_global:
            raise BadUrl("That address is not allowed.")


def robots_allows(url: str) -> bool:
    u = urlparse(url)
    rp = urllib.robotparser.RobotFileParser()
    try:
        r = httpx.get(f"{u.scheme}://{u.netloc}/robots.txt", headers=UA, timeout=10, follow_redirects=False)
        if r.status_code >= 400:
            return True
        rp.parse(r.text.splitlines())
    except httpx.HTTPError:
        return True
    return rp.can_fetch("JOBHUNT-AI", url)


def fetch_page(url: str) -> str:
    with httpx.stream("GET", url, headers=UA, timeout=20, follow_redirects=False) as r:
        r.raise_for_status()
        if "html" not in r.headers.get("content-type", "html").lower():
            raise NoJobData("That link is not a web page.")
        buf = bytearray()
        for chunk in r.iter_bytes():
            buf.extend(chunk)
            if len(buf) > MAX_BYTES:
                raise BadUrl("That page is too large.")
    return bytes(buf).decode("utf-8", errors="replace")


def _find_posting(node):
    if isinstance(node, list):
        for n in node:
            if (f := _find_posting(n)):
                return f
    elif isinstance(node, dict):
        t = node.get("@type")
        if t == "JobPosting" or (isinstance(t, list) and "JobPosting" in t):
            return node
        return _find_posting(node.get("@graph", []))
    return None


def parse_job_posting(page: str, url: str, country: str = "") -> NormalizedJob:
    for block in re.findall(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', page, re.S | re.I):
        try:
            post = _find_posting(json.loads(_html.unescape(block) if "&quot;" in block else block))
        except ValueError:
            continue
        if not post:
            continue
        title = html_to_text(str(post.get("title", "")))
        if not title:
            continue
        org = post.get("hiringOrganization") or {}
        loc = post.get("jobLocation") or {}
        loc = loc[0] if isinstance(loc, list) and loc else loc
        addr = (loc.get("address") or {}) if isinstance(loc, dict) else {}
        place = ", ".join(x for x in [addr.get("addressLocality"), addr.get("addressRegion")]
                          if isinstance(x, str)) if isinstance(addr, dict) else ""
        desc = html_to_text(str(post.get("description", "")))
        if "<" in desc:
            desc = html_to_text(desc)
        link = post.get("url") if isinstance(post.get("url"), str) and post["url"].startswith("http") else url
        return NormalizedJob(
            external_id=hashlib.sha1(url.encode()).hexdigest(), title=title[:300],
            company=(org.get("name", "") if isinstance(org, dict) else str(org))[:200],
            location=place[:200], country=country, is_remote=post.get("jobLocationType") == "TELECOMMUTE",
            description=desc, url=link[:1000], posted_at=parse_date(post.get("datePosted")))
    raise NoJobData("No structured job data found on that page. Use 'Add manually' and paste the vacancy.")


def import_job_from_url(url: str, country: str = "") -> NormalizedJob:
    assert_public_url(url)
    if not robots_allows(url):
        raise RobotsDisallowed("This site's robots.txt does not allow automated reading. Use 'Add manually' instead.")
    return parse_job_posting(fetch_page(url), url, country)
