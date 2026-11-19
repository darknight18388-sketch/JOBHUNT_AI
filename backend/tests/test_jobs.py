import json
from pathlib import Path

import httpx
import pytest

from app.api import jobs as jobs_api
from app.services.connectors.remotive import parse_remotive

FIX = json.loads((Path(__file__).parent / "fixtures" / "remotive_sample.json").read_text())


def auth(client, email="a@example.com"):
    client.post("/api/auth/register", json={"email": email, "password": "StrongPass123"})
    t = client.post("/api/auth/login", json={"email": email, "password": "StrongPass123"})
    return {"Authorization": f"Bearer {t.json()['access_token']}"}


@pytest.fixture()
def fixture_source(monkeypatch):
    items = parse_remotive(FIX)
    monkeypatch.setattr(jobs_api.CONNECTORS["remotive"], "fetch", lambda *a, **k: items)


MANUAL = {"title": "Trainee Mechanical Engineer", "company": "ABC Engineering (Pvt) Ltd",
          "location": "Colombo", "url": "https://example.com/careers/123",
          "description": "Assist with preventive maintenance of workshop machinery."}


def test_parse_remotive_normalises_and_skips_bad_records():
    jobs = parse_remotive(FIX)
    assert [j.external_id for j in jobs] == ["9001", "9002", "9003"]  # 9004 has non-https url
    j = jobs[0]
    assert j.title == "Python Developer" and j.company == "TestCo" and j.is_remote
    assert "<" not in j.description and "APIs" in j.description and "Python & FastAPI" in j.description
    assert j.url.startswith("https://remotive.com/")
    assert j.posted_at is not None and j.posted_at.tzinfo is not None


def test_parse_rejects_unexpected_format():
    with pytest.raises(ValueError):
        parse_remotive({"nope": []})
    with pytest.raises(ValueError):
        parse_remotive([])


def test_requires_auth(client):
    assert client.get("/api/jobs").status_code == 401
    assert client.post("/api/jobs/search", json={"query": "python"}).status_code == 401
    assert client.post("/api/jobs/manual", json=MANUAL).status_code == 401


def test_refresh_ingests_dedupes_and_attributes(client, fixture_source):
    h = auth(client)
    r = client.post("/api/jobs/search", headers=h, json={"query": "python"}).json()["sources"]
    assert r[0]["status"] == "ok"
    assert (r[0]["created"], r[0]["duplicates"]) == (2, 1)  # 9002 duplicates 9001
    data = client.get("/api/jobs", headers=h).json()
    assert data["total"] == 2
    j = next(x for x in data["items"] if x["title"] == "Python Developer")
    assert j["source_name"] == "Remotive" and "remotive.com" in j["attribution"]
    assert j["url"].startswith("https://remotive.com/")
    assert j["is_stale"] is False and j["is_manual"] is False
    old = next(x for x in data["items"] if x["title"] == "QA Engineer")
    assert old["is_stale"] is True


def test_refresh_is_rate_limited_per_source_terms(client, fixture_source):
    h = auth(client)
    assert client.post("/api/jobs/search", headers=h, json={"query": "python"}).json()["sources"][0]["status"] == "ok"
    second = client.post("/api/jobs/search", headers=h, json={"query": "python"}).json()["sources"][0]
    assert second["status"] == "skipped" and "Next refresh" in second["message"]
    assert client.get("/api/jobs", headers=h).json()["total"] == 2  # nothing re-fetched


def test_source_outage_is_logged_not_crashing(client, monkeypatch):
    def boom(*a, **k):
        raise httpx.ConnectError("network down")
    monkeypatch.setattr(jobs_api.CONNECTORS["remotive"], "fetch", boom)
    h = auth(client)
    r = client.post("/api/jobs/search", headers=h, json={"query": "python"})
    assert r.status_code == 200 and r.json()["sources"][0]["status"] == "error"
    src = client.get("/api/jobs/sources", headers=h).json()[0]
    assert src["last_status"] == "error" and "ConnectError" in src["last_error"]
    # retried immediately -> guarded by the short retry delay
    assert client.post("/api/jobs/search", headers=h, json={"query": "python"}).json()["sources"][0]["status"] == "skipped"


def test_filters_and_pagination(client, fixture_source):
    h = auth(client)
    client.post("/api/jobs/search", headers=h, json={"query": "python"})
    assert client.get("/api/jobs?q=python", headers=h).json()["total"] == 1
    assert client.get("/api/jobs?q=fastapi", headers=h).json()["total"] == 1  # description match
    assert client.get("/api/jobs?location=europe", headers=h).json()["total"] == 1
    assert client.get("/api/jobs?remote=false", headers=h).json()["total"] == 0
    assert client.get("/api/jobs?q=%25", headers=h).json()["total"] == 0  # wildcard is escaped
    p = client.get("/api/jobs?limit=1&page=2", headers=h).json()
    assert len(p["items"]) == 1 and p["total"] == 2
    assert client.get("/api/jobs?limit=500", headers=h).status_code == 422


def test_job_detail_returns_full_description(client, fixture_source):
    h = auth(client)
    client.post("/api/jobs/search", headers=h, json={"query": "python"})
    jid = client.get("/api/jobs?q=python", headers=h).json()["items"][0]["id"]
    d = client.get(f"/api/jobs/{jid}", headers=h).json()
    assert "PostgreSQL" in d["description"]
    assert client.get("/api/jobs/00000000-0000-0000-0000-000000000000", headers=h).status_code == 404


def test_manual_job_is_private_and_deletable(client):
    ha, hb = auth(client, "a@example.com"), auth(client, "b@example.com")
    r = client.post("/api/jobs/manual", json=MANUAL, headers=ha)
    assert r.status_code == 201
    job = r.json()
    assert job["is_manual"] and "unverified" in job["attribution"]
    assert client.get(f"/api/jobs/{job['id']}", headers=hb).status_code == 404
    assert client.get("/api/jobs", headers=hb).json()["total"] == 0
    assert client.delete(f"/api/jobs/{job['id']}", headers=hb).status_code == 404
    assert client.get("/api/jobs", headers=ha).json()["total"] == 1
    assert client.delete(f"/api/jobs/{job['id']}", headers=ha).status_code == 204
    assert client.get("/api/jobs", headers=ha).json()["total"] == 0


def test_manual_duplicate_and_validation(client):
    h = auth(client)
    assert client.post("/api/jobs/manual", json=MANUAL, headers=h).status_code == 201
    assert client.post("/api/jobs/manual", json=MANUAL, headers=h).status_code == 409
    assert client.post("/api/jobs/manual", json={**MANUAL, "title": "Other", "url": "javascript:alert(1)"},
                       headers=h).status_code == 422
    assert client.post("/api/jobs/manual", json={**MANUAL, "description": "short"},
                       headers=h).status_code == 422


def test_public_jobs_cannot_be_deleted_by_users(client, fixture_source):
    h = auth(client)
    client.post("/api/jobs/search", headers=h, json={"query": "python"})
    jid = client.get("/api/jobs", headers=h).json()["items"][0]["id"]
    assert client.delete(f"/api/jobs/{jid}", headers=h).status_code == 404
