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
