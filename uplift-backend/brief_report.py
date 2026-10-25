"""Executive Policy Brief assembler (Module D) — data layer, format-agnostic.

Builds a plain-data report dict for any district (or the national view) by
joining every seeded NISR layer:

    section            source layer
    -------------------------------------------------
    headline           survey_metrics (FinScope 2024 / EICV7, latest vintage)
    labour             district_lfs_metrics (LFS 2025, Module A)
    vup                district_vup_metrics (VUP 2025, Module B)
    food_security      district_cfsva_metrics (CFSVA 2024)
    living_standards   district_rdhs_metrics (RDHS 2025)
    verdicts + targets policy engine (10-rule rulebook, ministerial edits live)

The same dict feeds the PDF renderer (brief_pdf.py) and the CSV export
(brief_api.py), so the two artefacts can never disagree.
"""

from __future__ import annotations

import datetime as _dt
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from insights_api import _resolve_district, _load_metric_map, _load_national_means, _insights_payload
from targets import effective_targets
import cfsva_api
import labour_api
import rdhs_api
import seed_vup
import vup_api

SOURCES = [
    "NISR Rwanda Labour Force Survey (RLFS) 2025 vintage",
    "NISR EICV7 2023/24 + EICV7 VUP module 2025",
    "FinScope Rwanda Survey 2024 (NISR / AFI)",
    "CFSVA 2024 (NISR / WFP)",
    "RDHS 2025 household + birth recodes (weighted district panel)",
    "UpliftRwanda policy engine (NST2/Vision-2050 rulebook)",
]

SURVEY_LABELS = {
    "headline": "FinScope 2024 · EICV7 2023/24",
    "labour": "RLFS 2025",
    "vup": "EICV7 VUP 2025 + programme MIS",
    "food_security": "CFSVA 2024",
    "living_standards": "RDHS 2025",
    "verdicts": "UpliftRwanda policy engine",
}


def _fmt(value, unit="%", dash="—"):
    if value is None:
        return dash
    if unit == "count":
        return f"{int(value):,}"
    if unit == "pp":
        return f"{value:+.1f} pp"
    if unit == "RWF":
        return f"{value:,.0f} RWF"
    if unit == "pts":
        return f"{value:.1f} pts"
    if unit == "‰":
        return f"{value:.1f} ‰"
    return f"{value:.1f}%" if unit == "%" else f"{value:.1f}"


def _section(section_id, title, rows, subtitle=None):
    return {"id": section_id, "title": title, "subtitle": subtitle, "rows": rows}


def _row(label, value, unit="%", benchmark=None, note=None, basis=None):
    return {
        "label": label, "value": value, "unit": unit,
        "display": _fmt(value, unit), "benchmark": benchmark,
        "benchmark_display": _fmt(benchmark, unit) if benchmark is not None else None,
        "note": note, "basis": basis,
    }


def _district_name(db: Session, region_id: Optional[int]):
    if region_id is None:
        return None
    row = db.execute(text("SELECT district FROM regions WHERE id = :rid"),
                     {"rid": region_id}).first()
    return row[0] if row else None


def _labour_section(db: Session, district: dict):
    """(rows, mine_row) for the labour section; national scope uses weighted means."""
    rows_raw = [labour_api._row_dict(r) for r in labour_api._rows(db)]
    if not rows_raw:
        return []
    weights = labour_api._region_weights(db)
    means = {c: labour_api._weighted_mean(rows_raw, c, weights) for c in labour_api.WIDE_COLUMNS}
    ranks = labour_api._ranks(rows_raw)
    name = _district_name(db, district["id"])
    mine = next((r for r in rows_raw if r["district"] == name), None) if name else None
    is_national = mine is None

    lmap = labour_api.LFS_CATALOG
    out_rows = []
    for code in ["unemployment_rate", "youth_unemployment_rate", "youth_neet_rate",
                 "inactivity_rate", "lfpr", "lfpr_gender_gap_pp",
                 "tvet_unemployment_rate", "general_education_unemployment_rate",
                 "informal_employment_rate", "labor_underutilization_rate",
                 "disability_unemployment_rate"]:
        if is_national and code in ("tvet_unemployment_rate", "general_education_unemployment_rate",
                                    "disability_unemployment_rate", "lfpr_gender_gap_pp"):
            value = means.get(code)
        elif mine is not None and code == "lfpr_gender_gap_pp":
            value = mine["lfpr_male"] - mine["lfpr_female"]
        else:
            value = mine.get(code) if mine else means.get(code)
        if value is None:
            continue
        name_, unit, _desc, _dir = lmap[code]
        note = None
        rank = (ranks.get(code) or {}).get(mine["district"]) if mine else None
        if rank:
            note = f"rank {rank} of {len(ranks.get(code, {}))} districts"
            if is_national:
                note = None
        out_rows.append(_row(name_, value, unit, benchmark=means.get(code), note=note))
    if mine:
        tvet, general = mine.get("tvet_unemployment_rate"), mine.get("general_education_unemployment_rate")
        if tvet is not None and general is not None:
            out_rows.append(_row(
                "TVET advantage (General − TVET unemployment)",
                general - tvet, "pp", note="positive = TVET graduates outperform general stream",
            ))
    elif is_national:
        tvet, general = means.get("tvet_unemployment_rate"), means.get("general_education_unemployment_rate")
        if tvet is not None and general is not None:
            out_rows.append(_row("TVET advantage (General − TVET unemployment)",
                                 general - tvet, "pp",
                                 note="population-weighted national mean"))
    return out_rows


