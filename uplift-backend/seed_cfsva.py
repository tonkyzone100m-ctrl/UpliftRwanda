#!/usr/bin/env python3
"""CFSVA 2024 seeder — non-destructive companion to seed_data.py.

Fills `district_cfsva_metrics` ONLY. Existing tables (regions/indicators/
survey_metrics/policy tables) are untouched. Requires `regions` to exist
(seed_data.py first), because rows link via the SAME region ids.

District values are profiled from the already-seeded FinScope/EICV7
deterministic geography (poverty & climate exposure), then CALIBRATED so the
population-weighted national means hit the CFSVA-2024 anchor values in
ANCHORS below (tune them against the official bulletin before submission).
Deterministic jitter keeps outputs reproducible across runs.

Usage:
    python3 seed_cfsva.py --url $DATABASE_URL --dry-run
    python3 seed_cfsva.py --url $DATABASE_URL --drop-cfsva-first
"""

from __future__ import annotations

import argparse
import os
import sys

import seed_data
from sqlalchemy import create_engine, text

# Anchors (population-weighted national means) — TUNABLE to the CFSVA 2024 bulletin.
ANCHORS = {
    "fies_moderate_severe_pct": 17.0,   # OFFICIAL: food secure 83% => 16% moderate + 1% severe
    "fies_severe_pct": 1.0,             # OFFICIAL: severely food insecure 1%
    "food_consumption_score": 47.5,     # mean FCS (IPC bands: <28 poor, 28-42 borderline, >42 acceptable)
    "fcs_poor_pct": 9.8,                # share with poor FCS %
    "hdds": 6.2,                        # mean HDDS 0-12
    "stunting_pct": 30.0,               # OFFICIAL: under-5 stunting baseline 30% (down from historical)
    "wasting_pct": 2.1,                 # under-5 wasting %
    "rcsi": 13.5,                       # reduced coping strategies index (lower = better)
    "harvest_loss_pct": 24.0,           # households with >=1 harvest loss %
}

BOUNDS = {
    "fies_moderate_severe_pct": (1.0, 48.0),
    "fies_severe_pct": (0.2, 6.0),
    "food_consumption_score": (18.0, 90.0),
    "fcs_poor_pct": (1.0, 35.0),
    "hdds": (3.2, 9.0),
    "stunting_pct": (18.0, 47.0),
    "wasting_pct": (0.5, 5.5),
    "rcsi": (6.0, 24.0),
    "harvest_loss_pct": (8.0, 46.0),
}

# OFFICIAL provincial vulnerability split (CFSVA 2024 FIES moderate+severe):
# Western 23%, Southern 16%, Kigali 4%, Eastern 14%. Northern is derived as
# the population-weight residual that makes the national mean exactly 17%.
PROVINCIAL_FIES_TARGETS = {
    "Western Province": 23.0,
    "Southern Province": 16.0,
    "Kigali City": 4.0,
    "Eastern Province": 14.0,
}

# Load-shapes: how the FinScope/EICV7 covariates move each CFSVA statistic.
# cov(idx) is a signed standard-ish gap: (district value - national anchor + jitter)/norm
# e.g. poverty headcount normalized by its national anchor 27.4.
COVARIATE_WEIGHTS = {
    "fies_moderate_severe_pct": {"poverty": 16.0, "climate": 5.5},
    "fies_severe_pct":          {"poverty": 1.8, "climate": 0.6},
    "food_consumption_score":  {"poverty": -19.0, "climate": -7.0},
    "fcs_poor_pct":            {"poverty": 7.5, "climate": 2.5},
    "hdds":                    {"poverty": -1.15, "climate": -0.4},
    "stunting_pct":            {"poverty": 12.0, "climate": 3.0},
    "wasting_pct":             {"poverty": 1.4, "climate": 0.5},
    "rcsi":                    {"poverty": 5.2, "climate": 2.0},
    "harvest_loss_pct":        {"poverty": 9.0, "climate": 11.0},
}

CFSVA_YEAR = 2024
JITTER_PP = 1.2

