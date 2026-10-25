"""Opportunity & Credit Matchmaker routers + inclusion dashboard.

Endpoints
---------
GET  /api/matchmaker/catalog       -> product catalog + profile enums
POST /api/matchmaker/recommendations -> explainable ranked products for a profile
GET  /api/inclusion/summary        -> FinScope 2024 national KPIs + health tiers
GET  /api/inclusion/districts      -> per-district inclusion & financial-health rows

Recommendations join `district_vup_metrics` and the canonical
FinScope/EICV7 `survey_metrics` vintage with `_load_metric_map` so every
reason cites the citizen's own district profile.
"""

from typing import Any, Optional

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import bindparam, text

from main import get_db
from insights_api import _load_metric_map, _load_national_means, _resolve_district
from models import as_float
import seed_vup
import matchmaker_engine
import product_catalog

router = APIRouter(prefix="/api", tags=["matchmaker"])

INCLUSION_CODES = [
    "financial_inclusion_rate", "formal_inclusion", "transactional_account",
    "mobile_money", "formal_credit", "formal_savings", "financial_exclusion_rate",
    "financial_health", "financially_coping", "financially_vulnerable",
    "extremely_vulnerable",
]

INCLUSION_LABELS = {
    "financial_inclusion_rate": ("Financial Inclusion Rate", 96.0),
    "formal_inclusion": ("Formal Inclusion", 92.0),
    "transactional_account": ("Transactional Accounts", 77.0),
    "mobile_money": ("Mobile Money Use", 77.0),
    "formal_credit": ("Formal Credit Use", 24.0),
    "formal_savings": ("Formal Savings", 59.0),
    "financial_exclusion_rate": ("Financial Exclusion", 4.0),
    "financial_health": ("Financially Healthy", 10.0),
    "financially_coping": ("Financially Coping", 57.0),
    "financially_vulnerable": ("Financially Vulnerable", 31.0),
    "extremely_vulnerable": ("Extremely Vulnerable", 3.0),
}


class RecommendationRequest(BaseModel):
    """Citizen profile (validated server-side; every field optional except defaults)."""

    district: Optional[str] = Field(None, max_length=64, description="district name or id; defaults to national")
    age_group: str = Field("adult", pattern="^(youth|adult)$")
    gender: Optional[str] = Field(None, pattern="^(female|male|prefer_not_to_say)$")
    occupation: str = Field("mixed", pattern="^(farmer|trader|artisan|service|wage|self_employed|unemployed|mixed)$")
    activity: Optional[str] = Field(None, pattern="^(agri|trade|service|artisan|wage|mixed)$")
    goal: str = Field(
        "expand",
        pattern="^(start|expand|agri_inputs|education|housing|safety_net|save_long|emergency_borrow)$",
    )
    has_phone: bool = True
    has_sacco_membership: bool = False
    urban: Optional[bool] = Field(None, description="defaults to the district's area type")
    top_n: int = Field(6, ge=1, le=12)

    @field_validator("district")
    @classmethod
    def _clean_district(cls, v):
        return v.strip() if isinstance(v, str) and v.strip() else v


def _district_context(db: Any, ref: Optional[str]):
    """Load the district's own stats to personalize the scoring context."""
    if ref:
        district, hint = _resolve_district(db, ref)
        if district is None:
            return None, hint
        metric_map, vintage_years = _load_metric_map(db, district["id"])
    else:
        metric_map, vintage_years = _load_national_means(db)
        district = {"district": "National", "province": "Rwanda", "id": None, "area_type": "national"}
    return {"district": district, "matches": {c: metric_map.get(c) for c in (
        "formal_credit", "mobile_money", "formal_savings", "financial_inclusion_rate",
        "financially_vulnerable", "poverty_headcount")},
        "vintage_years": vintage_years}, None


def _vup_poverty(db: Any, region_id: Optional[int]) -> Optional[float]:
    """Beneficiary poverty (district) — personalization signal for VUP windows."""
    if region_id is None:
        return None
    row = db.execute(text(
        "SELECT poverty_rate_among_beneficiaries FROM district_vup_metrics"
        " WHERE region_id = :rid AND survey_year = :yr"
    ), {"rid": region_id, "yr": seed_vup.VUP_YEAR}).first()
    return as_float(row[0]) if row and row[0] is not None else None