def _vup_section(db: Session, district: dict):
    rows_raw = [vup_api._row_dict(r) for r in vup_api._rows(db)]
    if not rows_raw:
        return []
    name = _district_name(db, district["id"])
    mine = next((r for r in rows_raw if r["district"] == name), None) if name else None
    totals = {c: sum(r[c] for r in rows_raw) for c in vup_api.COMPONENT_COLUMNS}
    means = {c: vup_api._weighted(rows_raw, c) for c in vup_api.VALUE_COLUMNS}
    if mine is None:
        mine = {
            "beneficiaries_total": sum(totals.values()),
            "caseload_per_1000": vup_api._weighted(rows_raw, "caseload_per_1000"),
            **means,
        }
        share_note = "population-weighted national aggregate"
    else:
        share_note = "national share of the 30-district total"

    out_rows = []
    for code in vup_api.COMPONENT_COLUMNS:
        out_rows.append(_row(
            f"Beneficiaries — {seed_vup.COMPONENT_LABELS[code]}", mine[code], "count",
            benchmark=totals.get(code), note=share_note,
        ))
    out_rows.extend([
        _row("All VUP beneficiaries (5 components)", mine["beneficiaries_total"], "count"),
        _row("Caseload per 1,000 residents", mine.get("caseload_per_1000"), "pts"),
        _row("Poverty among beneficiaries (official anchor 41%)",
             mine.get("poverty_rate_among_beneficiaries"), "%",
             benchmark=means.get("poverty_rate_among_beneficiaries")),
        _row("Extreme-poverty share among beneficiaries",
             mine.get("extreme_among_beneficiaries"), "%",
             benchmark=means.get("extreme_among_beneficiaries")),
        _row("Payment timeliness (within statutory window)",
             mine.get("payment_timeliness_pct"), "%",
             benchmark=means.get("payment_timeliness_pct")),
        _row("Digital disbursement (SACCO + Mobile Money)",
             mine.get("digital_disbursement_pct"), "%",
             benchmark=means.get("digital_disbursement_pct")),
        _row("Umurenge SACCO channel share", mine.get("sacco_disbursement_pct"), "%"),
        _row("Mobile Money channel share", mine.get("momo_disbursement_pct"), "%"),
    ])
    return out_rows


def _cfsva_section(db: Session, district: dict):
    rows_raw = cfsva_api._rows(db, "", {})
    if not rows_raw:
        return []
    name = _district_name(db, district["id"])
    mine = next((r for r in rows_raw if r[1] == name), None)
    catalog = cfsva_api.CFSVA_CATALOG
    out_rows = []
    for i, code in enumerate(catalog):
        name_, unit = catalog[code]
        if mine is not None:
            value, note = mine[4 + i], None
        else:
            value = labour_api._weighted_mean(
                [{"district": r[1], code: r[4 + i]} for r in rows_raw],
                code, labour_api._region_weights(db))
            note = "population-weighted national mean"
        if value is None:
            continue
        out_rows.append(_row(name_, value, unit, benchmark=cfsva_api.ANCHORS.get(code), note=note))
    return out_rows


