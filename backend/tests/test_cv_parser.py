from app.parsers.cv_parser import parse_cv


def test_fuzzy_headings():
    text = """Nimal Perera
nimal@example.com
Educational Qualifications
BSc Engineering, University of Moratuwa
Work Experience:
Trainee Engineer, ABC Ltd
Industrial Training
Mechanical workshop trainee, 6 months
Professional Qualifications
NVQ Level 4 Welding
Key Skills
AutoCAD, SolidWorks
"""
    d = parse_cv(text)
    assert any("Moratuwa" in e for e in d["education"])
    assert any("ABC Ltd" in e for e in d["experience"])
    assert any("workshop trainee" in e for e in d["experience"])
    assert any("NVQ" in e for e in d["certifications"])
    assert {"AutoCAD", "SolidWorks"} <= set(d["skills"])


def test_inline_languages_and_skills():
    d = parse_cv("Nimal Perera\nLanguages: English, Sinhala, Tamil\nSkills: Python, Welding\n")
    assert d["languages"] == ["English", "Sinhala", "Tamil"]
    assert "Python" in d["skills"] and "Welding" in d["skills"]


def test_content_line_with_experience_word_is_not_a_heading():
    text = "Nimal Perera\nEXPERIENCE\n3 years experience in CAD design\nTrainee, ABC Ltd\n"
    d = parse_cv(text)
    assert "3 years experience in CAD design" in d["experience"]
    assert "Trainee, ABC Ltd" in d["experience"]


def test_skill_like_titles_do_not_end_sections():
    text = "SKILLS\nProject Management\nTeam Leadership\nEDUCATION\nBSc Engineering\n"
    d = parse_cv(text)
    assert "Project Management" in d["skills"]
    assert d["education"] == ["BSc Engineering"]


def test_letter_spaced_headings():
    text = """Nimal Perera
S K I L L S
AutoCAD, SolidWorks
L A N G U A G E S
English  •  Tamil  •  Sinhala
E D U C A T I O N
BSc Engineering, University of Moratuwa
W O R K   E X P E R I E N C E
Trainee Engineer, ABC Ltd
"""
    d = parse_cv(text)
    assert d["languages"] == ["English", "Tamil", "Sinhala"]
    assert any("Moratuwa" in e for e in d["education"])
    assert any("ABC Ltd" in e for e in d["experience"])
    assert {"AutoCAD", "SolidWorks"} <= set(d["skills"])


def test_wrapped_bullet_lines_are_merged():
    text = "KEY SKILLS\n• Mechanical maintenance &\ntroubleshooting\n• Preventive & corrective\nmaintenance\n"
    d = parse_cv(text)
    assert "Mechanical maintenance & troubleshooting" in d["skills"]
    assert "Preventive & corrective maintenance" in d["skills"]
    assert "troubleshooting" not in d["skills"]


def test_language_only_line_without_heading():
    d = parse_cv("Nimal Perera\nEnglish  •  Tamil  •  Sinhala\n")
    assert d["languages"] == ["English", "Tamil", "Sinhala"]


def test_language_fallback_does_not_fire_on_normal_text():
    d = parse_cv("Nimal Perera\nFluent in English communication at work\n")
    assert d["languages"] == []