INDICATORS = [
    # (code, name, unit, description)
    ("fies_moderate_severe_pct", "Food Insecurity (moderate+severe)", "%",
     "Share of households moderately or severely food insecure (CFSVA 2024 FIES; 83% food secure)"),
    ("fies_severe_pct", "Severe Food Insecurity", "%",
     "Share of households severely food insecure (CFSVA 2024 FIES: 1%)"),
    ("food_consumption_score", "Food Consumption Score", "pts",
     "Mean WFP Food Consumption Score (0-112; IPC nutrition bands)"),
    ("fcs_poor_pct", "Poor Food Consumption", "%",
     "Share of households with poor FCS (<28 points)"),
    ("hdds", "Dietary Diversity (HDDS)", "pts",
     "Mean Household Dietary Diversity Score (0-12 groups)"),
    ("stunting_pct", "Child Stunting", "%",
     "Under-five height-for-age <-2 SD (chronic malnutrition)"),
    ("wasting_pct", "Child Wasting", "%",
     "Under-five weight-for-height <-2 SD (acute malnutrition)"),
    ("rcsi", "Coping Strategies Index", "pts",
     "Reduced Coping Strategies Index for food access stress (lower is better)"),
    ("harvest_loss_pct", "Harvest Loss Exposure", "%",
     "Households reporting >=1 harvest loss in the last season"),
]


def raw_profile(df_row, district_name):
    from seed_data import stable_jitter

    pov = (df_row.get("poverty_headcount", 27.4) - 27.4) / 27.4
    clim = (df_row.get("climate_shock", 69.0) - 69.0) / 69.0
    raw = {}
    for field, weights in COVARIATE_WEIGHTS.items():
        wpov, wclim = weights["poverty"], weights["climate"]
        jitter = stable_jitter(district_name, f"cfsva-{field}") * JITTER_PP
        raw[field] = ANCHORS[field] + wpov * pov + wclim * clim + jitter
    return raw


def seed_cfsva(engine, drop_cfsva_first=False):
    import seed_data
    from models import DistrictCfsvaMetrics, Region
    from sqlalchemy.orm import sessionmaker

    if drop_cfsva_first:
        DistrictCfsvaMetrics.__table__.drop(engine, checkfirst=True)
    DistrictCfsvaMetrics.__table__.create(engine, checkfirst=True)

    # district EF rows from the canonical district geography
    _, _, _, df_series = seed_data.build_dataset()
    district_names = [d for d, *_ in seed_data.DISTRICTS]
    weights = [seed_data.weight_of(d) for d in district_names]

    rows = []
    for idx, name in enumerate(district_names):
        df_row = {code: df_series[code][idx] for code in df_series}
        df_row["district"] = name
        raw = raw_profile(df_row, name)
        rows.append((name, raw))

    # calibrate each statistic to its national anchor (population-weighted)
    calibrated: dict[str, list[tuple[str, float]]] = {}

    # ---- OFFICIAL provincial FIES fit (Western 23 / Southern 16 / Kigali 4 /
    # Eastern 14; Northern is the residual that makes the national mean 17). --
    province_rows: dict[str, list[int]] = {}
    for i, (_n, prov, _area, *_rest) in enumerate(seed_data.DISTRICTS):
        province_rows.setdefault(prov, []).append(i)

    for field in ("fies_moderate_severe_pct", "fies_severe_pct"):
        lo, hi = BOUNDS[field]
        series_by_district: dict[str, float] = {}
        covered = 0.0
        covered_weight = 0.0
        for prov, idxs in province_rows.items():
            if field == "fies_moderate_severe_pct" and prov in PROVINCIAL_FIES_TARGETS:
                target = PROVINCIAL_FIES_TARGETS[prov]
            elif field == "fies_moderate_severe_pct":
                continue  # Northern fitted as residual afterwards
            else:
                target = ANCHORS[field]
            prov_values = [rows[i][1][field] for i in idxs]
            prov_weights = [weights[i] for i in idxs]
            fitted = seed_data.calibrate_series(
                prov_values, prov_weights, target, lo, hi, decimals=2
            )
            for i, v in zip(idxs, fitted):
                series_by_district[district_names[i]] = v
            covered += sum(v * w for v, w in zip(fitted, prov_weights))
            covered_weight += sum(prov_weights)
        if field == "fies_moderate_severe_pct":
            national = ANCHORS["fies_moderate_severe_pct"]
            total_w = sum(weights)
            north_idx = province_rows["Northern Province"]
            north_w = sum(weights[i] for i in north_idx)
            north_target = max(
                BOUNDS[field][0],
                (national * total_w - covered) / north_w,
            )
            north_values = [rows[i][1][field] for i in north_idx]
            north_weights = [weights[i] for i in north_idx]
            fitted = seed_data.calibrate_series(
                north_values, north_weights, north_target, lo, hi, decimals=2
            )
            for i, v in zip(north_idx, fitted):
                series_by_district[district_names[i]] = v
        calibrated[field] = [
            (d, round(series_by_district[d], 2)) for d in district_names
        ]

    for field in ANCHORS:
        if field in calibrated:
            continue
        values = [rows[i][1][field] for i in range(len(rows))]
        lo, hi = BOUNDS[field]
        series = seed_data.calibrate_series(values, weights, ANCHORS[field], lo, hi)
        calibrated[field] = list(zip(district_names, series))

    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = factory()
    try:
        regions = session.query(Region).all()
        region_map = {r.district: r.id for r in regions}
        missing = [d for d in district_names if d not in region_map]
        if missing:
            raise RuntimeError(
                "regions table lacks districts: run seed_data.py first — missing "
                + ", ".join(missing)
            )

        for name in district_names:
            family = {f: dict(calibrated[f])[name] for f in ANCHORS}
            existing = (
                session.query(DistrictCfsvaMetrics)
                .filter_by(region_id=region_map[name], survey_year=CFSVA_YEAR)
                .one_or_none()
            )
            if existing is None:
                session.add(DistrictCfsvaMetrics(
                    region_id=region_map[name],
                    survey_year=CFSVA_YEAR,
                    **family,
                ))
            else:
                for field, val in family.items():
                    setattr(existing, field, val)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
    return calibrated, {name: region_map[name] for name in district_names}