@router.get("/matchmaker/catalog")
def matchmaker_catalog():
    products = [{
        key: p[key] for key in (
            "id", "name", "provider", "category", "description", "requirements",
            "ticket_rwf", "tenure", "collateral", "digital", "evidence",
        )
    } for p in product_catalog.CATALOG]
    return {
        "status": "success",
        "count": len(products),
        "data": products,
        "profile_enums": product_catalog.PROFILE_ENUMS,
        "weights": matchmaker_engine.WEIGHTS,
        "note": "Indicative product terms; always confirm with the provider before onboarding.",
    }


@router.post("/matchmaker/recommendations")
def matchmaker_recommendations(profile: RecommendationRequest, db: Any = Depends(get_db)):
    context, hint = _district_context(db, profile.district)
    if context is None:
        return JSONResponse(status_code=404, content={
            "status": "error", "code": "district_not_found",
            "detail": f"No district matching '{profile.district}'.", "hint": hint,
        })
    district = context["district"]
    user_profile = profile.model_dump()
    urban_default = district.get("area_type") in ("urban", "mixed")
    user_profile["urban"] = user_profile["urban"] if user_profile["urban"] is not None else urban_default
    engine_context = {
        "district": district["district"],
        "matches": context["matches"],
        "poverty_among_beneficiaries": _vup_poverty(db, district.get("id")),
        "vintage_years": context["vintage_years"],
    }
    results = matchmaker_engine.match(user_profile, engine_context, top_n=profile.top_n)
    return {
        "status": "success",
        "profile": {
            "district": district["district"],
            "province": district.get("province"),
            "age_group": user_profile["age_group"],
            "gender": user_profile.get("gender"),
            "occupation": user_profile["occupation"],
            "goal": user_profile["goal"],
            "urban": user_profile["urban"],
        },
        "district_context": {
            "formal_credit": engine_context["matches"].get("formal_credit"),
            "mobile_money": engine_context["matches"].get("mobile_money"),
            "formal_savings": engine_context["matches"].get("formal_savings"),
            "financial_inclusion_rate": engine_context["matches"].get("financial_inclusion_rate"),
            "poverty_among_vup_beneficiaries": engine_context["poverty_among_beneficiaries"],
        },
        "results": results,
        "disclaimer": "Terms are indicative (static catalog). Verify with the provider; no financial advice is provided by this tool.",
    }


@router.get("/inclusion/summary")
def inclusion_summary(db: Any = Depends(get_db)):
    """FinScope 2024 national KPI block for the inclusion tab."""
    means, vintage_years = _load_national_means(db)
    national = {code: {
        "value": means.get(code),
        "label": INCLUSION_LABELS[code][0],
        "benchmark": INCLUSION_LABELS[code][1],
    } for code in INCLUSION_CODES if code in means}
    return {
        "status": "success",
        "scope": "national",
        "metric_count": len(national),
        "metrics": national,
        "health_tiers": {
            "healthy": means.get("financial_health"),
            "coping": means.get("financially_coping"),
            "vulnerable": means.get("financially_vulnerable"),
            "extremely_vulnerable": means.get("extremely_vulnerable"),
        },
        "vintage_years": {c: vintage_years.get(c) for c in INCLUSION_CODES if c in vintage_years},
    }


@router.get("/inclusion/districts")
def inclusion_districts(db: Any = Depends(get_db)):
    query = text("""
        SELECT r.province, r.district, r.area_type, r.population_weight, i.indicator_code,
               ROUND(CAST(sm.value AS numeric), 1) AS value
        FROM survey_metrics sm
        JOIN regions r ON sm.region_id = r.id
        JOIN indicators i ON sm.indicator_id = i.id
        WHERE i.indicator_code IN :codes
          AND sm.survey_year = (
              SELECT MAX(t.survey_year) FROM survey_metrics t
              WHERE t.region_id = sm.region_id AND t.indicator_id = sm.indicator_id
          )
        ORDER BY r.province, r.district, i.indicator_code
    """).bindparams(bindparam("codes", expanding=True))
    rows = db.execute(query, {"codes": INCLUSION_CODES}).fetchall()
    by_district: dict[str, dict] = {}
    for province, district, area_type, weight, code, value in rows:
        entry = by_district.setdefault(district, {
            "province": province, "area_type": area_type,
            "population_weight": as_float(weight), "metrics": {},
        })
        entry["metrics"][code] = as_float(value)
    data = [{"district": d, **payload} for d, payload in by_district.items()]
    return {"status": "success", "count": len(data), "data": data}
