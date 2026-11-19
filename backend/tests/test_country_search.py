import io
import zipfile
from pathlib import Path

import httpx
import pytest

from app.api import jobs as jobs_api
from app.services.connectors import import_url, rss
from app.services.connectors.base import JobConnector, NormalizedJob
from app.services.connectors.rss import RssConnector, parse_rss

RSS_XML = (Path(__file__).parent / "fixtures" / "itpro_sample.xml").read_bytes()


def auth(client, email="a@example.com"):
    client.post("/api/auth/register", json={"email": email, "password": "StrongPass123"})
    t = client.post("/api/auth/login", json={"email": email, "password": "StrongPass123"})
    return {"Authorization": f"Bearer {t.json()['access_token']}"}


def make_docx(lines):
    body = "".join(f"<w:p><w:r><w:t>{l}</w:t></w:r></w:p>" for l in lines)
    xml = ('<?xml version="1.0" encoding="UTF-8"?><w:document xmlns:w="http://schemas.openxmlformats.org/'
           f'wordprocessingml/2006/main"><w:body>{body}</w:body></w:document>')
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("word/document.xml", xml)
    return buf.getvalue()


class FakeConnector(JobConnector):
    key, name, site_url, attribution = "fake", "Fake", "", "Job via Fake"
    uses_query = True
    min_interval_hours = 0

    def __init__(self):
        self.calls = []

    def fetch(self, query="", country="ALL", location=""):
        self.calls.append((query, country, location))
        return [
            NormalizedJob(f"lk-{query}", "Maintenance Engineer", "Lanka Eng", "Colombo", "LK", description="AutoCAD maintenance"),
            NormalizedJob(f"gb-{query}", "Maintenance Engineer", "UK Eng", "Leeds", "GB", description="AutoCAD maintenance"),
            NormalizedJob(f"any-{query}", "Remote CAD Designer", "Anywhere Ltd", "Worldwide", "ANY", is_remote=True, description="CAD design"),
        ]


@pytest.fixture()
def fake(monkeypatch):
    f = FakeConnector()
    monkeypatch.setitem(jobs_api.CONNECTORS, "fake", f)
    monkeypatch.setattr(jobs_api.CONNECTORS["remotive"], "fetch", lambda *a, **k: [])
    return f


def test_countries_endpoint(client):
    data = client.get("/api/countries").json()
    assert data[0] == {"code": "ALL", "name": "All countries"}
    assert {"code": "LK", "name": "Sri Lanka"} in data


def test_search_validation(client, fake):
    h = auth(client)
    assert client.post("/api/jobs/search", headers=h, json={"country": "XX", "query": "x"}).status_code == 400
    assert client.post("/api/jobs/search", headers=h, json={"country": "LK"}).status_code == 400  # no CV, no query
    assert client.post("/api/jobs/search", json={"query": "x"}).status_code == 401


def test_country_filter_and_remote_toggle(client, fake):
    h = auth(client)
    def run(**kw):
        r = client.post("/api/jobs/search", headers=h, json={"query": "cad", **kw}).json()
        return sorted(j["country"] for j in r["jobs"])
    assert run(country="LK") == ["ANY", "LK"]
    assert run(country="LK", include_remote=False) == ["LK"]
    assert run(country="GB") == ["ANY", "GB"]
    assert run(country="ALL") == ["ANY", "GB", "LK"]
    assert client.get("/api/jobs?country=LK&include_remote=false", headers=h).json()["total"] == 1


def test_blank_query_is_built_from_cv_skills(client, fake):
    h = auth(client)
    cv = make_docx(["Nimal Perera", "SKILLS", "AutoCAD, SolidWorks, Teamwork, Python, Welding"])
    rid = client.post("/api/resumes/upload", headers=h, files={"file": ("cv.docx", cv)}).json()["id"]
    client.post(f"/api/resumes/{rid}/analyze", headers=h)
    r = client.post("/api/jobs/search", headers=h, json={"country": "LK"}).json()
    assert 1 <= len(r["queries"]) <= 3
    assert "Teamwork" not in r["queries"]  # generic skills are not used as searches
    assert {"AutoCAD", "SolidWorks"} <= set(r["queries"])
    assert [c[0] for c in fake.calls] == r["queries"]  # query-based source called once per query
    assert all(c[1] == "LK" for c in fake.calls)


