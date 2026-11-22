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


# Anonymised replica of a real PDF whose text came out with spaces inside words.
GARBLED = """Test Person
E D U C A T I O N
B E n g in Mech ani c a l E n g in ee rin g
University of Sunderland, UK (2026 - R)
C o mmu ni c ation : English, Tamil & Sinhala
HND in Mech ani c a l E n g in ee rin g
Pearson, UK (2024 - 2026)
Ce rti f i c at e in Au to m o b i le T ech ni c ian
Ceylon German Technical Training Institute, Sri Lanka (2017 - 2021)
P R O F E S S I O N A L
E X P E R I E N C E
Mechanical Engineering graduate with practical hands-on experience in maintenance, fault diagnosis, equipment inspection, and technical troubleshooting gained through industrial and automotive maintenance environments.
Phone: +94 77 000 0000
Email: test.person@example.com
WhatsApp: whatsapp/test
LinkedIn: linkedin.com/in/test
Sri Lanka Transport Board, Sri Lanka (SLTB)
Automobile Technician (Jan 2021 - Dec 2021)
Performed inspection, diagnosis, maintenance, and repair of mechanical, electrical, and electromechanical systems.
C E R T I F I C A T I O N S
N ationa l Ce rti f i c at e ( NVQ L evel 4 )
Automobile Mechanic - TVEC, Sri Lanka
Ce rti f i c at e o f P ro f i c i e n cy as Ski lle d C ra f ts m an
Automobile Mechanic - NAITA, Sri Lanka
Technical: Mechanical Maintenance & T roubleshootin g
Equipment I nspection & F ault Diagnosi s
AutoCAD & Solid W ork s
Preventive Maintenanc e
H ealth & Safety Procedure s
MA TL A B
Microsoft O ffice Suit e
Management: Customer Service & Active L istenin g
T ime Management & Prioritizatio n
"""


def test_garbled_pdf_text_still_finds_skills_languages_and_sections():
    d = parse_cv(GARBLED)
    assert {"AutoCAD", "SolidWorks", "MATLAB", "Preventive Maintenance", "Microsoft Office"} <= set(d["skills"])
    assert d["languages"] == ["English", "Tamil", "Sinhala"]
    everything = " ".join(d["education"] + d["experience"] + d["certifications"])
    assert "Phone" not in everything and "linkedin" not in everything.lower() and "@" not in everything
    assert not any("Communication" in e or "P R O F E S S" in e for e in d["education"])
    assert "Automobile Technician (Jan 2021 - Dec 2021)" in d["experience"]
    assert len(d["certifications"]) == 4  # the skills lines no longer leak into certifications
    assert not any(_frag in " ".join(d["skills"]) for _frag in ("T roubleshootin", "I nspection", "Diagnosi s"))
    assert "text_quality" in d["uncertain_fields"]  # the user is told the text is garbled
    assert d["email"] == "test.person@example.com" and d["phone"].startswith("+94 77")


def test_clean_cv_is_not_flagged_as_garbled():
    clean = ("Nimal Perera\nEDUCATION\nBSc Engineering in Mechanical Engineering, University of Moratuwa, "
             "graduated with honours in 2024\nEXPERIENCE\nTrainee Engineer at ABC Engineering where I assisted "
             "with preventive maintenance of workshop machinery and performed inspection and repair of "
             "mechanical systems each week\nSKILLS\nAutoCAD, SolidWorks, Python, R, C\n")
    d = parse_cv(clean)
    assert "text_quality" not in d["uncertain_fields"]
    assert {"R", "C"} <= set(d["skills"])  # short skills in a comma list are kept


def test_short_skills_are_not_matched_through_broken_words():
    d = parse_cv("Medi c al Ad visor and cadet leader\n")
    assert "CAD" not in d["skills"]


def test_language_lines():
    from app.parsers.cv_parser import _language_line
    assert _language_line("Languages: English (fluent), Sinhala")
    assert _language_line("Communication : English, Tamil & Sinhala")
    assert _language_line("English  •  Tamil  •  Sinhala")
    assert not _language_line("English")
    assert not _language_line("Communication: Excellent verbal and written skills")
    assert not _language_line("Fluent in English communication at work")
