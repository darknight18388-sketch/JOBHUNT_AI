import io
import zipfile
from pathlib import Path

from app.core.config import settings

CV_LINES = [
    "Nimal Perera",
    "nimal.perera@example.com | +94 77 123 4567",
    "EDUCATION",
    "BSc Engineering in Mechanical Engineering, University of Moratuwa",
    "SKILLS",
    "AutoCAD, SolidWorks, Preventive Maintenance, Python",
    "LANGUAGES",
    "English, Sinhala",
    "EXPERIENCE",
    "Trainee Engineer, ABC Ltd, 2024",
    "CERTIFICATIONS",
    "NVQ Level 4 Welding",
]


def make_docx(lines=CV_LINES) -> bytes:
    body = "".join(f"<w:p><w:r><w:t>{l}</w:t></w:r></w:p>" for l in lines)
    xml = ('<?xml version="1.0" encoding="UTF-8"?>'
           '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
           f"<w:body>{body}</w:body></w:document>")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("word/document.xml", xml)
    return buf.getvalue()


def make_pdf(lines) -> bytes:
    stream = "BT /F1 12 Tf 50 750 Td 14 TL " + " ".join(f"({l}) Tj T*" for l in lines) + " ET"
    objs = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        "/Contents 5 0 R /Resources << /Font << /F1 4 0 R >> >> >>",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream",
    ]
    out = b"%PDF-1.4\n"
    offsets = []
    for i, o in enumerate(objs, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n{o}\nendobj\n".encode()
    xref = len(out)
    out += f"xref\n0 {len(objs)+1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objs)+1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode()
    return out


def auth(client, email):
    client.post("/api/auth/register", json={"email": email, "password": "StrongPass123"})
    t = client.post("/api/auth/login", json={"email": email, "password": "StrongPass123"})
    return {"Authorization": f"Bearer {t.json()['access_token']}"}


def upload(client, h, name="cv.docx", data=None, mime="application/octet-stream"):
    data = make_docx() if data is None else data
    return client.post("/api/resumes/upload", files={"file": (name, data, mime)}, headers=h)


def test_requires_auth(client):
    assert client.get("/api/resumes").status_code == 401
    assert client.post("/api/resumes/upload",
                       files={"file": ("a.docx", b"x")}).status_code == 401


def test_upload_and_analyze_docx(client):
    h = auth(client, "a@example.com")
    r = upload(client, h)
    assert r.status_code == 201
    rid = r.json()["id"]
    a = client.post(f"/api/resumes/{rid}/analyze", headers=h).json()
    assert a["email"] == "nimal.perera@example.com"
    assert a["full_name"] == "Nimal Perera"
    assert "+94 77 123 4567" in a["phone"]
    assert {"AutoCAD", "SolidWorks", "Python"} <= set(a["skills"])
    assert a["languages"] == ["English", "Sinhala"]
    assert any("Moratuwa" in e for e in a["education"])
    assert a["confirmed"] is False


def test_upload_and_analyze_pdf(client):
    h = auth(client, "a@example.com")
    pdf = make_pdf(["Nimal Perera", "nimal.perera@example.com", "SKILLS",
                    "Python, AutoCAD, SolidWorks"])
    r = upload(client, h, "cv.pdf", pdf, "application/pdf")
    assert r.status_code == 201
    a = client.post(f"/api/resumes/{r.json()['id']}/analyze", headers=h).json()
    assert a["email"] == "nimal.perera@example.com"
    assert "Python" in a["skills"]


def test_missing_fields_flagged_not_invented(client):
    h = auth(client, "a@example.com")
    r = upload(client, h, data=make_docx(["Some random text without any real CV data in it."]))
    a = client.post(f"/api/resumes/{r.json()['id']}/analyze", headers=h).json()
    assert a["email"] == "" and a["phone"] == "" and a["skills"] == []
    assert "email" in a["uncertain_fields"] and "skills" in a["uncertain_fields"]


def test_rejects_wrong_extension(client):
    h = auth(client, "a@example.com")
    assert upload(client, h, "cv.txt", b"hello world", "text/plain").status_code == 400


def test_rejects_fake_pdf(client):
    h = auth(client, "a@example.com")
    assert upload(client, h, "cv.pdf", b"just text pretending", "application/pdf").status_code == 400


def test_rejects_corrupt_docx(client):
    h = auth(client, "a@example.com")
    assert upload(client, h, "cv.docx", b"PK\x03\x04garbage-not-a-zip").status_code == 400


def test_rejects_empty_and_oversized(client):
    h = auth(client, "a@example.com")
    assert upload(client, h, "cv.pdf", b"").status_code == 400
    big = b"%PDF-" + b"0" * (settings.max_upload_mb * 1024 * 1024 + 10)
    assert upload(client, h, "cv.pdf", big, "application/pdf").status_code == 413


def test_user_cannot_access_other_users_cv(client):
    ha, hb = auth(client, "a@example.com"), auth(client, "b@example.com")
    rid = upload(client, ha).json()["id"]
    client.post(f"/api/resumes/{rid}/analyze", headers=ha)
    assert client.get(f"/api/resumes/{rid}", headers=hb).status_code == 404
    assert client.post(f"/api/resumes/{rid}/analyze", headers=hb).status_code == 404
    assert client.get(f"/api/resumes/{rid}/analysis", headers=hb).status_code == 404
    assert client.put(f"/api/resumes/{rid}/analysis", json={}, headers=hb).status_code == 404
    assert client.delete(f"/api/resumes/{rid}", headers=hb).status_code == 404
    assert client.get("/api/resumes", headers=hb).json() == []
    assert len(client.get("/api/resumes", headers=ha).json()) == 1


def test_edit_confirm_and_delete(client):
    h = auth(client, "a@example.com")
    rid = upload(client, h).json()["id"]
    client.post(f"/api/resumes/{rid}/analyze", headers=h)
    body = {"full_name": "Nimal P.", "skills": ["Python", " Welding "], "confirmed": True}
    r = client.put(f"/api/resumes/{rid}/analysis", json=body, headers=h).json()
    assert r["confirmed"] is True and r["uncertain_fields"] == []
    assert r["skills"] == ["Python", "Welding"]
    assert client.get(f"/api/resumes/{rid}/analysis", headers=h).json()["full_name"] == "Nimal P."

    d = Path(settings.upload_dir)
    assert any(d.iterdir())
    assert client.delete(f"/api/resumes/{rid}", headers=h).status_code == 204
    assert client.get(f"/api/resumes/{rid}", headers=h).status_code == 404
    assert not any(d.iterdir())
