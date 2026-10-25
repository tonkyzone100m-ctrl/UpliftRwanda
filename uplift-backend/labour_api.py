"""LFS 2025 labour-market layer: catalog, national summary, district wide rows,
district profiles, gender/education/disability disaggregation and a
/api/metrics-contract row feed (category "Labour Market (LFS 2025)").

Source: `district_lfs_metrics` + `district_lfs_segments` (seed_lfs.py), a
calibrated panel anchored to RLFS 2025 national statistics (unemployment
12.4%, youth NEET 24.5%, male-female LFPR gap 14.3 pp).
"""

from typing import Any, Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from main import get_db
from insights_api import _resolve_district
from models import as_float
import seed_lfs

router = APIRouter(prefix="/api/labour", tags=["labour"])

LFS_YEAR = seed_lfs.LFS_YEAR
LFS_CATEGORY = "Labour Market (LFS 2025)"

# code -> (name, unit, description, direction)  direction: "lower"|"higher" is better
LFS_CATALOG = {
    "unemployment_rate": ("Unemployment Rate", "%",
        "Share of the labour force without work, available and searching (RLFS 2025 national: 12.4%)", "lower"),
    "employment_ratio": ("Employment-to-Population Ratio", "%",
        "Share of the working-age population that is employed", "higher"),
    "lfpr": ("Labour Force Participation Rate", "%",
        "Share of the working-age population in or actively seeking work", "higher"),
    "inactivity_rate": ("Out-of-Labour-Force (Inactivity) Rate", "%",
        "Share of the working-age population neither working nor job-seeking", "lower"),
    "youth_unemployment_rate": ("Youth Unemployment (16-30)", "%",
        "Share of the youth labour force without work (RLFS 2025 vintage)", "lower"),
    "youth_neet_rate": ("Youth NEET Rate (16-30)", "%",
        "Youth not in employment, education or training (RLFS 2025 national: 24.5%)", "lower"),
    "lfpr_gender_gap_pp": ("LFPR Gender Gap (male - female)", "pp",
        "Male minus female labour-force participation gap (RLFS 2025 national: 14.3 pp)", "lower"),
    "unemployment_gender_gap": ("Unemployment Gap (female - male)", "pp",
        "Female minus male unemployment rate (women carry a structural premium)", "lower"),
    "informal_employment_rate": ("Informal Employment Share", "%",
        "Informal share of total employment (subsistence + unregistered non-farm)", "lower"),
    "time_underemployment_rate": ("Time-Related Underemployment", "%",
        "Employed persons working below full-week hours thresholds", "lower"),
    "labor_underutilization_rate": ("Labour Underutilization (LU3)", "%",
        "Unemployed + time-related underemployment + potential labour force", "lower"),
    "tvet_unemployment_rate": ("TVET Graduate Unemployment", "%",
        "Unemployment among TVET graduates - the skilling advantage", "lower"),
    "general_education_unemployment_rate": ("General-Stream Unemployment", "%",
        "Unemployment among general (non-TVET) secondary leavers", "lower"),
    "disability_lfpr": ("Participation with Disability", "%",
        "LFPR among persons reporting a disability", "higher"),
    "disability_unemployment_rate": ("Unemployment with Disability", "%",
        "Unemployment among disabled labour force members", "lower"),
}

WIDE_COLUMNS = [c for c in LFS_CATALOG if c not in ("lfpr_gender_gap_pp", "unemployment_gender_gap")]

# wide-table columns surfaced by /districts and /metrics
SELECT_COLUMNS = [
    "unemployment_rate", "employment_ratio", "lfpr", "inactivity_rate",
    "youth_unemployment_rate", "youth_neet_rate", "lfpr_male", "lfpr_female",
    "unemployment_rate_male", "unemployment_rate_female", "youth_neet_male",
    "youth_neet_female", "informal_employment_rate", "time_underemployment_rate",
    "labor_underutilization_rate", "tvet_unemployment_rate",
    "general_education_unemployment_rate", "disability_lfpr",
    "disability_unemployment_rate",
]