def _rdhs_section(db: Session, district: dict):
    rows_raw = rdhs_api._rows(db, "", {})
    if not rows_raw:
        return []
    name = _district_name(db, district["id"])
    mine = next((r for r in rows_raw if r[1] == name), None)
    catalog = rdhs_api.RDHS_CATALOG
    out_rows = []
    for code in catalog:
        if code == "households":
            continue  # housekeeping column
        name_, unit = catalog[code]
        if mine is not None:
            value = mine[4 + list(catalog).index(code)]
            note = None
        else:
            pairs = [(r[4 + list(catalog).index(code)], r[1]) for r in rows_raw]
            value = _weighted_pairs(db, pairs)
            note = "household-weighted national mean"
        if value is None:
            continue
        out_rows.append(_row(name_, value, unit, note=note))
    return out_rows


def _weighted_pairs(db: Session, pairs):
    weights = labour_api._region_weights(db)
    total = acc = 0.0
    for v, name in pairs:
        if v is None:
            continue
        w = weights.get(name)
        if not w:
            continue
        acc += float(v) * w
        total += w
    return round(acc / total, 2) if total else None


def build_report(db: Session, ref: Optional[str]) -> tuple[Optional[dict], Optional[str]]:
    """Assemble the report dict. Returns (report, error_hint)."""
    now = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    national = ref in (None, "", "national")
    if national:
        district = {"id": None, "district": "National", "province": "Rwanda",
                    "area_type": "national", "population_weight": None}
        metric_map, _vintages = _load_national_means(db)
    else:
        district, hint = _resolve_district(db, ref)
        if district is None:
            return None, f"No district matching '{ref}'."
        metric_map, _vintages = _load_metric_map(db, district["id"])

    payload = _insights_payload(metric_map, effective_targets(db))
    verdicts = payload.get("insights", [])

    headline_codes = [
        "poverty_headcount", "extreme_poverty_rate", "social_protection",
        "financial_inclusion_rate", "transactional_account", "mobile_money",
        "formal_credit", "formal_savings", "financially_vulnerable",
        "extremely_vulnerable", "climate_shock",
    ]
    headline_benchmarks = payload.get("benchmarks", {})
    headline_labels = {
        "poverty_headcount": "Poverty headcount",
        "extreme_poverty_rate": "Extreme poverty",
        "social_protection": "Households reached by social protection",
        "financial_inclusion_rate": "Financial inclusion",
        "transactional_account": "Transactional accounts",
        "mobile_money": "Mobile-money use",
        "formal_credit": "Formal credit use",
        "formal_savings": "Formal savings",
        "financially_vulnerable": "Financially vulnerable",
        "extremely_vulnerable": "Extremely vulnerable",
        "climate_shock": "Climate-shock exposure",
    }
    headline_rows = []
    for code in headline_codes:
        v = metric_map.get(code)
        if v is None:
            continue
        headline_rows.append(_row(
            headline_labels.get(code, code), v, "%",
            benchmark=headline_benchmarks.get(code),
        ))

    sections = [
        _section("headline", "Poverty & Financial Inclusion", headline_rows,
                 subtitle=SURVEY_LABELS["headline"]),
        _section("labour", "Labour Market", _labour_section(db, district),
                 subtitle=SURVEY_LABELS["labour"]),
        _section("vup", "VUP Social Protection Tracker", _vup_section(db, district),
                 subtitle=SURVEY_LABELS["vup"]),
        _section("food_security", "Food Security & Nutrition", _cfsva_section(db, district),
                 subtitle=SURVEY_LABELS["food_security"]),
        _section("living_standards", "Living Standards", _rdhs_section(db, district),
                 subtitle=SURVEY_LABELS["living_standards"]),
    ]
    sections = [s for s in sections if s["rows"]]

    recommendations = recommend(metric_map, sections, verdicts)

    return {
        "meta": {
            "generated_at": now,
            "scope": "national" if national else "district",
            "district": district["district"],
            "province": district["province"],
            "area_type": district["area_type"],
            "survey_labels": SURVEY_LABELS,
            "sources": SOURCES,
            "row_counts": {s["id"]: len(s["rows"]) for s in sections},
            "disclaimer": (
                "All layers combine OFFICIAL national anchors with calibrated district panels "
                "(FinScope/LFS microdata cannot be redistributed). Weighted national aggregates "
                "are exact; single district cells are calibrated reconstructions — interpret them "
                "as decision-grade stand-ins, not phonebook-level microdata."
            ),
        },
        "sections": sections,
        "verdicts": [{
            "id": v.get("id"), "severity": v.get("severity"),
            "pillar": v.get("pillar"),
            "headline": v.get("title") or v.get("headline"),
            "action": v.get("description") or v.get("action"),
        } for v in verdicts],
        "thresholds": payload.get("thresholds"),
        "recommendations": recommendations,
    }, None


