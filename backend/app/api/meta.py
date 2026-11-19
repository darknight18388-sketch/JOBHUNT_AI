from fastapi import APIRouter

from app.core.countries import COUNTRIES

router = APIRouter(prefix="/api", tags=["meta"])


@router.get("/countries")
def countries():
    return [{"code": "ALL", "name": "All countries"}] + [
        {"code": c, "name": n} for c, n in sorted(COUNTRIES.items(), key=lambda x: x[1])]