SEGMENT_LABELS = {
    "gender": {"male": "Male", "female": "Female"},
    "education": {"primary": "Primary only", "secondary_general": "General secondary",
                  "tvet": "TVET", "tertiary": "Tertiary"},
    "disability": {"with_disability": "With disability", "without_disability": "Without disability"},
}
SEGMENT_INDICATORS = ("unemployment", "lfpr", "employment_ratio", "neet")


def _rows(db: Session, ref_sql: str = "", params: dict | None = None):
    params = {"yr": LFS_YEAR, **(params or {})}
    cols_sql = ", ".join(f"t.{c}" for c in SELECT_COLUMNS)
    query = text(f"""
        SELECT r.province, r.district, r.area_type, t.survey_year,
               {cols_sql}, t.lfpr_male - t.lfpr_female AS gap,
               t.unemployment_rate_female - t.unemployment_rate_male AS unemp_gap
        FROM district_lfs_metrics t
        JOIN regions r ON t.region_id = r.id
        WHERE t.survey_year = :yr
        {ref_sql}
        ORDER BY r.province, r.district
    """)
    return db.execute(query, params).fetchall()


def _row_dict(row):
    """Wide row -> payload dict (labelled row probe)."""
    keys = ["province", "district", "area_type", "survey_year"] + SELECT_COLUMNS + \
        ["lfpr_gender_gap_pp", "unemployment_gender_gap"]
    data = dict(zip(keys, row))
    return {k: (as_float(v) if k not in ("province", "district", "area_type") else v) for k, v in data.items()}


def _ranks(rows: list[dict]) -> dict:
    """For 'lower-is-better' codes: rank 1 = highest rate."""
    ranks: dict[str, dict[str, int]] = {}
    for code in WIDE_COLUMNS:
        direction = LFS_CATALOG[code][3]
        ordered = sorted(
            [r for r in rows if r.get(code) is not None],
            key=lambda r: r[code],
            reverse=(direction == "lower"),
        )
        ranks[code] = {r["district"]: i + 1 for i, r in enumerate(ordered)}
    return ranks


def _weighted_mean(rows: list[dict], key: str, weights: dict[str, float]) -> Optional[float]:
    total = 0.0
    acc = 0.0
    for r in rows:
        v = r.get(key)
        w = weights.get(r["district"])
        if v is None or not w:
            continue
        acc += v * w
        total += w
    return round(acc / total, 2) if total else None


def _region_weights(db: Session) -> dict[str, float]:
    return {
        row[1]: as_float(row[2]) or 1.0
        for row in db.execute(text("SELECT id, district, population_weight FROM regions")).fetchall()
    }


@router.get("/indicators")
def labour_indicators(db: Session = Depends(get_db)):
    weights = _region_weights(db)
    rows = [_row_dict(r) for r in _rows(db)]
    means = {code: _weighted_mean(rows, code, weights) for code in WIDE_COLUMNS}
    official = seed_lfs.ANCHORS
    data = [{
        "indicator_code": code,
        "indicator_name": LFS_CATALOG[code][0],
        "unit": LFS_CATALOG[code][1],
        "description": LFS_CATALOG[code][2],
        "direction": LFS_CATALOG[code][3],
        "national_anchor": official[code] if code in ("unemployment_rate", "youth_neet_rate") else means.get(code),
        "national_mean": means.get(code),
        "survey_year": LFS_YEAR,
    } for code in LFS_CATALOG]
    return {
        "status": "success",
        "count": len(data),
        "national_hierarchy": {
            "unemployment_rate": seed_lfs.ANCHORS["unemployment_rate"],
            "youth_neet_rate": seed_lfs.ANCHORS["youth_neet_rate"],
            "lfpr_gender_gap_pp": seed_lfs.ANCHORS["lfpr_gender_gap_pp"],
        },
        "dimensions": [
            {"dimension": dim, "segments": SEGMENT_LABELS[dim],
             "indicators": list(SEGMENT_INDICATORS)}
            for dim in SEGMENT_LABELS
        ],
        "data": data,
    }


