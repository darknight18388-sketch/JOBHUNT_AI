import httpx
import pytest

from app.api import jobs as jobs_api
from app.core.config import settings
from app.services.connectors import careerjet
from app.services.connectors.careerjet import CareerjetConnector
from app.services.connectors.context import client_context


def auth(client, email="a@example.com"):
    client.post("/api/auth/register", json={"email": email, "password": "StrongPass123"})
    t = client.post("/api/auth/login", json={"email": email, "password": "StrongPass123"})
    return {"Authorization": f"Bearer {t.json()['access_token']}"}


def test_job_titles_are_grouped_and_unique(client):
    data = client.get("/api/job-titles").json()
    assert {"Engineering & Technical", "IT & Software"} <= {g["group"] for g in data}
    titles = [t for g in data for t in g["titles"]]
    assert "Mechanical Engineer" in titles and "Maintenance Engineer" in titles
    assert len(titles) == len(set(titles))


def test_job_sites_links_for_sri_lanka(client):
    links = client.get("/api/job-sites", params={"country": "LK", "query": "Mechanical Engineer"}).json()
    by = {l["name"]: l["url"] for l in links}
    assert by["LinkedIn Jobs"].startswith("https://www.linkedin.com/jobs/search/?")
    assert "keywords=Mechanical+Engineer" in by["LinkedIn Jobs"] and "Sri+Lanka" in by["LinkedIn Jobs"]
    assert "site%3Atopjobs.lk" in by["TopJobs.lk"] and "Mechanical+Engineer" in by["TopJobs.lk"]
    assert {"ikman.lk jobs", "Xpress.jobs", "Indeed", "Google Jobs"} <= set(by)
    assert all(u.startswith("https://") for u in by.values())


def test_job_sites_links_for_other_country_skip_sri_lankan_sites(client):
    names = {l["name"] for l in client.get("/api/job-sites", params={"country": "GB", "query": "x"}).json()}
    assert "TopJobs.lk" not in names and "LinkedIn Jobs" in names


def test_job_sites_query_is_url_encoded(client):
    links = client.get("/api/job-sites", params={"country": "LK", "query": "a&b=c #x"}).json()
    li = next(l["url"] for l in links if l["name"] == "LinkedIn Jobs")
    assert "a%26b%3Dc+%23x" in li


@pytest.fixture()
def careerjet_on(monkeypatch):
    monkeypatch.setattr(settings, "careerjet_api_key", "KEY123")
    monkeypatch.setattr(settings, "careerjet_user_ip", "")


def test_careerjet_requires_key_and_known_country(monkeypatch):
    c = CareerjetConnector()
    monkeypatch.setattr(settings, "careerjet_api_key", "")
    assert c.enabled() is False
    monkeypatch.setattr(settings, "careerjet_api_key", "k")
    assert c.enabled() and c.applies("LK") and not c.applies("ALL") and not c.applies("MX")


def test_careerjet_request_and_normalisation(careerjet_on, monkeypatch):
    seen = {}

    def fake_get(url, params=None, auth=None, timeout=None):
        seen.update(url=url, params=params, auth=auth)
        return httpx.Response(200, request=httpx.Request("GET", url), json={
            "type": "JOBS", "hits": 2, "jobs": [
                {"title": "Maintenance Engineer", "company": "Lanka Eng", "date": "Wed,15 Nov 2026 19:13:43 GMT",
                 "description": "Preventive <b>maintenance</b>", "locations": "Colombo",
                 "salary": "LKR 150000 per month", "url": "https://jobviewtrack.com/v2/abc"},
                {"title": "No link job", "url": "http://insecure.example/x"},
            ]})
    monkeypatch.setattr(careerjet.httpx, "get", fake_get)
    token = client_context.set({"ip": "203.0.113.7", "ua": "UnitTest/1.0"})
    try:
        jobs = CareerjetConnector().fetch("maintenance engineer", "LK", "Colombo")
    finally:
        client_context.reset(token)
    assert seen["auth"] == ("KEY123", "")  # key is sent as basic auth, never in the URL
    assert "KEY123" not in str(seen["params"])
    p = seen["params"]
    assert (p["locale_code"], p["keywords"], p["location"]) == ("en_LK", "maintenance engineer", "Colombo")
    assert (p["user_ip"], p["user_agent"]) == ("203.0.113.7", "UnitTest/1.0")
    assert len(jobs) == 1  # insecure-link record skipped
    j = jobs[0]
    assert j.company == "Lanka Eng" and j.country == "LK" and j.location == "Colombo"
    assert j.description == "Preventive maintenance" and j.url == "https://jobviewtrack.com/v2/abc"
    assert j.posted_at is not None and j.posted_at.year == 2026


def test_careerjet_location_mode_returns_nothing(careerjet_on, monkeypatch):
    monkeypatch.setattr(careerjet.httpx, "get", lambda url, **k: httpx.Response(
        200, request=httpx.Request("GET", url), json={"type": "LOCATIONS", "locations": ["A", "B"]}))
    assert CareerjetConnector().fetch("x", "LK", "Springfield") == []


def test_careerjet_in_search_unsupported_locale_is_reported_safely(client, careerjet_on, monkeypatch):
    def fake_get(url, **k):
        req = httpx.Request("GET", url)
        return httpx.Response(400, request=req, json={"message": "Unsupported locale code"})
    monkeypatch.setattr(careerjet.httpx, "get", fake_get)
    monkeypatch.setattr(jobs_api.CONNECTORS["remotive"], "fetch", lambda *a, **k: [])
    h = auth(client)
    r = client.post("/api/jobs/search", headers=h, json={"query": "x", "country": "LK"})
    assert r.status_code == 200
    cj = next(s for s in r.json()["sources"] if s["source"] == "careerjet")
    assert cj["status"] == "error"
    src = next(s for s in client.get("/api/jobs/sources", headers=h).json() if s["key"] == "careerjet")
    assert src["last_error"] == "HTTPStatusError (HTTP 400)" and src["enabled"] is True


def test_careerjet_gets_clients_ip_from_search_request(client, careerjet_on, monkeypatch):
    captured = {}

    def fake_fetch(self, query="", country="ALL", location=""):
        captured.update(client_context.get())
        return []
    monkeypatch.setattr(CareerjetConnector, "fetch", fake_fetch)
    monkeypatch.setattr(jobs_api.CONNECTORS["remotive"], "fetch", lambda *a, **k: [])
    h = auth(client)
    client.post("/api/jobs/search", headers={**h, "User-Agent": "MyBrowser/9"},
                json={"query": "x", "country": "LK"})
    assert captured["ua"] == "MyBrowser/9" and captured["ip"]
