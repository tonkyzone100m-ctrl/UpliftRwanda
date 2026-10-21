"""Analytics + policy-engine endpoints for UpliftRwanda.

Kept as a separate router so main.py stays focused on connection handling
and the raw /api/metrics feed. Included in main.py with:

    from insights_api import router as insights_router
    app.include_router(insights_router)

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

from policy import generate_insights
from seed_data import build_dataset  # noqa: F401  (validated by seed_data itself)

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


def _as_int(value):
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_float(value):
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


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
        "population_weight": _as_float(row[4]),
        "metric_count": _as_int(row[5]),
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
        "population_weight": _as_float(row[4]),
    }, None


def _load_metric_map(db, region_id):
    query = text("""
        SELECT i.indicator_code, ROUND(CAST(sm.value AS numeric), 1) AS value
        FROM survey_metrics sm
        JOIN indicators i ON sm.indicator_id = i.id
        WHERE sm.region_id = :rid AND sm.survey_year = :yr
    """)
    return {
        code: _as_float(value)
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
        code: round(_as_float(mean), 2)
        for code, mean in db.execute(query, {"yr": SURVEY_YEAR}).fetchall()
    }


def _insights_payload(metrics):
    payload = generate_insights(metrics, OFFICIAL_BENCHMARKS)
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
    return {"status": "success", "district": district, **_insights_payload(metrics)}


@router.get("/insights/national")
def national_insights(db: Session = Depends(get_db)):
    """Population-weighted national means passed through the policy engine."""
    metrics = _load_national_means(db)
    return {"status": "success", "scope": "national", "metrics": metrics, **_insights_payload(metrics)}


# ---------------------------------------------------------------------------
# Demo bootstrap: runs the FinScope/EICV7 seeder with THIS process's engine,
# so no DB password needs to be exported into any other shell.
# Replace/refresh the live 12-row donor dataset with the calibrated
# 30-district x 14-indicator dataset (420 rows).
# ---------------------------------------------------------------------------

@router.post("/admin/seed")
def seed_database(confirm: str = "", drop_existing: bool = True, include_cfsva: bool = True):
    if confirm != "uplift2026":
        return JSONResponse(
            status_code=401,
            content={
                "status": "error",
                "code": "confirm_required",
                "hint": "This endpoint replaces all analytics tables with the "
                        "calibrated FinScope 2024 / EICV7 dataset. Call with "
                        "?confirm=uplift2026 if that is intended.",
            },
        )
    import seed_data
    from main import engine

    engine_local = engine
    if drop_existing:
        # Legacy cleanup FIRST: the dev-era table name (renamed to
        # district_cfsva_metrics) is not part of current metadata, so its FK
        # would block `drop_all() from dropping regions (Postgres FK
        # dependency). SQLite reorders silently, Postgres does not.
        from sqlalchemy import text
        with engine_local.begin() as conn:
            conn.execute(text("DROP TABLE IF EXISTS district_food_security"))
        from models import Base
        Base.metadata.drop_all(engine_local)
    regions, indicators, metrics, series = seed_data.seed(engine_local, drop_existing=drop_existing)

    cfsva_seeded = bool(include_cfsva)
    if include_cfsva:
        try:
            import seed_cfsva
            seed_cfsva.seed_cfsva(engine_local)
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