@router.get("/summary")
def labour_summary(db: Session = Depends(get_db)):
    """National KPI block + worst/best league tables for the dashboard."""
    weights = _region_weights(db)
    rows = [_row_dict(r) for r in _rows(db)]
    if not rows:
        return JSONResponse(status_code=503, content={
            "status": "error", "code": "labour_layer_missing",
            "detail": "LFS 2025 layer is not seeded yet.",
            "hint": "python3 seed_lfs.py --url $DATABASE_URL",
        })
    ranks = _ranks(rows)
    means = {c: _weighted_mean(rows, c, weights) for c in WIDE_COLUMNS}
    lfpr_male_national = _weighted_mean(rows, "lfpr_male", weights)
    lfpr_female_national = _weighted_mean(rows, "lfpr_female", weights)
    unemp_male_national = _weighted_mean(rows, "unemployment_rate_male", weights)
    unemp_female_national = _weighted_mean(rows, "unemployment_rate_female", weights)
    gender_gap_national = round((lfpr_male_national or 0) - (lfpr_female_national or 0), 2)
    unemp_gap_national = round((unemp_female_national or 0) - (unemp_male_national or 0), 2)

    def league(code, worst_first=True, n=5):
        ordered = sorted(
            [r for r in rows if r.get(code) is not None],
            key=lambda r: r[code],
            reverse=worst_first,
        )
        return [{
            "district": r["district"], "province": r["province"], "value": r[code],
            "rank": ranks[code][r["district"]],
        } for r in ordered[:n]]

    return {
        "status": "success",
        "survey_year": LFS_YEAR,
        "national": {
            "unemployment_rate": means["unemployment_rate"],
            "employment_ratio": means["employment_ratio"],
            "lfpr": means["lfpr"],
            "inactivity_rate": means["inactivity_rate"],
            "youth_unemployment_rate": means["youth_unemployment_rate"],
            "youth_neet_rate": means["youth_neet_rate"],
            "lfpr_gender_gap_pp": gender_gap_national,
            "unemployment_gender_gap": unemp_gap_national,
            "lfpr_male": lfpr_male_national,
            "lfpr_female": lfpr_female_national,
            "tvet_unemployment_rate": means["tvet_unemployment_rate"],
            "general_education_unemployment_rate": means["general_education_unemployment_rate"],
            "tvet_advantage_pp": round(
                (means["general_education_unemployment_rate"] or 0)
                - (means["tvet_unemployment_rate"] or 0), 2),
            "informal_employment_rate": means["informal_employment_rate"],
            "time_underemployment_rate": means["time_underemployment_rate"],
            "labor_underutilization_rate": means["labor_underutilization_rate"],
            "disability_lfpr": means["disability_lfpr"],
            "disability_unemployment_rate": means["disability_unemployment_rate"],
        },
        "official": {
            "unemployment_rate": seed_lfs.ANCHORS["unemployment_rate"],
            "youth_neet_rate": seed_lfs.ANCHORS["youth_neet_rate"],
            "lfpr_gender_gap_pp": seed_lfs.ANCHORS["lfpr_gender_gap_pp"],
        },
        "leagues": {
            "unemployment_worst": league("unemployment_rate", worst_first=True),
            "unemployment_best": league("unemployment_rate", worst_first=False),
            "inactivity_worst": league("inactivity_rate", worst_first=True),
            "youth_neet_worst": league("youth_neet_rate", worst_first=True),
            "tvet_worst": league("tvet_unemployment_rate", worst_first=True),
            # derived per-district gaps (not part of the wide-rank set)
            "gender_gap_worst": [
                {"district": r["district"], "province": r["province"],
                 "value": round(r["lfpr_male"] - r["lfpr_female"], 2), "rank": None}
                for r in sorted(rows, key=lambda r: r["lfpr_male"] - r["lfpr_female"], reverse=True)[:5]
            ],
        },
    }


