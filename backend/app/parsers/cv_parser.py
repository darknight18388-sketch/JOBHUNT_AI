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
    "skills": {"skills", "technical skills", "key skills", "core skills", "skills summary", "technical",
               "management", "soft skills", "professional skills", "core competencies",
               "competencies", "areas of expertise", "expertise"},
    "languages": {"languages", "language skills"},
    "other": {"references", "referees", "summary", "profile", "objective", "professional",
              "professional summary", "professional profile", "personal profile", "about me",
              "career objective", "personal details", "personal information", "projects",
              "interests", "hobbies", "declaration", "achievements",
              "extracurricular activities"},
}
_HEADING_LOOKUP = {h: k for k, hs in HEADINGS.items() for h in hs}
_HEADING_COMPACT = {re.sub(r"\s+", "", h): k for h, k in _HEADING_LOOKUP.items()}
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
    r"^\s*(languages?|language skills|technical skills|key skills|core skills|skills|technical|management|"
    r"soft skills|professional skills|core competencies|competencies|certifications?|certificates)"
    r"\s*[:\-\u2013\u2014]\s*(\S.*)$", re.I)


def _despace(line: str) -> str:
    """Join letter-spaced text such as 'E D U C A T I O N' into 'EDUCATION'."""
    out = []
    for chunk in re.split(r"\s{2,}", line.strip()):
        toks = chunk.split(" ")
        out.append("".join(toks) if len(toks) >= 3 and all(len(t) == 1 for t in toks) else chunk)
    return " ".join(out)


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
    line = _despace(line)
    t = line.strip().strip(":").strip().lower()
    if t in _HEADING_LOOKUP:
        return _HEADING_LOOKUP[t]
    compact = re.sub(r"\s+", "", t)  # headings broken like "E d u c a t i o n" or "Ce rti f i c at e s"
    if 3 <= len(compact) <= 30 and compact in _HEADING_COMPACT:
        return _HEADING_COMPACT[compact]
    return _classify(line) if _looks_like_heading(line) else None


COMMON_SHORT = {"a", "an", "am", "as", "at", "be", "by", "do", "go", "he", "if", "in", "is", "it", "me", "my",
                "no", "of", "on", "or", "so", "to", "up", "us", "we", "ai", "ml", "hr", "qa", "ui", "ux", "pc",
                "uk", "sl", "lk", "id", "tv", "ms", "mr", "dr"}
CONTACT_RE = re.compile(r"^\s*(phone|mobile|tel|telephone|email|e-mail|whatsapp|linkedin|github|address|"
                        r"website|portfolio)\b", re.I)
LANG_NAMES = {l.lower() for l in LANGUAGES}
LANG_LABELS = {"communication", "languages", "language", "languageskills"}
FRAGMENTATION_LIMIT = 0.12


def _compact(s: str) -> str:
    return re.sub(r"[^a-z0-9+#]", "", s.lower())


def _short_ratio(text: str) -> tuple[int, int]:
    toks = re.findall(r"[A-Za-z]+", text)
    return sum(1 for t in toks if len(t) <= 2 and t.lower() not in COMMON_SHORT), len(toks)


def _fragmented(s: str) -> bool:
    """True for text with spaces inside words, e.g. 'T roubleshootin g'."""
    short, n = _short_ratio(s)
    return n >= 3 and short / n > 0.3


def _text_fragmentation(text: str) -> float:
    short, n = _short_ratio(text)
    return short / n if n >= 30 else 0.0


def _is_contact(line: str) -> bool:
    low = line.lower()
    return bool(CONTACT_RE.match(line)) or "@" in line or "linkedin.com" in low or "github.com" in low


def _language_line(line: str) -> bool:
    """'English  •  Tamil  •  Sinhala' or 'Communication : English, Tamil & Sinhala' (also with
    spaces inside the label). Only lines made up of language names count."""
    body, labelled = line, False
    if ":" in line:
        left, right = line.split(":", 1)
        if re.sub(r"\s+", "", left).lower() in LANG_LABELS:
            body, labelled = right, True
    parts = [re.sub(r"\(.*?\)", "", p).strip(" .") for p in re.split(r"[,;|\u2022/&]|\band\b", body, flags=re.I)]
    parts = [p for p in parts if p]
    return len(parts) >= (1 if labelled else 2) and all(p.lower() in LANG_NAMES for p in parts)


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
            stripped = line.strip()
            is_bullet = stripped[0] in BULLETS
            if not is_bullet and stripped[0].islower() and out[cur]:
                # wrapped continuation of the previous line
                out[cur][-1] = (out[cur][-1] + " " + stripped)[:300]
                continue
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
    body, lang_lines = [], []
    for line in lines:
        if _language_line(line):
            lang_lines.append(line)      # a languages line, wherever it sits
        elif not _is_contact(line):      # phone / email / links are not education or experience
            body.append(line)
    sec = _sections(body)

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

    compact_text = _compact(text)
    for name, rx in _SKILL_RES:
        if rx.search(text):
            add(name)
        elif len(_compact(name)) >= 6 and _compact(name) in compact_text:
            add(name)  # PDF text with spaces inside words: 'Solid W ork s' -> SolidWorks
    for entry in sec.get("skills", []):
        for part in re.split(r"[,;|•]", entry):
            part = part.strip().lstrip(BULLETS).strip()
            if part and not _fragmented(part):
                add(part)
    skills = skills[:60]

    lang_text = " ".join(sec.get("languages", []) + lang_lines)
    found = [(m.start(), l) for l in LANGUAGES
             if (m := re.search(rf"\b{l}\b", lang_text, re.I))]
    languages = [l for _, l in sorted(found)]  # keep the order used in the CV

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
    if _text_fragmentation(text) > FRAGMENTATION_LIMIT:
        uncertain.append("text_quality")  # extracted text is garbled: ask the user to check everything
    data["uncertain_fields"] = uncertain
    return data
