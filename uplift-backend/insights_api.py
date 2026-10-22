"""Analytics + policy-engine endpoints for UpliftRwanda.

Endpoints
---------
    GET /api/districts               district index (ids + province + weights)
    GET /api/indicators              indicator catalog with official benchmarks
    GET /api/districts/{ref}/insights   automated policy engine for one district
    GET /api/insights/national          population-weighted national policy view
"""

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from auth import get_current_admin
from models import as_int, as_float
from policy import generate_insights
from targets import effective_targets

router = APIRouter(prefix="/api", tags=["insights"])

# Official NISR FinScope 2024 / EICV7 benchmarks echoed by insight endpoints
OFFICIAL_BENCHMARKS = {
    "financial_inclusion_rate": 96.0,
    "transactional_account": 77.0,
    "mobile_money": 77.0,
    "financial_exclusion_rate": 4.0,
    "formal_credit": 24.0,
    "formal_savings": 59.0,
    "poverty_headcount": 27.4,
    "extreme_poverty_rate": 4.5,
    "social_protection": 61.3,
    "climate_shock": 69.0,
    "financial_health": 10.0,
    "financially_coping": 57.0,
    "financially_vulnerable": 31.0,
    "extremely_vulnerable": 3.0,
}

SURVEY_YEAR = 2024

DISTRICT_INDEX_QUERY = text("""
    SELECT r.id, r.district, r.province, r.area_type, r.population_weight,
           (SELECT COUNT(*) FROM survey_metrics sm WHERE sm.region_id = r.id) AS metric_count
    FROM regions r
    ORDER BY r.province, r.district;
""")

INDICATOR_QUERY = text("""
    SELECT i.id, i.indicator_code, i.indicator_name, i.category, i.unit, i.description
    FROM indicators i
    ORDER BY i.id;
""")


def get_db():
    """Late binding so monkeypatching main.SessionLocal covers insight routes too."""
    from main import SessionLocal

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/districts")
def list_districts(db: Session = Depends(get_db)):
    rows = db.execute(DISTRICT_INDEX_QUERY).fetchall()
    data = [{
        "id": row[0],
        "district": row[1],
        "province": row[2],
        "area_type": row[3],
        "population_weight": as_float(row[4]),
        "metric_count": as_int(row[5]),
    } for row in rows]
    return {"status": "success", "count": len(data), "data": data}


@router.get("/indicators")
def list_indicators(db: Session = Depends(get_db)):
    rows = db.execute(INDICATOR_QUERY).fetchall()
    data = [{
        "id": row[0],
        "indicator_code": row[1],
        "indicator_name": row[2],
        "category": row[3],
        "unit": row[4],
        "description": row[5],
        "official_benchmark": OFFICIAL_BENCHMARKS.get(row[1]),
    } for row in rows]
    return {"status": "success", "count": len(data), "data": data}


def _resolve_district(db, ref):
    """Accepts a numeric region id or a case-insensitive district name."""
    if isinstance(ref, int) or (isinstance(ref, str) and ref.isdigit()):
        query = text(
            "SELECT id, district, province, area_type, population_weight "
            "FROM regions WHERE id = :ref"
        )
        params = {"ref": int(ref)}
    else:
        query = text(
            "SELECT id, district, province, area_type, population_weight "
            "FROM regions WHERE LOWER(district) = LOWER(:ref)"
        )
        params = {"ref": ref}
    row = db.execute(query, params).first()
    if row is None:
        districts = [d for (d,) in db.execute(text("SELECT district FROM regions ORDER BY district")).fetchall()]
        hint = ", ".join(districts[:6]) + f" ... ({len(districts)} total; /api/districts lists all)"
        return None, hint
    return {
        "id": row[0],
        "district": row[1],
        "province": row[2],
        "area_type": row[3],
        "population_weight": as_float(row[4]),
    }, None


def _load_metric_map(db, region_id):
    query = text("""
        SELECT i.indicator_code, ROUND(CAST(sm.value AS numeric), 1) AS value
        FROM survey_metrics sm
        JOIN indicators i ON sm.indicator_id = i.id
        WHERE sm.region_id = :rid AND sm.survey_year = :yr
    """)
    return {
        code: as_float(value)
        for code, value in db.execute(query, {"rid": region_id, "yr": SURVEY_YEAR}).fetchall()
    }


def _load_national_means(db):
    query = text("""
        SELECT i.indicator_code,
               SUM(sm.value * r.population_weight) / SUM(r.population_weight) AS mean
        FROM survey_metrics sm
        JOIN regions r ON sm.region_id = r.id
        JOIN indicators i ON sm.indicator_id = i.id
        WHERE sm.survey_year = :yr
        GROUP BY i.indicator_code
    """)
    return {
        code: round(as_float(mean), 2)
        for code, mean in db.execute(query, {"yr": SURVEY_YEAR}).fetchall()
    }


def _insights_payload(metrics, targets=None):
    """Policy-engine payload; ministerial target overrides flow through here."""
    payload = generate_insights(metrics, OFFICIAL_BENCHMARKS, targets=targets)
    payload["benchmarks"] = OFFICIAL_BENCHMARKS
    return payload


@router.get("/districts/{ref}/insights")
def district_insights(ref: str, db: Session = Depends(get_db)):
    """Automated policy engine verdict (id OR district name, case-insensitive)."""
    district, hint = _resolve_district(db, ref)
    if district is None:
        return JSONResponse(
            status_code=404,
            content={
                "status": "error",
                "code": "district_not_found",
                "detail": f"No district matching '{ref}'.",
                "hint": hint,
            },
        )
    metrics = _load_metric_map(db, district["id"])
    return {"status": "success", "district": district, **_insights_payload(metrics, effective_targets(db))}


@router.get("/insights/national")
def national_insights(db: Session = Depends(get_db)):
    """Population-weighted national means passed through the policy engine."""
    metrics = _load_national_means(db)
    return {"status": "success", "scope": "national", "metrics": metrics, **_insights_payload(metrics, effective_targets(db))}


@router.post("/admin/seed", summary="Admin-only: full dataset reseed (JWT required)")
def seed_database(
    drop_existing: bool = True,
    include_cfsva: bool = True,
    _admin: dict = Depends(get_current_admin),
):
    """Regenerate the calibrated FinScope/EICV7 (+CFSVA) dataset."""
    import seed_data
    from main import engine

    if drop_existing:
        # Legacy table name (renamed to district_cfsva_metrics) is gone from the
        # metadata; its FK would block drop_all() on regions in Postgres.
        with engine.begin() as conn:
            conn.execute(text("DROP TABLE IF EXISTS district_food_security"))
        from models import Base
        Base.metadata.drop_all(engine)
    regions, indicators, metrics, _ = seed_data.seed(engine, drop_existing=drop_existing)

    cfsva_seeded = bool(include_cfsva)
    if include_cfsva:
        try:
            import seed_cfsva
            seed_cfsva.seed_cfsva(engine)
        except Exception as exc:  # CFSVA layer failure must not fail FinScope seeding
            cfsva_seeded = False
            return {
                "status": "partial",
                "seeded": {"regions": regions, "indicators": indicators, "metric_rows": metrics},
                "cfsva": {"seeded": False, "error": str(exc)},
                "note": "FinScope/EICV7 data re-seeded; CFSVA layer failed (see error).",
            }
    return {
        "status": "success",
        "seeded": {"regions": regions, "indicators": indicators, "metric_rows": metrics},
        "cfsva": {"seeded": cfsva_seeded},
        "note": "Database re-seeded with calibrated FinScope 2024 / EICV7 + CFSVA 2024 data.",
    }