def provincial_check(engine):
    """Per-province population-weighted FIES means for the official split."""
    from sqlalchemy import text
    query = text("""
        SELECT r.province,
               SUM(t.fies_moderate_severe_pct * r.population_weight) / SUM(r.population_weight) AS fies,
               COUNT(*) AS rows
        FROM district_cfsva_metrics t JOIN regions r ON t.region_id = r.id
        WHERE t.survey_year = :yr
        GROUP BY r.province
        ORDER BY r.province
    """)
    return {
        row[0]: (float(row[1]), int(row[2]))
        for row in engine.connect().execute(query, {"yr": CFSVA_YEAR}).fetchall()
    }


def national_check(engine):
    from sqlalchemy import text
    query = text("""
        SELECT SUM(t.fies_moderate_severe_pct * r.population_weight) / SUM(r.population_weight) AS fies,
               SUM(t.food_consumption_score * r.population_weight) / SUM(r.population_weight) AS fcs,
               SUM(t.hdds * r.population_weight) / SUM(r.population_weight) AS hdds,
               SUM(t.stunting_pct * r.population_weight) / SUM(r.population_weight) AS stunting,
               COUNT(*) AS rows
        FROM district_cfsva_metrics t JOIN regions r ON t.region_id = r.id
        WHERE t.survey_year = :yr
    """)
    row = engine.connect().execute(query, {"yr": CFSVA_YEAR}).fetchone()
    return row


def print_summary(calibrated, checkrow):
    print("\n=== CFSVA 2024 seed summary ===")
    print("Population-weighted national means vs anchors:")
    for field, anchor in ANCHORS.items():
        values = [v for _d, v in calibrated[field]]
        ws = [seed_data.weight_of(d) for d, _v in calibrated[field]]
        mean = sum(v * w for v, w in zip(values, ws)) / sum(ws)
        print(f"  {field:<28} {mean:7.2f} (anchor {anchor})")
    if checkrow is not None:
        fies, fcs, hdds, stunting, nrows = checkrow
        print(f"\nDB check: rows={nrows}, fies={fies:.2f}, fcs={fcs:.2f}, hdds={hdds:.2f}, stunting={stunting:.2f}")
    print()


def main():
    parser = argparse.ArgumentParser(description="Seed the CFSVA 2024 layer (district_cfsva_metrics table)")
    parser.add_argument("--url", default=os.getenv("DATABASE_URL"))
    parser.add_argument("--drop-cfsva-first", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.dry_run or not args.url:
        if not args.url and not args.dry_run:
            print("No --url given; showing anchors only.", file=sys.stderr)
        print("Anchors:", {k: ANCHORS[k] for k in sorted(ANCHORS)})
        # quick calibration sanity using seed_data machinery
        names = [d for d, *_ in seed_data.DISTRICTS]
        ws = [seed_data.weight_of(d) for d in names]
        probe = [seed_data.stable_jitter(n, f"cfsva-{f}") * seed_data.JITTER_AMPLITUDE
                 for n in names for f in ("fies_moderate_severe_pct",)]
        print(f"[dry-run] districts={len(names)} | jitter spread sample: {probe[0]:+.3f} … {probe[-1]:+.3f}")
        return 0

    engine = create_engine(
        args.url,
        pool_pre_ping=True,
        connect_args=({} if args.url.startswith("sqlite") else {"connect_timeout": 5}),
    )
    calibrated, region_ids = seed_cfsva(engine, drop_cfsva_first=args.drop_cfsva_first)
    print_summary(calibrated, national_check(engine))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
