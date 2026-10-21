"""CFSVA 2024 routers — additive only (no existing endpoint is modified).

Registered from main.py:
    from cfsva_api import router as cfsva_router
    app.include_router(cfsva_router)

Endpoints
---------
GET /api/cfsva/indicators         -> indicator catalog + national anchors
GET /api/cfsva/districts          -> all district rows (joined with region info)
GET /api/cfsva/districts/{ref}    -> one district row (id or name, any case)
GET /api/cfsva/metrics            -> dashboard row-feed in the EXACT /api/metrics
                                     contract (category "Food Security"), so the
                                     existing table/search/filter UIs consume it
                                     without a single change.
"""

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from insights_api import get_db
from seed_cfsva import ANCHORS

router = APIRouter(prefix="/api/cfsva", tags=["cfsva"])

CFSVA_YEAR = 2024
CFSVA_CATEGORY = "Food Security"

CFSVA_CATALOG = {
    "fies_moderate_severe_pct": ("Food Insecurity (moderate+severe)", "%"),
    "fies_severe_pct": ("Severe Food Insecurity", "%"),
    "food_consumption_score": ("Food Consumption Score", "pts"),
    "fcs_poor_pct": ("Poor Food Consumption", "%"),
    "hdds": ("Dietary Diversity (HDDS)", "pts"),
    "stunting_pct": ("Child Stunting", "%"),
    "wasting_pct": ("Child Wasting", "%"),
    "rcsi": ("Coping Strategies Index", "pts"),
    "harvest_loss_pct": ("Harvest Loss Exposure", "%"),
}
INDICATOR_DESCRIPTIONS = {
    "fies_moderate_severe_pct": "Households moderately or severely food insecure (CFSVA 2024 FIES; national food-secure baseline 83%)",
    "fies_severe_pct": "Households severely food insecure (CFSVA 2024 FIES baseline 1%)",
    "food_consumption_score": "Mean WFP Food Consumption Score (0-112; IPC nutrition bands)",
    "fcs_poor_pct": "Share of households with poor FCS (<28 points)",
    "hdds": "Mean Household Dietary Diversity Score (0-12 food groups)",
    "stunting_pct": "Under-five height-for-age <-2 SD (chronic malnutrition; national baseline 30%)",
    "wasting_pct": "Under-five weight-for-height <-2 SD (acute malnutrition)",
    "rcsi": "Reduced Coping Strategies Index for food access stress (lower is better)",
    "harvest_loss_pct": "Households reporting >=1 harvest loss last season",
}


FOOD_COLUMNS = tuple(CFSVA_CATALOG)

# OFFICIAL CFSVA 2024 national food-security status split (households):
# 83% food secure / 16% moderately insecure / 1% severely insecure.
NATIONAL_STATUS_SPLIT = {
    "food_secure_pct": 83.0,
    "moderately_insecure_pct": 16.0,
    "severely_insecure_pct": 1.0,
}


def _rows(db: Session, ref_sql: str, params: dict):
    cols_sql = ", ".join(f"t.{c}" for c in FOOD_COLUMNS)
    query = text(f"""
        SELECT r.province, r.district, r.area_type,
               t.survey_year{", " + cols_sql if cols_sql else ""}
        FROM district_cfsva_metrics t
        JOIN regions r ON t.region_id = r.id
        {ref_sql}
        ORDER BY r.province, r.district
    """)
    return db.execute(query, {"yr": CFSVA_YEAR, **params}).fetchall()


def _metric_rows(db: Session):
    row_sets = _rows(db, "", {})
    metrics = []
    for row in row_sets:
        for idx, (code, (name, unit)) in enumerate(CFSVA_CATALOG.items()):
            metrics.append({
                "province": row[0],
                "district": row[1],
                "area_type": row[2],
                "indicator_code": code,
                "indicator_name": name,
                "category": CFSVA_CATEGORY,
                "unit": unit,
                "survey_year": row[3],
                "value": float(row[4 + idx]) if row[4 + idx] is not None else None,
            })
    return metrics


@router.get("/indicators")
def cfsva_indicators(db: Session = Depends(get_db)):
    data = [{
        "indicator_code": code,
        "indicator_name": name,
        "unit": unit,
        "description": INDICATOR_DESCRIPTIONS[code],
        "national_anchor": ANCHORS[code],
        "survey_year": CFSVA_YEAR,
    } for code, (name, unit) in CFSVA_CATALOG.items()]
    return {
        "status": "success",
        "count": len(data),
        "national_status_split": NATIONAL_STATUS_SPLIT,
        "data": data,
    }


@router.get("/districts")
def cfsva_districts(db: Session = Depends(get_db)):
    rows = _rows(db, "", {})
    fields = list(FOOD_COLUMNS)
    data = [{
        "province": r[0],
        "district": r[1],
        "area_type": r[2],
        "survey_year": r[3],
        **{f: r[4 + i] for i, f in enumerate(fields)},
    } for r in rows]
    return {"status": "success", "count": len(data), "data": data}


@router.get("/metrics")
def cfsva_metrics(db: Session = Depends(get_db)):
    metrics = _metric_rows(db)
    return {"status": "success", "count": len(metrics), "data": metrics}


@router.get("/districts/{ref}")
def cfsva_district(ref: str, db: Session = Depends(get_db)):
    if isinstance(ref, int) or ref.isdigit():
        where = "WHERE r.id = :rid"
        params = {"rid": int(ref)}
    else:
        where = "WHERE LOWER(r.district) = LOWER(:name)"
        params = {"name": ref}
    row_set = _rows(db, where, params)
    if not row_set:
        return JSONResponse(
            status_code=404,
            content={
                "status": "error",
                "code": "cfsva_district_not_found",
                "detail": f"No CFSVA record matching '{ref}' for survey year {CFSVA_YEAR}.",
                "hint": "Seed the food-security layer: python3 seed_cfsva.py --url $DATABASE_URL",
            },
        )
    row = row_set[0]
    fields = list(FOOD_COLUMNS)
    return {
        "status": "success",
        "district": row[1],
        "province": row[0],
        "area_type": row[2],
        "survey_year": row[3],
        **{f: float(row[4 + i]) for i, f in enumerate(fields)},
        "national_anchors": ANCHORS,
    }
