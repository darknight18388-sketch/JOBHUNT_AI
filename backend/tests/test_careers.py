"""Company career pages (ported from the user's Phase 5b patch). Offline: all network calls are stubbed."""
from pathlib import Path

import pytest

from app.api import jobs as jobs_api
from app.services import careers
from app.services.connectors import ats, jsonld, web
from app.services.connectors.base import NormalizedJob

FIX = Path(__file__).parent / "fixtures"


def auth(client, email="a@example.com"):
    client.post("/api/auth/register", json={"email": email, "password": "StrongPass123"})
    t = client.post("/api/auth/login", json={"email": email, "password": "StrongPass123"})
    return {"Authorization": f"Bearer {t.json()['access_token']}"}


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    monkeypatch.setattr(jobs_api.CONNECTORS["remotive"], "fetch", lambda *a, **k: [])


GH = {"jobs": [{"id": 11, "title": "Backend Engineer", "location": {"name": "Remote - Asia"},
                "absolute_url": "https://boards.greenhouse.io/acme/jobs/11", "first_published": "2026-11-01T10:00:00-05:00",
                "content": "&lt;p&gt;Build &amp;amp; run APIs in Python&lt;/p&gt;", "departments": [{"name": "Engineering"}]},
               {"id": 12, "title": "", "absolute_url": "https://boards.greenhouse.io/acme/jobs/12"}]}
LEVER = [{"id": "abc", "text": "Data Analyst", "categories": {"location": "Colombo", "commitment": "Full-time", "team": "Data"},
          "hostedUrl": "https://jobs.lever.co/acme/abc", "createdAt": 1762000000000, "workplaceType": "hybrid",
          "descriptionPlain": "Analyse data with SQL and Excel.", "lists": [{"text": "Requirements", "content": "<li>Degree</li>"}]}]
ASHBY = {"jobs": [{"id": "x1", "title": "Designer", "location": "Remote", "isRemote": True, "employmentType": "FullTime",
                   "jobUrl": "https://jobs.ashbyhq.com/acme/x1", "publishedAt": "2026-11-02T00:00:00.000+00:00",
                   "descriptionHtml": "<p>Design in Figma</p>", "department": "Design"},
                  {"id": "x2", "title": "Hidden", "isListed": False, "jobUrl": "https://jobs.ashbyhq.com/acme/x2"}]}
REC = {"offers": [{"id": 5, "title": "Accountant", "city": "Kandy", "country": "Sri Lanka", "remote": False,
                   "careers_url": "https://acme.recruitee.com/o/accountant", "created_at": "2026-11-03T08:00:00.000Z",
                   "description": "<p>Tally and SAP</p>", "requirements": "<p>ACCA part-qualified</p>"}]}
WORKABLE = {"jobs": [{"title": "QA Engineer", "shortcode": "AB12", "city": "Colombo", "country": "Sri Lanka",
                      "url": "https://apply.workable.com/acme/j/AB12/", "telecommuting": False,
                      "published_on": "2026-11-04", "description": "<p>Testing with Selenium</p>"}]}


@pytest.mark.parametrize("fn,payload,title,loc,remote", [
    (ats.parse_greenhouse, GH, "Backend Engineer", "Remote - Asia", True),
    (ats.parse_lever, LEVER, "Data Analyst", "Colombo", False),
    (ats.parse_ashby, ASHBY, "Designer", "Remote", True),
    (ats.parse_recruitee, REC, "Accountant", "Kandy, Sri Lanka", False),
    (ats.parse_workable, WORKABLE, "QA Engineer", "Colombo, Sri Lanka", False),
])
def test_ats_parsers(fn, payload, title, loc, remote):
    jobs = fn(payload, "Acme", "LK")
    assert len(jobs) == 1  # incomplete / unlisted records are skipped, not guessed
    j = jobs[0]
    assert (j.title, j.company, j.location, j.is_remote, j.country) == (title, "Acme", loc, remote, "LK")
    assert j.url.startswith("https://") and "<" not in j.description and j.description


def test_greenhouse_description_is_unescaped_text():
    assert ats.parse_greenhouse(GH, "Acme")[0].description == "Build & run APIs in Python"


@pytest.mark.parametrize("fn,bad", [(ats.parse_greenhouse, []), (ats.parse_lever, {}), (ats.parse_ashby, {"x": 1}),
                                    (ats.parse_recruitee, []), (ats.parse_workable, "x")])
