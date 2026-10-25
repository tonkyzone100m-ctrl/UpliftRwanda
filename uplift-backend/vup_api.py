"""VUP social-protection layer: five-component catalog, national summary,
district caseloads, district profiles and a /api/metrics-contract row feed
(category "VUP Social Protection").

Source: `district_vup_metrics` (seed_vup.py). Poverty among beneficiaries is
the OFFICIAL EICV7 VUP 2025 anchor (41%); operational metrics are the
programme-side modelled layer described in the seeder docstring.
"""


from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from main import get_db
from insights_api import _resolve_district
from models import as_float, as_int
import seed_vup

router = APIRouter(prefix="/api/vup", tags=["vup"])

VUP_YEAR = seed_vup.VUP_YEAR
VUP_CATEGORY = "VUP Social Protection"

COMPONENT_COLUMNS = tuple(seed_vup.COMPONENT_LABELS)

VALUE_COLUMNS = (
    *COMPONENT_COLUMNS,
    "poverty_rate_among_beneficiaries", "extreme_among_beneficiaries",
    "payment_timeliness_pct", "sacco_disbursement_pct",
    "momo_disbursement_pct", "cash_disbursement_pct",
)

METRIC_CATALOG = {
    **{c: (f"VUP {label}", "beneficiaries") for c, label in seed_vup.COMPONENT_LABELS.items()},
    "poverty_rate_among_beneficiaries": ("Poverty Among VUP Beneficiaries", "%"),
    "extreme_among_beneficiaries": ("Extreme Poverty Among VUP Beneficiaries", "%"),
    "payment_timeliness_pct": ("Payment Timeliness (%)", "%"),
    "sacco_disbursement_pct": ("Umurenge SACCO Disbursement Share", "%"),
    "momo_disbursement_pct": ("Mobile Money Disbursement Share", "%"),
    "cash_disbursement_pct": ("Cash Disbursement Share", "%"),
}

METRIC_DESCRIPTIONS = {
    "poverty_rate_among_beneficiaries": "Share of VUP beneficiary households below the poverty line (OFFICIAL EICV7 VUP: 41%)",
    "extreme_among_beneficiaries": "Share of beneficiaries below the extreme-poverty line (OFFICIAL anchor 12.5%)",
    "payment_timeliness_pct": "Payments completed within the statutory window (modelled programme-side KPI)",
    "sacco_disbursement_pct": "Share of disbursements routed via Umurenge SACCO (modelled)",
    "momo_disbursement_pct": "Share of disbursements routed via Mobile Money (modelled)",
    "cash_disbursement_pct": "Share of disbursements as cash-in-transit (residual; digital-first policy target)",
}


def _rows(db: Session, ref_sql: str = "", params: dict | None = None):
    params = params or {"yr": VUP_YEAR}
    cols_sql = ", ".join(f"t.{c}" for c in VALUE_COLUMNS)
    query = text(f"""
        SELECT r.province, r.district, r.area_type, r.population_weight,
               t.survey_year, {cols_sql}
        FROM district_vup_metrics t
        JOIN regions r ON t.region_id = r.id
        WHERE t.survey_year = :yr
        {ref_sql}
        ORDER BY r.province, r.district
    """)
    return db.execute(query, params).fetchall()


def _row_dict(row):
    keys = ["province", "district", "area_type", "population_weight", "survey_year", *VALUE_COLUMNS]
    data = dict(zip(keys, row))
    base = {k: (v if k in ("province", "district", "area_type") else as_float(v)) for k, v in data.items()}
    int_fields = set(COMPONENT_COLUMNS)
    for k in int_fields & set(base):
        base[k] = as_int(base[k])
    # derived analytics the dashboard consumes directly
    total = sum(base[c] for c in COMPONENT_COLUMNS)
    base["beneficiaries_total"] = total
    base["moderate_among_beneficiaries"] = round(
        max(0.0, (base["poverty_rate_among_beneficiaries"] or 0.0)
            - (base["extreme_among_beneficiaries"] or 0.0)), 1)
    base["digital_disbursement_pct"] = round(
        min(100.0, (base["sacco_disbursement_pct"] or 0.0)
            + (base["momo_disbursement_pct"] or 0.0)), 1)
    pop = base["population_weight"] or 0.0
    base["caseload_per_1000"] = round(total / (pop * 1000.0), 1) if pop else None  # pop_weight is in millions
    return base


def _weighted(rows, key, weight_key="population_weight"):
    total = 0.0
    acc = 0.0
    for r in rows:
        v = r.get(key)
        w = r.get(weight_key)
        if v is None or not w:
            continue
        acc += v * w
        total += w
    return round(acc / total, 2) if total else None


@router.get("/indicators")
def vup_indicators():
    data = [{
        "column": col,
        "indicator_name": METRIC_CATALOG[col][0],
        "unit": METRIC_CATALOG[col][1],
        "label": seed_vup.COMPONENT_LABELS.get(col),
        "description": METRIC_DESCRIPTIONS.get(col),
        "basis": "OFFICIAL (EICV7 VUP 2025)" if col in (
            "poverty_rate_among_beneficiaries", "extreme_among_beneficiaries") else "MODELLED (calibrated panel)",
    } for col in VALUE_COLUMNS]
    return {
        "status": "success",
        "count": len(data),
        "survey_year": VUP_YEAR,
        "national_totals": seed_vup.NATIONAL_COMPONENTS,
        "anchors": seed_vup.ANCHORS,
        "data": data,
    }