def recommend(metric_map: dict, sections: list[dict], verdicts: list[dict]) -> list[str]:
    """Deterministic action list triggered by the joined evidence."""
    by_id = {s["id"]: s for s in sections}
    recs: list[str] = []

    pov = metric_map.get("poverty_headcount")
    vup_rows = by_id.get("vup", {"rows": []})["rows"]
    pov_vup = next((r["value"] for r in vup_rows
                    if r["label"].startswith("Poverty among beneficiaries")), None)
    if pov is not None and pov > 30:
        if pov_vup is not None:
            recs.append(
                f"Local poverty is {pov:.1f}% vs the 27.4% national anchor, and {pov_vup:.1f}% of "
                f"VUP beneficiaries remain poor — deepen Direct Support → Financial Services "
                f"graduation caseloads (FS + NSDS) ahead of public-works expansion.")
        else:
            recs.append(
                f"Local poverty is {pov:.1f}% vs the 27.4% anchor: scale VUP Direct Support and "
                f"Financial Services graduation caseloads first.")

    vlookup = {r["label"]: r["value"] for r in vup_rows}
    timeliness = vlookup.get("Payment timeliness (within statutory window)")
    digital = vlookup.get("Digital disbursement (SACCO + Mobile Money)")
    if timeliness is not None and timeliness < 88:
        recs.append(
            f"Only {timeliness:.1f}% of VUP payments land in-window ({digital if digital is not None else 0:.1f}% "
            f"digital): audit distribution-day staffing and complete the digital switch.")
    elif digital is not None and digital < 75:
        recs.append(
            f"Digital disbursement is {digital:.1f}% — push the Umurenge SACCO/mobile-money switch "
            f"to cut cash-in-transit risk and lock in financial-inclusion spillovers.")

    labour_rows = by_id.get("labour", {"rows": []})["rows"]
    llookup = {r["label"]: r["value"] for r in labour_rows}
    neet = llookup.get("Youth NEET Rate (16-30)")
    if neet is not None and neet > 26:
        recs.append(
            f"Youth NEET stands at {neet:.1f}% (national 24.5%): stand up a youth "
            f"entrepreneurship + apprenticeship pipeline wired to BDF and Duterimbere entry points.")
    tvet = llookup.get("TVET Graduate Unemployment")
    general = llookup.get("General-Stream Unemployment")
    if tvet is not None and general is not None and general > tvet + 4:
        recs.append(
            f"TVET graduates outperform general-stream leavers by {general - tvet:.1f} pp "
            f"unemployment — reallocate short-term skills budget toward TVET trades.")
    inact = llookup.get("Out-of-Labour-Force (Inactivity) Rate")
    if inact is not None and inact > 36:
        recs.append(
            f"Out-of-labour-force share is {inact:.1f}% (among Rwanda's highest): expand Expanded "
            f"Public Works with caregiving-adjusted schedules to pull participants in.")

    food_rows = by_id.get("food_security", {"rows": []})["rows"]
    flookup = {r["label"]: r["value"] for r in food_rows}
    stunting = flookup.get("Child Stunting")
    if stunting is not None and stunting > 30:
        recs.append(
            f"Child stunting remains {stunting:.1f}%: tighten Nutrition-Sensitive Direct Support "
            f"targeting (pregnant/lactating + under-2 households) and link to SMART-Nkunganire inputs.")

    vuln = metric_map.get("financially_vulnerable")
    if vuln is not None and vuln > 31:
        recs.append(
            f"{vuln:.1f}% of adults are financially vulnerable (national 31%): bundle micro-insurance "
            f"and Ibimina savings groups into VUP Financial Services sessions.")

    if not recs:
        recs.append("Maintain the current mix: no critical flag fired across employment, poverty, "
                    "food-security or financial-inclusion thresholds.")
    return recs