def test_ats_parsers_reject_unexpected_shapes(fn, bad):
    with pytest.raises(ValueError):
        fn(bad, "Acme")


@pytest.mark.parametrize("url,expected", [
    ("https://boards.greenhouse.io/acme", ("greenhouse", "acme")),
    ("https://job-boards.greenhouse.io/acme/jobs/1", ("greenhouse", "acme")),
    ("https://jobs.lever.co/acme", ("lever", "acme")),
    ("https://jobs.ashbyhq.com/acme", ("ashby", "acme")),
    ("https://acme.recruitee.com/", ("recruitee", "acme")),
    ("https://apply.workable.com/acme/", ("workable", "acme")),
    ("https://www.acme.lk/careers", None),
    ("https://boards.greenhouse.io/", None),
    ("https://jobs.lever.co/ac me%2F..", None),
    ("https://evil.example.com/boards.greenhouse.io/acme", None),
])
def test_detect_ats(url, expected):
    assert ats.detect_ats(url) == expected


def test_ats_api_url_rejects_path_tricks():
    with pytest.raises(ValueError):
        ats.api_url("lever", "../../etc")
    assert ats.api_url("lever", "acme") == "https://api.lever.co/v0/postings/acme?mode=json"


# ------------------------------------------------------------------ career pages (JSON-LD)
def test_jsonld_posting_parsed():
    html = (FIX / "career_job_page.html").read_text()
    job = jsonld.posting_to_job(jsonld.extract_postings(html)[0], "https://careers.example.lk/jobs/x")
    assert (job.title, job.company, job.location, job.country) == ("Maintenance Trainee", "Lanka Machines (Pvt) Ltd", "Colombo", "LK")
    assert job.job_type == "INTERN" and "preventive maintenance" in job.description and "<p>" not in job.description


def test_jsonld_graph_and_itemlist():
    html = ('<script type="application/ld+json">{"@graph":[{"@type":"WebSite"},{"@type":"ItemList","itemListElement":'
            '[{"@type":"ListItem","item":{"@type":"JobPosting","title":"A"}}]}]}</script>')
    assert [p["title"] for p in jsonld.extract_postings(html)] == ["A"]
    assert jsonld.extract_postings("<script type='application/ld+json'>{broken</script>") == []


def test_listing_follows_only_same_host_job_links():
    links = jsonld.detail_links((FIX / "career_listing.html").read_text(), "https://careers.example.lk/careers")
    assert links == ["https://careers.example.lk/jobs/trainee-engineer", "https://careers.example.lk/jobs/accountant"]


def test_career_page_connector_visits_detail_pages(monkeypatch):
    pages = {"https://careers.example.lk/careers": (FIX / "career_listing.html").read_text(),
             "https://careers.example.lk/jobs/trainee-engineer": (FIX / "career_job_page.html").read_text(),
             "https://careers.example.lk/jobs/accountant": "<html>no data</html>"}
    monkeypatch.setattr(web, "safe_get", lambda u, **k: pages[u])
    monkeypatch.setattr(jsonld.time, "sleep", lambda s: None)
    jobs = jsonld.CareerPageConnector("career-x", "Lanka Machines", "https://careers.example.lk/careers", "LK").fetch()
    assert [j.title for j in jobs] == ["Maintenance Trainee"]


def test_career_page_without_structured_data_is_an_error(monkeypatch):
    monkeypatch.setattr(web, "safe_get", lambda u, **k: "<html><body>Apply by email</body></html>")
    with pytest.raises(LookupError):
        jsonld.CareerPageConnector("career-x", "Co", "https://careers.example.lk/").fetch()


# ------------------------------------------------------------------ safety guards
@pytest.mark.parametrize("bad", ["http://127.0.0.1/x", "http://localhost/x", "file:///etc/passwd",
                                 "http://169.254.169.254/latest", "http://10.0.0.5/", "ftp://example.com/"])
def test_private_and_odd_urls_blocked(bad):
    with pytest.raises(ValueError):
        web.assert_public_url(bad)


# ------------------------------------------------------------------ API: company career pages
class FakeCareer:
    def __init__(self, items):
        self.items = items

    def fetch(self):
        return self.items


