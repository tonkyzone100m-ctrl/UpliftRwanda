"""RDHS 2025 routers — additive only (no existing endpoint is modified).

Endpoints
---------
GET /api/rdhs/indicators         -> indicator catalog + population-weighted national means
GET /api/rdhs/districts          -> all district rows (joined with region info)
GET /api/rdhs/districts/{ref}    -> one district row (id or name, any case)
GET /api/rdhs/metrics            -> dashboard row-feed in the EXACT /api/metrics
                                    contract (category "Living Standards (RDHS
                                    2025)"), so the existing table/search/filter
                                    UIs consume it without a single change.

Source: RWHR91FL (household recode) + RWBR91FL (birth recode), aggregated by
preprocess_rdhs.py into db/rdhs/rdhs_2025_district_panel.json and seeded into
`district_rdhs_metrics` by seed_rdhs.py. All shares use hv005/v005 DHS weights.
"""

from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from insights_api import get_db
import seed_rdhs

router = APIRouter(prefix="/api/rdhs", tags=["rdhs"])

RDHS_YEAR = 2025
RDHS_CATEGORY = "Living Standards (RDHS 2025)"

# code -> (indicator name, unit). Drives the long/tidy /api/rdhs row-feed.
RDHS_CATALOG = {
    "electricity_pct": ("Electricity Access", "%"),
    "improved_water_pct": ("Improved Water Source", "%"),
    "improved_sanitation_pct": ("Improved Sanitation", "%"),
    "bank_account_pct": ("Bank Account", "%"),
    "mobile_fintech_pct": ("Mobile Money / Fintech Use", "%"),
    "mobile_phone_pct": ("Mobile Phone Ownership", "%"),
    "insurance_pct": ("Health Insurance Coverage", "%"),
    "urban_pct": ("Urban Households", "%"),
    "wealth_p20_pct": ("Wealth: Poorest Quintile Share", "%"),
    "wealth_p40_pct": ("Wealth: Bottom 40% Share", "%"),
    "wealth_p60p_pct": ("Wealth: Top 60% Share", "%"),
    "imr_per_1000": ("Infant Mortality (IMR)", "per 1,000"),
    "u5mr_per_1000": ("Under-5 Mortality (U5MR)", "per 1,000"),
    "stunting_pct": ("Child Stunting", "%"),
    "underweight_pct": ("Child Underweight", "%"),
    "wasting_pct": ("Child Wasting", "%"),
    "households": ("Households Sampled", "count"),
}

INDICATOR_DESCRIPTIONS = {
    "electricity_pct": "Households with electricity (hv206=1), DHS-weights",
    "improved_water_pct": "Households with an improved drinking-water source (WHO/JMP grouping, hv201)",
    "improved_sanitation_pct": "Households with improved non-shared sanitation (WHO/JMP grouping, hv205)",
    "bank_account_pct": "Households with a bank account (hv247=1) — financial inclusion headline",
    "mobile_fintech_pct": "Households using a phone for financial transactions (hv263=1) — mobile money",
    "mobile_phone_pct": "Households owning a mobile phone (hv243a=1)",
    "insurance_pct": "Households with any member insured across the SH21 health-insurance battery",
    "urban_pct": "Households in urban clusters (hv025=1)",
    "wealth_p20_pct": "Share of households in the poorest wealth quintile (hv270=1) — pro-poor lens",
    "wealth_p40_pct": "Wealth share of the bottom 40% (quintiles 1+2) — NST2/Vision 2050 prosperity-sharing proxy",
    "wealth_p60p_pct": "Wealth share of the top 60% (quintiles 3+4+5)",
    "imr_per_1000": "Infant deaths per 1,000 live births — direct complete-exposure cohort from birth history",
    "u5mr_per_1000": "Under-five deaths per 1,000 live births — complete-exposure cohort (conservative vs official synthetic tables)",
    "stunting_pct": "Under-five height-for-age <-2 SD (chronic malnutrition)",
    "underweight_pct": "Under-five weight-for-age <-2 SD",
    "wasting_pct": "Under-five weight-for-height <-2 SD (acute malnutrition)",
    "households": "Household questionnaire records in the recode for the district",
}

# Metric columns exactly as stored in district_rdhs_metrics.
HOUSEHOLD_COLUMNS = tuple(RDHS_CATALOG)


def _method_notes() -> dict[str, Any]:
    """Method block from the committed panel (in-process cache, resilient)."""
    try:
        payload = seed_rdhs.load_panel()
        return payload.get("method", {})
    except Exception:
        return {}