@router.get("/districts")
def labour_districts(db: Session = Depends(get_db)):
    rows = [_row_dict(r) for r in _rows(db)]
    return {"status": "success", "count": len(rows), "survey_year": LFS_YEAR, "data": rows}


@router.get("/districts/{ref}")
def labour_district(ref: str, db: Session = Depends(get_db)):
    district, hint = _resolve_district(db, ref)
    if district is None:
        return JSONResponse(status_code=404, content={
            "status": "error", "code": "district_not_found",
            "detail": f"No district matching '{ref}'.", "hint": hint,
        })
    rows = [_row_dict(r) for r in _rows(
        db, "AND LOWER(r.district) = LOWER(:name)", {"yr": LFS_YEAR, "name": district["district"]})]
    if not rows:
        return JSONResponse(status_code=404, content={
            "status": "error", "code": "labour_district_not_found",
            "detail": f"No LFS 2025 record for '{ref}' (year {LFS_YEAR}).",
            "hint": "Seed the layer: python3 seed_lfs.py --url $DATABASE_URL",
        })
    mine = rows[0]
    weights = _region_weights(db)
    all_rows = [_row_dict(r) for r in _rows(db)]
    ranks = _ranks(all_rows)
    means = {c: _weighted_mean(all_rows, c, weights) for c in WIDE_COLUMNS}
    return {
        "status": "success",
        "district": mine["district"],
        "region": district,
        "survey_year": LFS_YEAR,
        **mine,
        "national_means": means,
        "ranks": {c: ranks[c].get(mine["district"]) for c in WIDE_COLUMNS},
        "district_count": len(all_rows),
    }


@router.get("/disaggregation")
def labour_disaggregation(
    dimension: str = Query("gender", pattern="^(gender|education|disability)$"),
    district: Optional[str] = Query(None),
    indicator: Optional[str] = Query(None),
    segment: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Long/tidy demographic splits powering the dashboard filter chips."""
    filters = ["t.survey_year = :yr", "t.dimension = :dim"]
    params: dict[str, Any] = {"yr": LFS_YEAR, "dim": dimension}
    if district:
        filters.append("LOWER(r.district) = LOWER(:district)")
        params["district"] = district
    if indicator:
        filters.append("t.indicator = :indicator")
        params["indicator"] = indicator
    if segment:
        filters.append("t.segment = :segment")
        params["segment"] = segment
    query = text(f"""
        SELECT r.province, r.district, t.dimension, t.segment, t.indicator, t.value
        FROM district_lfs_segments t
        JOIN regions r ON t.region_id = r.id
        WHERE {' AND '.join(filters)}
        ORDER BY r.province, r.district, t.segment, t.indicator
    """)
    rows = [{
        "province": row[0], "district": row[1], "dimension": row[2],
        "segment": row[3], "segment_label": SEGMENT_LABELS[row[2]].get(row[3], row[3]),
        "indicator": row[4], "value": as_float(row[5]),
    } for row in db.execute(query, params).fetchall()]
    return {
        "status": "success",
        "count": len(rows),
        "dimension": dimension,
        "data": rows,
    }


@router.get("/metrics")
def labour_metrics(db: Session = Depends(get_db)):
    """Row-feed consistent with GET /api/metrics (category 'Labour Market')."""
    rows = [_row_dict(r) for r in _rows(db)]
    metrics = []
    for row in rows:
        for code in WIDE_COLUMNS:
            name, unit, _desc, _dir = LFS_CATALOG[code]
            metrics.append({
                "province": row["province"], "district": row["district"],
                "area_type": row["area_type"],
                "indicator_code": code,
                "indicator_name": name,
                "category": LFS_CATEGORY,
                "unit": unit,
                "survey_year": row["survey_year"],
                "value": row.get(code),
            })
    return {"status": "success", "count": len(metrics), "data": metrics}