def _items():
    return [NormalizedJob(external_id="j1", title="Trainee Engineer", url="https://careers.acme.lk/j1",
                          description="Preventive maintenance and AutoCAD for trainees."),
            NormalizedJob(external_id="j2", title="Accountant", company="Acme", url="https://careers.acme.lk/j2",
                          description="Tally and SAP experience for the accounts team.")]


def test_career_source_lifecycle_privacy_and_cache(client, monkeypatch):
    monkeypatch.setattr(careers, "connector_for", lambda s: FakeCareer(_items()))
    ha, hb = auth(client, "a@example.com"), auth(client, "b@example.com")
    r = client.post("/api/jobs/careers", json={"company": "Acme", "url": "https://boards.greenhouse.io/acme",
                                               "country": "LK"}, headers=ha)
    assert r.status_code == 201 and r.json()["ats"] == "greenhouse"
    cid = r.json()["id"]
    assert client.post("/api/jobs/careers", json={"company": "Acme", "url": "https://boards.greenhouse.io/acme"},
                       headers=ha).status_code == 409
    ref = client.post(f"/api/jobs/careers/{cid}/refresh", headers=ha).json()
    assert (ref["status"], ref["created"]) == ("ok", 2)
    assert client.post(f"/api/jobs/careers/{cid}/refresh", headers=ha).json()["status"] == "skipped"
    jobs = client.get("/api/jobs?country=LK", headers=ha).json()["items"]
    assert {j["title"] for j in jobs} == {"Trainee Engineer", "Accountant"}
    t = next(j for j in jobs if j["title"] == "Trainee Engineer")
    assert t["company"] == "Acme" and t["country"] == "LK"
    assert t["attribution"] == "From Acme's official career page" and t["is_manual"] is False
    # other users see nothing and cannot touch it
    assert client.get("/api/jobs", headers=hb).json()["total"] == 0
    assert client.get(f"/api/jobs/{t['id']}", headers=hb).status_code == 404
    assert client.get("/api/jobs/careers", headers=hb).json() == []
    assert client.post(f"/api/jobs/careers/{cid}/refresh", headers=hb).status_code == 404
    assert client.delete(f"/api/jobs/careers/{cid}", headers=hb).status_code == 404
    # individual career jobs cannot be deleted one by one; removing the source removes them all
    assert client.delete(f"/api/jobs/{t['id']}", headers=ha).status_code == 404
    assert client.delete(f"/api/jobs/careers/{cid}", headers=ha).status_code == 204
    assert client.get("/api/jobs", headers=ha).json()["total"] == 0


def test_search_refreshes_users_career_pages_for_the_selected_country(client, monkeypatch):
    monkeypatch.setattr(careers, "connector_for", lambda s: FakeCareer(_items()))
    h = auth(client)
    client.post("/api/jobs/careers", json={"company": "Acme", "url": "https://boards.greenhouse.io/acme",
                                           "country": "LK"}, headers=h)
    r = client.post("/api/jobs/search", json={"country": "LK", "query": "engineer", "include_remote": False},
                    headers=h).json()
    assert any(x["source"] == "Acme" and x["status"] == "ok" for x in r["sources"])
    assert [j["title"] for j in r["jobs"]] == ["Trainee Engineer"]
    assert r["note"] == ""  # a country-specific source (your career page) was used
    de = client.post("/api/jobs/search", json={"country": "DE", "query": "engineer"}, headers=h).json()
    assert not any(x["source"] == "Acme" for x in de["sources"])
    other = auth(client, "b@example.com")
    r2 = client.post("/api/jobs/search", json={"country": "LK", "query": "engineer"}, headers=other).json()
    assert not any(x["source"] == "Acme" for x in r2["sources"]) and r2["jobs"] == []


def test_career_source_failure_is_recorded(client, monkeypatch):
    class Boom:
        def fetch(self):
            raise LookupError("No JobPosting data found.")
    monkeypatch.setattr(careers, "connector_for", lambda s: Boom())
    h = auth(client)
    cid = client.post("/api/jobs/careers", json={"company": "Acme", "url": "https://boards.greenhouse.io/acme"},
                      headers=h).json()["id"]
    r = client.post(f"/api/jobs/careers/{cid}/refresh", headers=h).json()
    assert r["status"] == "error" and "No JobPosting" in r["message"]
    c = client.get("/api/jobs/careers", headers=h).json()[0]
    assert c["last_status"] == "error" and "LookupError" in c["last_error"]
    assert client.post(f"/api/jobs/careers/{cid}/refresh", headers=h).json()["status"] == "skipped"  # retry delay


