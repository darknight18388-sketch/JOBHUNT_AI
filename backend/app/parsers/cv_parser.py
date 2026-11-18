"""Deterministic, rule-based CV parser. Only returns facts present in the CV text.
Uncertain fields are flagged so the user must confirm them."""
import re

SKILLS = [
    "Python", "Java", "JavaScript", "TypeScript", "React", "Node.js", "SQL", "PostgreSQL",
    "MySQL", "MongoDB", "HTML", "CSS", "Git", "Docker", "Linux", "C++", "C#", "PHP",
    "FastAPI", "Django", "Flask", "Excel", "Microsoft Office", "PowerPoint", "AutoCAD",
    "SolidWorks", "CATIA", "ANSYS", "MATLAB", "CAD", "CAM", "CNC", "Welding", "Machining",
    "Preventive Maintenance", "Maintenance", "Workshop", "Hydraulics", "Pneumatics",
    "Thermodynamics", "Fluid Mechanics", "HVAC", "PLC", "Project Management",
    "Data Analysis", "Machine Learning", "Networking", "Cybersecurity", "Accounting",
    "Communication", "Teamwork", "Leadership", "Problem Solving", "Customer Service",
]
_SKILL_RES = [
    (s, re.compile(r"(?<![A-Za-z0-9+#.])" + re.escape(s) + r"(?![A-Za-z0-9+#])", re.I))
    for s in SKILLS
]

HEADINGS = {
    "education": {"education", "academic qualifications", "educational qualifications",
                  "academic background"},
    "experience": {"experience", "work experience", "professional experience",
                   "employment history", "employment", "internship", "internships",
                   "work history"},
    "certifications": {"certifications", "certification", "certificates", "courses",
                       "training", "professional qualifications"},
    "skills": {"skills", "technical skills", "key skills", "core skills", "skills summary"},
    "languages": {"languages", "language skills"},
    "other": {"references", "referees", "summary", "profile", "objective",
              "career objective", "personal details", "personal information", "projects",
              "interests", "hobbies", "declaration", "achievements",
              "extracurricular activities"},
}
_HEADING_LOOKUP = {h: k for k, hs in HEADINGS.items() for h in hs}
LANGUAGES = ["English", "Sinhala", "Tamil", "Hindi", "French", "German", "Japanese",
             "Chinese", "Arabic", "Spanish"]

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"\+?\d[\d\s\-()]{7,}\d")
BULLETS = "•-*–·▪●◦ \t"


_FUZZY = [
    ("experience", ["experience", "employment", "internship", "work history",
                    "career history", "industrial training", "work placement"]),
    ("certifications", ["certif", "professional qualification"]),
    ("education", ["education", "academic", "qualification"]),
    ("languages", ["language"]),
    ("skills", ["skills", "competenc"]),
    ("other", ["profile", "summary", "objective", "reference", "referee", "personal",
               "hobb", "declaration", "achievement", "extracurricular"]),
]
_CONNECTORS = {"and", "&", "of", "the", "in", "for"}
INLINE_RE = re.compile(
    r"^\s*(languages?|language skills|technical skills|key skills|core skills|skills|"
    r"certifications?|certificates)\s*[:\-\u2013\u2014]\s*(\S.*)$", re.I)


def _classify(text: str):
    t = re.sub(r"\s+", " ", text.strip().strip(":-\u2013\u2014\u2022*_|#").strip().lower())
    if t in _HEADING_LOOKUP:
        return _HEADING_LOOKUP[t]
    for key, kws in _FUZZY:
        if any(kw in t for kw in kws):
            return key
    return None


def _looks_like_heading(line: str) -> bool:
    s = line.strip().strip(":-\u2013\u2014\u2022*_|#").strip()
    if not s or len(s) > 50 or len(s.split()) > 5:
        return False
    if any(c.isdigit() for c in s) or "," in s or "@" in s:
        return False
    if s.isupper() or line.rstrip().endswith(":"):
        return True
    words = s.replace(":", " ").split()
    return all(w[0].isupper() or w.lower() in _CONNECTORS for w in words)


def _heading(line: str):
    t = line.strip().strip(":").strip().lower()
    if t in _HEADING_LOOKUP:
        return _HEADING_LOOKUP[t]
    return _classify(line) if _looks_like_heading(line) else None


def _clean(line: str) -> str:
    return line.strip().lstrip(BULLETS).strip()[:300]


def _sections(lines):
    out, cur = {}, None
    for line in lines:
        m = INLINE_RE.match(line)
        if m and (key := _classify(m.group(1))):
            cur = key
            out.setdefault(cur, [])
            c = _clean(m.group(2))
            if len(c) >= 3:
                out[cur].append(c)
            continue
        h = _heading(line)
        if h:
            cur = h
            out.setdefault(cur, [])
        elif cur and line.strip():
            c = _clean(line)
            if len(c) >= 3:
                out[cur].append(c)
    return out


def _name(lines):
    for line in [l.strip() for l in lines if l.strip()][:5]:
        words = line.split()
        if (1 <= len(words) <= 5 and len(line) <= 60 and "@" not in line
                and not any(c.isdigit() for c in line) and not _heading(line)):
            return line
    return ""


def parse_cv(text: str) -> dict:
    lines = text.splitlines()
    sec = _sections(lines)

    email = (EMAIL_RE.search(text) or [""])[0] if EMAIL_RE.search(text) else ""
    phone = ""
    for m in PHONE_RE.finditer(text):
        if 9 <= sum(c.isdigit() for c in m.group()) <= 15:
            phone = m.group().strip()
            break

    skills, seen = [], set()

    def add(s):
        k = s.lower()
        if k and k not in seen and len(s) <= 60:
            seen.add(k)
            skills.append(s)

    for name, rx in _SKILL_RES:
        if rx.search(text):
            add(name)
    for entry in sec.get("skills", []):
        for part in re.split(r"[,;|•]", entry):
            add(part.strip().lstrip(BULLETS).strip())
    skills = skills[:60]

    lang_text = " ".join(sec.get("languages", []))
    languages = [l for l in LANGUAGES if re.search(rf"\b{l}\b", lang_text, re.I)]

    data = {
        "full_name": _name(lines),
        "email": email,
        "phone": phone,
        "skills": skills,
        "education": sec.get("education", [])[:30],
        "experience": sec.get("experience", [])[:30],
        "certifications": sec.get("certifications", [])[:30],
        "languages": languages,
    }
    uncertain = [k for k in ("full_name", "email", "phone", "skills", "education",
                             "experience", "languages") if not data[k]]
    data["uncertain_fields"] = uncertain
    return data