def test_own_private_jobs_show_in_every_country(client, fake):
    h = auth(client)
    client.post("/api/jobs/manual", headers=h, json={
        "title": "Trainee Technician", "company": "My Lead", "location": "Kandy",
        "description": "Workshop maintenance trainee role."})
    r = client.post("/api/jobs/search", headers=h, json={"query": "technician", "country": "LK"}).json()
    assert [j["title"] for j in r["jobs"]] == ["Trainee Technician"]
    other = auth(client, "b@example.com")
    r2 = client.post("/api/jobs/search", headers=other, json={"query": "technician", "country": "LK"}).json()
    assert r2["jobs"] == []


def test_note_when_no_country_specific_source(client, monkeypatch):
    monkeypatch.setattr(jobs_api.CONNECTORS["remotive"], "fetch", lambda *a, **k: [])
    h = auth(client)
    r = client.post("/api/jobs/search", headers=h, json={"query": "x", "country": "IN"}).json()
    assert "No source for India" in r["note"]
    assert [s["source"] for s in r["sources"]] == ["remotive"]


def test_parse_itpro_rss_fixture():
    jobs = parse_rss(RSS_XML, "LK")
    assert [j.title for j in jobs] == ["Software Engineer (Python) at Example Lanka", "QA Intern at Sample Tech"]
    a, b = jobs
    assert a.company == "Example Lanka" and a.location == "Colombo" and a.country == "LK"
    assert a.url.startswith("https://itpro.lk/job/") and "Python" in a.description
    assert "Apply for this job" not in a.description and "<" not in a.description
    assert b.is_remote and a.posted_at is not None


def test_rss_end_to_end_through_search(client, monkeypatch):
    feeds = [{"name": "itpro-test", "country": "LK", "url": "https://itpro.lk/rss/all/", "enabled": True}]
    monkeypatch.setattr(RssConnector, "feeds", lambda self: feeds)
    monkeypatch.setattr(jobs_api.CONNECTORS["remotive"], "fetch", lambda *a, **k: [])
    monkeypatch.setattr(rss.httpx, "get", lambda *a, **k: httpx.Response(
        200, content=RSS_XML, request=httpx.Request("GET", "https://itpro.lk/rss/all/")))
    h = auth(client)
    r = client.post("/api/jobs/search", headers=h,
                    json={"query": "docker", "country": "LK", "include_remote": False}).json()
    rss_res = next(s for s in r["sources"] if s["source"] == "rss")
    assert rss_res["status"] == "ok" and rss_res["created"] == 2
    assert [j["title"] for j in r["jobs"]] == ["Software Engineer (Python) at Example Lanka"]  # only it mentions Docker
    assert r["total"] == 1
    j = r["jobs"][0]
    assert j["source_name"] == "itpro.lk" and "official RSS feed" in j["attribution"]
    assert r["note"] == ""  # a country-specific source was used


def test_rss_feed_config_ignores_unsafe_entries(tmp_path):
    p = tmp_path / "s.json"
    p.write_text('{"rss": [{"name":"a","country":"LK","url":"http://insecure.example/x","enabled":true},'
                 '{"name":"b","country":"ZZ","url":"https://ok.example/x","enabled":true},'
                 '{"name":"c","country":"LK","url":"https://ok.example/x","enabled":false},'
                 '{"name":"d","country":"LK","url":"https://ok.example/x","enabled":true}]}')
    assert [f["name"] for f in rss.load_feeds(p)] == ["d"]
    assert rss.load_feeds(tmp_path / "missing.json") == []


def test_api_secrets_never_stored_in_errors(client, monkeypatch):
    class Keyed(FakeConnector):
        key = "keyed"
        def fetch(self, query="", country="ALL", location=""):
            req = httpx.Request("GET", "https://api.example.com/x?app_key=SUPERSECRET")
            raise httpx.HTTPStatusError("boom https://api.example.com/x?app_key=SUPERSECRET",
                                        request=req, response=httpx.Response(500, request=req))
    monkeypatch.setitem(jobs_api.CONNECTORS, "keyed", Keyed())
    monkeypatch.setattr(jobs_api.CONNECTORS["remotive"], "fetch", lambda *a, **k: [])
    h = auth(client)
    r = client.post("/api/jobs/search", headers=h, json={"query": "x"})
    assert r.status_code == 200 and "SUPERSECRET" not in r.text
    src = next(s for s in client.get("/api/jobs/sources", headers=h).json() if s["key"] == "keyed")
    assert src["last_error"] == "HTTPStatusError (HTTP 500)"