def test_career_add_validation(client, monkeypatch):
    h = auth(client)
    post = lambda url: client.post("/api/jobs/careers", json={"company": "Acme", "url": url}, headers=h)
    assert post("http://acme.lk/careers").status_code == 400                # https only
    assert post("https://127.0.0.1/careers").status_code == 400             # private address
    assert post("https://169.254.169.254/careers").status_code == 400
    monkeypatch.setattr(web, "assert_public_url", lambda u: None)           # skip DNS in tests
    monkeypatch.setattr(web, "robots_allows", lambda u: False)
    assert post("https://www.acme.lk/careers").status_code == 403           # robots.txt says no
    monkeypatch.setattr(web, "robots_allows", lambda u: True)
    assert post("https://www.acme.lk/careers").json()["ats"] == "jsonld"
    assert client.post("/api/jobs/careers", json={"company": "A", "url": "https://boards.greenhouse.io/a",
                                                  "country": "ZZ"}, headers=h).status_code == 400
    assert client.post("/api/jobs/careers", json={"company": "A", "url": "https://boards.greenhouse.io/a"},
                       headers={}).status_code == 401


def test_career_limit_per_user(client, monkeypatch):
    monkeypatch.setattr(careers, "MAX_PER_USER", 2)
    h = auth(client)
    for n in ("a", "b"):
        assert client.post("/api/jobs/careers", json={"company": n, "url": f"https://boards.greenhouse.io/{n}"},
                           headers=h).status_code == 201
    assert client.post("/api/jobs/careers", json={"company": "c", "url": "https://boards.greenhouse.io/c"},
                       headers=h).status_code == 400


def test_jsonld_handles_html_escaped_json():
    html = ('<script type="application/ld+json">{&quot;@type&quot;:&quot;JobPosting&quot;,'
            '&quot;title&quot;:&quot;Welder&quot;}</script>')
    assert [p["title"] for p in jsonld.extract_postings(html)] == ["Welder"]


# ------------------------------------------------------------------ web.safe_get: redirects, size, robots
class _Resp:
    def __init__(self, status=200, headers=None, body=b"", chunks=None):
        self.status_code, self.headers = status, headers or {}
        self._chunks, self.encoding = chunks if chunks is not None else [body], "utf-8"

    def raise_for_status(self):
        if self.status_code >= 400:
            import httpx
            raise httpx.HTTPStatusError("bad", request=httpx.Request("GET", "https://x"),
                                        response=httpx.Response(self.status_code))

    def iter_bytes(self):
        yield from self._chunks

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


@pytest.fixture()
def fake_web(monkeypatch):
    pages = {}
    monkeypatch.setattr(web, "assert_public_url", lambda u: None)
    monkeypatch.setattr(web, "robots_allows", lambda u: True)
    monkeypatch.setattr(web.httpx, "stream", lambda m, url, **k: pages[url])
    return pages


def test_safe_get_follows_same_host_redirect(fake_web):
    fake_web["https://a.example/x"] = _Resp(301, {"location": "/y"})
    fake_web["https://a.example/y"] = _Resp(200, body=b"<html>ok</html>")
    assert web.safe_get("https://a.example/x") == "<html>ok</html>"


def test_safe_get_refuses_cross_host_redirect(fake_web):
    fake_web["https://a.example/x"] = _Resp(302, {"location": "https://evil.example/y"})
    with pytest.raises(ValueError, match="another site"):
        web.safe_get("https://a.example/x")


def test_safe_get_redirect_loop_and_size_cap_and_robots(fake_web, monkeypatch):
    fake_web["https://a.example/loop"] = _Resp(302, {"location": "/loop"})
    with pytest.raises(ValueError, match="Too many redirects"):
        web.safe_get("https://a.example/loop")
    fake_web["https://a.example/big"] = _Resp(200, chunks=[b"x" * 1_000_000] * 3)
    with pytest.raises(ValueError, match="too large"):
        web.safe_get("https://a.example/big")
    fake_web["https://a.example/err"] = _Resp(500)
    with pytest.raises(Exception):
        web.safe_get("https://a.example/err")
    monkeypatch.setattr(web, "robots_allows", lambda u: False)
    with pytest.raises(PermissionError):
        web.safe_get("https://a.example/page")