def _rows(db: Session, ref_sql: str, params: dict):
    cols_sql = ", ".join(f"t.{c}" for c in HOUSEHOLD_COLUMNS)
    query = text(f"""
        SELECT r.province, r.district, r.area_type,
               t.survey_year{", " + cols_sql if cols_sql else ""}
        FROM district_rdhs_metrics t
        JOIN regions r ON t.region_id = r.id
        WHERE t.survey_year = :yr
        {ref_sql}
        ORDER BY r.province, r.district
    """)
    return db.execute(query, {"yr": RDHS_YEAR, **params}).fetchall()


def _metric_rows(db: Session):
    row_sets = _rows(db, "", {})
    metrics = []
    for row in row_sets:
        for idx, (code, (name, unit)) in enumerate(RDHS_CATALOG.items()):
            raw = row[4 + idx]
            metrics.append({
                "province": row[0],
                "district": row[1],
                "area_type": row[2],
                "indicator_code": code,
                "indicator_name": name,
                "category": RDHS_CATEGORY,
                "unit": unit,
                "survey_year": row[3],
                "value": float(raw) if raw is not None else None,
            })
    return metrics


def _national_means(db: Session) -> dict[str, float | None]:
    """Population-weighted national mean per catalog column (single query)."""
    weighted = ", ".join(
        f"SUM(t.{code} * r.population_weight) / SUM(r.population_weight) AS {code}"
        for code in HOUSEHOLD_COLUMNS
    )
    query = text(f"""
        SELECT {weighted}
        FROM district_rdhs_metrics t JOIN regions r ON t.region_id = r.id
        WHERE t.survey_year = :yr
    """)
    row = db.execute(query, {"yr": RDHS_YEAR}).fetchone()
    return {code: (float(row[idx]) if row[idx] is not None else None)
            for idx, code in enumerate(HOUSEHOLD_COLUMNS)}


@router.get("/indicators")
def rdhs_indicators(db: Session = Depends(get_db)):
    means = _national_means(db)
    data = [{
        "indicator_code": code,
        "indicator_name": name,
        "unit": unit,
        "description": INDICATOR_DESCRIPTIONS[code],
        "national_mean": means.get(code),
        "survey_year": RDHS_YEAR,
    } for code, (name, unit) in RDHS_CATALOG.items()]
    return {
        "status": "success",
        "count": len(data),
        "survey": seed_rdhs.SURVEY_NAME,
        "method": _method_notes(),
        "data": data,
    }


@router.get("/districts")
def rdhs_districts(db: Session = Depends(get_db)):
    rows = _rows(db, "", {})
    fields = list(HOUSEHOLD_COLUMNS)
    data = [{
        "province": r[0],
        "district": r[1],
        "area_type": r[2],
        "survey_year": r[3],
        **{f: (float(r[4 + i]) if r[4 + i] is not None else None) for i, f in enumerate(fields)},
    } for r in rows]
    counts = {"districts": len(data)}
    if data:
        counts["households"] = int(sum((d["households"] or 0) for d in data))
    return {"status": "success", "count": len(data), "counts": counts, "method": _method_notes(), "data": data}


@router.get("/metrics")
def rdhs_metrics(db: Session = Depends(get_db)):
    metrics = _metric_rows(db)
    return {"status": "success", "count": len(metrics), "data": metrics}


@router.get("/districts/{ref}")
def rdhs_district(ref: str, db: Session = Depends(get_db)):
    if ref.isdigit():
        where = "AND r.id = :rid"
        params = {"rid": int(ref)}
    else:
        where = "AND LOWER(r.district) = LOWER(:name)"
        params = {"name": ref}
    row_set = _rows(db, where, params)
    if not row_set:
        return JSONResponse(
            status_code=404,
            content={
                "status": "error",
                "code": "rdhs_district_not_found",
                "detail": f"No RDHS 2025 record matching '{ref}' for survey year {RDHS_YEAR}.",
                "hint": "Seed the RDHS layer: python3 seed_rdhs.py --url $DATABASE_URL",
            },
        )
    row = row_set[0]
    fields = list(HOUSEHOLD_COLUMNS)
    return {
        "status": "success",
        "district": row[1],
        "province": row[0],
        "area_type": row[2],
        "survey_year": row[3],
        **{f: (float(row[4 + i]) if row[4 + i] is not None else None) for i, f in enumerate(fields)},
        "method": _method_notes(),
    }
