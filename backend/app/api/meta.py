from urllib.parse import quote_plus, urlencode

from fastapi import APIRouter, Query

from app.core.countries import COUNTRIES, valid_country

router = APIRouter(prefix="/api", tags=["meta"])

JOB_TITLES = {
    "Engineering & Technical": [
        "Mechanical Engineer", "Maintenance Engineer", "Production Engineer", "Service Engineer",
        "Trainee Engineer", "Design Engineer (CAD)", "Project Engineer", "Quality Engineer",
        "Industrial Engineer", "Electrical Engineer", "Civil Engineer", "Mechanical Technician",
        "Automotive Technician", "Maintenance Technician", "HVAC Technician", "Welder",
        "CNC Operator", "Health & Safety Officer",
    ],
    "IT & Software": [
        "Software Engineer", "Web Developer", "QA Engineer", "Data Analyst", "DevOps Engineer",
        "IT Support Engineer", "Network Engineer", "UI/UX Designer", "Business Analyst",
    ],
    "Business & Administration": [
        "Accountant", "Finance Executive", "Marketing Executive", "HR Executive", "Sales Executive",
        "Customer Service Representative", "Administrative Assistant", "Project Manager",
        "Logistics Executive", "Procurement Officer", "Store Keeper",
    ],
    "Other": [
        "Teacher", "Nurse", "Driver", "Graphic Designer", "Hospitality Executive",
    ],
}


@router.get("/countries")
def countries():
    return [{"code": "ALL", "name": "All countries"}] + [
        {"code": c, "name": n} for c, n in sorted(COUNTRIES.items(), key=lambda x: x[1])]


@router.get("/job-titles")
def job_titles():
    return [{"group": g, "titles": t} for g, t in JOB_TITLES.items()]


def _google(q: str) -> str:
    return "https://www.google.com/search?q=" + quote_plus(q)


@router.get("/job-sites")
def job_sites(country: str = Query("ALL", max_length=8), query: str = Query("", max_length=100),
              location: str = Query("", max_length=100)):
    """Ready-made search links for sites that do not allow automated collection. They open the
    site's own results in a new tab; this app does not read or store anything from them."""
    if not valid_country(country):
        country = "ALL"
    q = query.strip()
    place = " ".join(x for x in (location.strip(), COUNTRIES.get(country, "")) if x)
    links = [{"name": "LinkedIn Jobs", "url": "https://www.linkedin.com/jobs/search/?" +
              urlencode({"keywords": q, "location": place or "Worldwide"})}]
    if country in ("LK", "ALL"):
        for name, domain in (("TopJobs.lk", "topjobs.lk"), ("ikman.lk jobs", "ikman.lk"),
                             ("Xpress.jobs", "xpress.jobs")):
            links.append({"name": name, "url": _google(f"{q} jobs site:{domain}".strip())})
    links.append({"name": "Indeed", "url": _google(f"{q} jobs {place} site:indeed.com".strip())})
    links.append({"name": "Google Jobs", "url": _google(f"{q} jobs {place}".strip())})
    return links
