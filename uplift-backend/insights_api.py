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


def _load_metric_map(db: Session, region_id: int) -> tuple[dict, dict]:
    """Latest survey vintage wins per (district, indicator).

    Uploaded vintages (e.g. the 2025 LFS) override the calibrated 2024 baseline
    indicator-by-indicator; indicators without a newer row keep the baseline.
    Returns ({indicator_code: value}, {indicator_code: survey_year}).
    """
    query = text("""
        SELECT i.indicator_code, sm.survey_year, ROUND(CAST(sm.value AS numeric), 1) AS value
        FROM survey_metrics sm
        JOIN indicators i ON sm.indicator_id = i.id
        WHERE sm.region_id = :rid
          AND sm.survey_year = (
              SELECT MAX(t.survey_year) FROM survey_metrics t
              WHERE t.region_id = sm.region_id AND t.indicator_id = sm.indicator_id
          )
        ORDER BY i.indicator_code;
    """)
    rows = db.execute(query, {"rid": region_id}).fetchall()
    metrics = {code: as_float(value) for code, _year, value in rows}
    vintage_years = {code: as_int(year) for code, year, _value in rows}
    return metrics, vintage_years


def _load_national_means(db: Session) -> tuple[dict, dict]:
    """Population-weighted means over each district's latest vintage."""
    query = text("""
        SELECT i.indicator_code, MAX(sm.survey_year) AS vintage_year,
               SUM(sm.value * r.population_weight) / NULLIF(SUM(r.population_weight), 0) AS mean
        FROM survey_metrics sm
        JOIN regions r ON sm.region_id = r.id
        JOIN indicators i ON sm.indicator_id = i.id
        WHERE sm.survey_year = (
              SELECT MAX(t.survey_year) FROM survey_metrics t
              WHERE t.region_id = sm.region_id AND t.indicator_id = sm.indicator_id
        )
        GROUP BY i.indicator_code
        ORDER BY i.indicator_code;
    """)
    rows = db.execute(query).fetchall()
    metrics = {code: round(as_float(mean), 2) for code, _year, mean in rows}
    vintage_years = {code: as_int(year) for code, year, _mean in rows}
    return metrics, vintage_years


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
    metrics, vintage_years = _load_metric_map(db, district["id"])
    return {
        "status": "success",
        "district": district,
        "vintage_years": vintage_years,
        "metrics": metrics,
        **_insights_payload(metrics, effective_targets(db)),
    }


@router.get("/insights/national")
def national_insights(db: Session = Depends(get_db)):
    """Population-weighted national means passed through the policy engine."""
    metrics, vintage_years = _load_national_means(db)
    years_query = text("SELECT DISTINCT sm.survey_year FROM survey_metrics sm ORDER BY sm.survey_year")
    years = [as_int(year) for (year,) in db.execute(years_query).fetchall()]
    return {
        "status": "success",
        "scope": "national",
        "years": years,
        "vintage_years": vintage_years,
        "metrics": metrics,
        **_insights_payload(metrics, effective_targets(db)),
    }


@router.post("/admin/seed", summary="Admin-only: full dataset reseed (JWT required)")
def seed_database(
    drop_existing: bool = True,
    include_cfsva: bool = True,
    include_labour: bool = False,
    include_vup: bool = False,
    include_rdhs: bool = False,
    _admin: dict = Depends(get_current_admin),
):
    """Regenerate the calibrated FinScope/EICV7 (+CFSVA) dataset.

    Newer survey layers are opt-in flags so legacy automations keep the exact
    600-row contract; CLI seeders (seed_lfs.py / seed_vup.py / seed_rdhs.py)
    remain the canonical path for a full stack reset.
    """
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
    layer_status = {}
    if include_cfsva:
        try:
            import seed_cfsva
            seed_cfsva.seed_cfsva(engine)
            layer_status["cfsva"] = "seeded"
        except Exception as exc:
            cfsva_seeded = False
            layer_status["cfsva"] = f"failed: {exc}"
            return {
                "status": "partial",
                "seeded": {"regions": regions, "indicators": indicators, "metric_rows": metrics},
                "cfsva": {"seeded": False, "error": str(exc)},
                "layer_status": layer_status,
                "note": "FinScope/EICV7 data re-seeded; CFSVA layer failed (see error).",
            }
    extras = {}
    if include_labour:
        try:
            import seed_lfs
            seed_lfs.seed_lfs(engine)
            extras["labour_lfs_2025"] = "seeded"
        except Exception as exc:
            extras["labour_lfs_2025"] = f"failed: {exc}"
    if include_vup:
        try:
            import seed_vup
            seed_vup.seed_vup(engine)
            extras["vup_2025"] = "seeded"
        except Exception as exc:
            extras["vup_2025"] = f"failed: {exc}"
    if include_rdhs:
        try:
            import seed_rdhs
            seed_rdhs.seed_rdhs(engine)
            extras["rdhs_2025"] = "seeded"
        except Exception as exc:
            extras["rdhs_2025"] = f"failed: {exc}"
    return {
        "status": "success",
        "seeded": {"regions": regions, "indicators": indicators, "metric_rows": metrics},
        "cfsva": {"seeded": cfsva_seeded},
        "extra_layers": extras,
        "layer_status": layer_status,
        "note": "Database re-seeded with calibrated FinScope 2024 / EICV7 (+CFSVA) data.",
    }
