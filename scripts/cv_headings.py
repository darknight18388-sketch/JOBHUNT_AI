"""Debug helper: prints short lines (likely section headings) from your latest uploaded CV's
extracted text, so you can see how headings look. Run from the backend folder:
    python ../scripts/cv_headings.py
Output may include your name line, so hide personal details before sharing it."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from sqlalchemy import select  # noqa: E402

import app.models  # noqa: E402,F401
from app.database.session import SessionLocal  # noqa: E402
from app.models.resume import Resume  # noqa: E402

with SessionLocal() as db:
    r = db.scalar(select(Resume).order_by(Resume.created_at.desc()))
    if not r:
        sys.exit("No resumes found")
    print(f"File type: {r.file_type}, characters: {len(r.extracted_text)}")
    for i, line in enumerate(r.extracted_text.splitlines()):
        t = line.strip()
        spaced = sum(len(w) == 1 for w in t.split()) >= 4
        if t and (spaced or (len(t.split()) <= 6 and not any(c.isdigit() for c in t) and "@" not in t)):
            print(f"{i:3d}: {t!r}{'   <-- letter-spaced' if spaced else ''}")