@pytest.mark.parametrize("bad", [
    "http://127.0.0.1/x", "http://localhost/x", "http://169.254.169.254/latest/meta-data",
    "http://10.0.0.5/job", "http://192.168.1.10/job", "http://[::1]/x",
    "file:///etc/passwd", "ftp://example.com/x", "javascript:alert(1)"])
def test_import_url_blocks_private_and_non_http(client, bad):
    h = auth(client)
    assert client.post("/api/jobs/import-url", headers=h, json={"url": bad}).status_code == 400


PAGE = """<html><head><script type="application/ld+json">
{"@context":"https://schema.org","@type":"JobPosting","title":"Mechanical Maintenance Engineer",
 "hiringOrganization":{"@type":"Organization","name":"Lanka Machines (Pvt) Ltd"},
 "jobLocation":{"@type":"Place","address":{"@type":"PostalAddress","addressLocality":"Colombo","addressRegion":"Western"}},
 "description":"&lt;p&gt;Preventive maintenance of hydraulic &amp;amp; pneumatic systems.&lt;/p&gt;",
 "datePosted":"2026-11-10","url":"https://careers.example.lk/jobs/42"}
</script></head><body>hi</body></html>"""


@pytest.fixture()
def page_ok(monkeypatch):
    monkeypatch.setattr(import_url, "assert_public_url", lambda u: None)
    monkeypatch.setattr(import_url, "robots_allows", lambda u: True)
    monkeypatch.setattr(import_url, "fetch_page", lambda u: PAGE)


def test_import_url_creates_private_unverified_job(client, page_ok):
    ha, hb = auth(client, "a@example.com"), auth(client, "b@example.com")
    r = client.post("/api/jobs/import-url", headers=ha,
                    json={"url": "https://careers.example.lk/jobs/42", "country": "LK"})
    assert r.status_code == 201
    j = r.json()
    assert j["title"] == "Mechanical Maintenance Engineer" and j["company"] == "Lanka Machines (Pvt) Ltd"
    assert j["location"] == "Colombo, Western" and j["country"] == "LK" and j["is_manual"] is True
    assert "hydraulic & pneumatic" in j["description"] and "<" not in j["description"]
    assert j["url"] == "https://careers.example.lk/jobs/42"
    assert client.get(f"/api/jobs/{j['id']}", headers=hb).status_code == 404
    assert client.post("/api/jobs/import-url", headers=ha,
                       json={"url": "https://careers.example.lk/jobs/42"}).status_code == 409
    assert client.delete(f"/api/jobs/{j['id']}", headers=ha).status_code == 204


def test_import_url_respects_robots_and_missing_data(client, monkeypatch):
    h = auth(client)
    monkeypatch.setattr(import_url, "assert_public_url", lambda u: None)
    monkeypatch.setattr(import_url, "robots_allows", lambda u: False)
    r = client.post("/api/jobs/import-url", headers=h, json={"url": "https://blocked.example/job"})
    assert r.status_code == 403
    monkeypatch.setattr(import_url, "robots_allows", lambda u: True)
    monkeypatch.setattr(import_url, "fetch_page", lambda u: "<html>no structured data</html>")
    r = client.post("/api/jobs/import-url", headers=h, json={"url": "https://plain.example/job"})
    assert r.status_code == 422 and "Add manually" in r.json()["detail"]


def test_fetch_page_enforces_size_cap(monkeypatch):
    class FakeStream:
        headers = {"content-type": "text/html"}
        def raise_for_status(self): pass
        def iter_bytes(self):
            for _ in range(5):
                yield b"x" * (1024 * 1024)
        def __enter__(self): return self
        def __exit__(self, *a): return False
    monkeypatch.setattr(import_url.httpx, "stream", lambda *a, **k: FakeStream())
    with pytest.raises(import_url.BadUrl):
        import_url.fetch_page("https://big.example/x")