@router.get("/summary")
def vup_summary(db: Session = Depends(get_db)):
    rows = [_row_dict(r) for r in _rows(db)]
    if not rows:
        return JSONResponse(status_code=503, content={
            "status": "error", "code": "vup_layer_missing",
            "detail": "VUP layer is not seeded yet.",
            "hint": "python3 seed_vup.py --url $DATABASE_URL",
        })
    totals = {c: sum(r[c] for r in rows) for c in COMPONENT_COLUMNS}
    total_all = sum(totals.values())
    poverty_national = _weighted(rows, "poverty_rate_among_beneficiaries")
    extreme_national = _weighted(rows, "extreme_among_beneficiaries")
    digital = _weighted(rows, "digital_disbursement_pct")
    leagues = {
        **{component: sorted(rows, key=lambda r: r[component], reverse=True)[:5]
           for component in COMPONENT_COLUMNS},
        "caseload_per_1000_worst": sorted(
            [r for r in rows if r["caseload_per_1000"] is not None],
            key=lambda r: r["caseload_per_1000"], reverse=True,
        )[:5],
        "poverty_among_beneficiaries_worst": sorted(
            rows, key=lambda r: r["poverty_rate_among_beneficiaries"], reverse=True,
        )[:5],
        "payment_timeliness_worst": sorted(
            rows, key=lambda r: r["payment_timeliness_pct"])[:5],
    }
    league_data = {
        name: [{
            "district": r["district"], "province": r["province"],
            "value": r[name] if name in COMPONENT_COLUMNS else r[{
                "caseload_per_1000_worst": "caseload_per_1000",
                "poverty_among_beneficiaries_worst": "poverty_rate_among_beneficiaries",
                "payment_timeliness_worst": "payment_timeliness_pct",
            }[name]],
        } for r in rows_]
        for name, rows_ in leagues.items()
    }
    return {
        "status": "success",
        "survey_year": VUP_YEAR,
        "national": {
            "component_totals": totals,
            "beneficiaries_total": total_all,
            "poverty_among_beneficiaries": poverty_national,
            "extreme_among_beneficiaries": extreme_national,
            "moderate_among_beneficiaries": round(max(0.0, (poverty_national or 0) - (extreme_national or 0)), 2),
            "payment_timeliness_pct": _weighted(rows, "payment_timeliness_pct"),
            "disbursement_mix": {
                "umurenge_sacco": _weighted(rows, "sacco_disbursement_pct"),
                "mobile_money": _weighted(rows, "momo_disbursement_pct"),
                "cash": _weighted(rows, "cash_disbursement_pct"),
                "digital_total": digital,
            },
        },
        "anchors": seed_vup.ANCHORS,
        "leagues": league_data,
    }


@router.get("/districts")
def vup_districts(db: Session = Depends(get_db)):
    rows = [_row_dict(r) for r in _rows(db)]
    return {"status": "success", "count": len(rows), "survey_year": VUP_YEAR, "data": rows}


@router.get("/districts/{ref}")
def vup_district(ref: str, db: Session = Depends(get_db)):
    district, hint = _resolve_district(db, ref)
    if district is None:
        return JSONResponse(status_code=404, content={
            "status": "error", "code": "vup_district_not_found",
            "detail": f"No district matching '{ref}'.", "hint": hint,
        })
    rows = [_row_dict(r) for r in _rows(
        db, "AND LOWER(r.district) = LOWER(:name)",
        {"yr": VUP_YEAR, "name": district["district"]})]
    if not rows:
        return JSONResponse(status_code=404, content={
            "status": "error", "code": "vup_district_not_found",
            "detail": f"No VUP record for '{ref}' (year {VUP_YEAR}).",
            "hint": "Seed the layer: python3 seed_vup.py --url $DATABASE_URL",
        })
    all_rows = [_row_dict(r) for r in _rows(db)]
    mine = rows[0]
    return {
        "status": "success",
        "district": mine["district"],
        "region": district,
        "survey_year": VUP_YEAR,
        **mine,
        "national_means": {c: _weighted(all_rows, c) for c in VALUE_COLUMNS},
        "national_component_totals": {c: sum(r[c] for r in all_rows) for c in COMPONENT_COLUMNS},
        "district_count": len(all_rows),
    }


@router.get("/metrics")
def vup_metrics(db: Session = Depends(get_db)):
    rows = [_row_dict(r) for r in _rows(db)]
    metrics = []
    for row in rows:
        for code in VALUE_COLUMNS:
            name, unit = METRIC_CATALOG[code]
            metrics.append({
                "province": row["province"], "district": row["district"],
                "area_type": row["area_type"],
                "indicator_code": code,
                "indicator_name": name,
                "category": VUP_CATEGORY,
                "unit": unit,
                "survey_year": row["survey_year"],
                "value": row.get(code),
            })
    return {"status": "success", "count": len(metrics), "data": metrics}
