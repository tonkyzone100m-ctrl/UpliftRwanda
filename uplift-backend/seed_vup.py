#!/usr/bin/env python3
"""VUP seeder — Vision Umurenge Programme beneficiary & operations layer.

NON-DESTRUCTIVE companion to seed_data.py. Fills `district_vup_metrics` ONLY
(one row per district x 2025 vintage). Requires `regions` to exist first.

What is OFFICIAL vs MODELLED (the module labels both on screen):
  OFFICIAL (EICV7 VUP 2025 + hackathon brief):
    * poverty incidence among VUP beneficiary households .... 41.0%
    * extreme-poverty share among beneficiaries ............. 12.5%  (moderate = 41 - 12.5 = 28.5)
    * direct-support engagement baseline ..................... 9.5% of households (seed_data anchor)
    * public-works engagement baseline ...................... 21.0% of households members (seed_data anchor)
  MODELLED (calibrated stand-in, same as every other district panel layer):
    * component caseloads (DS / cPW / ePW / NSDS / FS) — distributed across
      districts with a poverty-weighted share of plausible national totals
      and deterministic md5 jitter so repeated runs are byte-identical
    * payment timeliness (91% within the statutory window)
    * digital disbursement mix: Umurenge SACCO 61% · Mobile Money 24% · cash 15%

Design: VUP intensity follows poverty (.deep_rural archetype districts carry
the largest caseloads); DS/NSDS target the ultra-poor (Ubudehe 1), public
works follow working-capacity density, and FS caseloads follow SACCO coverage.

Usage:
    python3 seed_vup.py --url $DATABASE_URL --dry-run
    python3 seed_vup.py --url $DATABASE_URL --drop-vup-first
"""

from __future__ import annotations

import argparse
import os
import sys

from sqlalchemy import create_engine

import seed_data

VUP_YEAR = 2025

# ---------------------------------------------------------------------------
# 1. Anchors (population-weighted calibration targets)
# ---------------------------------------------------------------------------

ANCHORS = {
    # OFFICIAL — EICV7 VUP 2025 module / hackathon brief
    "poverty_among_beneficiaries": 41.0,
    "extreme_among_beneficiaries": 12.5,
    # MODELLED — operational-efficiency targets (programme-side)
    "payment_timeliness_pct": 91.0,
    "sacco_disbursement_pct": 61.0,
    "momo_disbursement_pct": 24.0,
    "cash_disbursement_pct": 15.0,   # must stay = 100 - sacco - momo
}

BOUNDS = {
    "poverty_among_beneficiaries": (22.0, 62.0),
    "extreme_among_beneficiaries": (4.0, 26.0),
    "payment_timeliness_pct": (74.0, 99.0),
    "sacco_disbursement_pct": (40.0, 78.0),
    "momo_disbursement_pct": (8.0, 40.0),
    "cash_disbursement_pct": (5.0, 30.0),
}

# MODELLED national component caseloads (annual beneficiaries) — the district
# split is calibrated to distribute EXACTLY these totals across all 30
# districts (integers), defensively greater than any plausible audit.
NATIONAL_COMPONENTS = {
    "beneficiaries_ds": 131_500,     # Direct Support (Ubudehe 1 households)
    "beneficiaries_cpw": 246_000,    # Classic Public Works
    "beneficiaries_epw": 158_500,    # Expanded Public Works (lighter/seasonal works)
    "beneficiaries_nsds": 47_200,    # Nutrition-Sensitive Direct Support
    "beneficiaries_fs": 88_600,      # Financial Services (VUP loans & SACCO bonds)
}

COMPONENT_LABELS = {
    "beneficiaries_ds": "Direct Support (DS)",
    "beneficiaries_cpw": "Classic Public Works (cPW)",
    "beneficiaries_epw": "Expanded Public Works (ePW)",
    "beneficiaries_nsds": "Nutrition-Sensitive Direct Support (NSDS)",
    "beneficiaries_fs": "Financial Services (FS)",
}

JITTER_POP = 1.2

# Component intensity covariance with the calibrated FinScope/EICV7 geography:
# share_i = povertypull * (poverty_gap_i) + basetone * (archetype) + jitter,
# then `calibrate_share` scales the vector to sum to exactly the national total.
COMPONENT_INTENSITY = {
    #            poverty weight   base(itself)   component-specific nuance
    "beneficiaries_ds":  {"poverty": 2.6, "base": 1.0, "floor": 0.6},
    "beneficiaries_cpw": {"poverty": 2.2, "base": 1.0, "floor": 0.5},
    "beneficiaries_epw": {"poverty": 1.6, "base": 1.0, "floor": 0.4},
    "beneficiaries_nsds": {"poverty": 3.0, "base": 1.0, "floor": 0.5},
    "beneficiaries_fs":  {"poverty": 1.1, "base": 1.0, "floor": 0.35},
}

# Vulnerability overrides: chronically poor districts carry above-average
# VUP caseloads per capita (Southern deep rural + Nyamagabe/Kirehe/Bugesera).
CASELOAD_OVERRIDES = {
    "Nyaruguru": 1.12, "Gisagara": 1.10, "Ruhango": 1.05, "Nyamagabe": 1.11,
    "Kirehe": 1.08, "Bugesera": 1.06, "Burera": 1.06, "Gakenke": 1.05,
    "Karongi": 1.07, "Nyamasheke": 1.07, "Rutsiro": 1.09, "Ngororero": 1.08,
    "Nyabihu": 1.04,
    # Kigali core: small relative caseload (urban targeting elsewhere)
    "Gasabo": 0.95, "Kicukiro": 0.94, "Nyarugenge": 0.96,
}


def _district_profile_params(district):
    """Covariates: poverty + social-protection reach from the canonical panel."""
    district_names = [d for d, *_ in seed_data.DISTRICTS]
    idx = district_names.index(district)
    _, _, _, df_series = seed_data.build_dataset()
    poverty = df_series["poverty_headcount"][idx]
    social = df_series["social_protection"][idx]
    return poverty, social, idx


def build_panel():
    """Returns (rows: {district: dict), national_totals_check, checks)."""
    district_names = [d for d, *_ in seed_data.DISTRICTS]
    weights_raw = [seed_data.weight_of(d) for d in district_names]
    weight_total = sum(weights_raw)

    _, _, _, df_series = seed_data.build_dataset()
    poverty_anchor = seed_data.TARGETS["poverty"]      # 27.4
    poverty_series = df_series["poverty_headcount"]

    # ---- component share vectors -----------------------------------------
    shares: dict[str, list[float]] = {}
    for component, spec in COMPONENT_INTENSITY.items():
        raw = []
        for i, name in enumerate(district_names):
            pov_gap = max(-0.6, (poverty_series[i] - poverty_anchor) / poverty_anchor)
            base = spec["base"] * weights_raw[i] / weight_total
            pull = spec["poverty"] * pov_gap
            jitter = seed_data.stable_jitter(name, f"vup-{component}") * JITTER_POP * 0.004
            multiplier = CASELOAD_OVERRIDES.get(name, 1.0)
            raw.append(max(spec["floor"] * base, (base + pull * base * 0.4) * multiplier + pull * base + jitter))
        shares[component] = raw

    # calibrate each component's shares to sum to exactly the national total
    component_values: dict[str, list[int]] = {c: [] for c in NATIONAL_COMPONENTS}
    for component, total in NATIONAL_COMPONENTS.items():
        raw = shares[component]
        s = sum(raw)
        scaled = [max(0.0, v / s * total) for v in raw]
        # largest-remainder rounding keeps integers summing EXACTLY to the total
        floors = [int(v) for v in scaled]
        remainder = sorted(range(len(scaled)), key=lambda i: scaled[i] - floors[i], reverse=True)
        allocated = sum(floors)
        counter = 0
        while allocated < total:
            floors[remainder[counter % len(remainder)]] += 1
            counter += 1
            allocated += 1
        component_values[component] = floors

    # ---- poverty profile among beneficiaries ------------------------------
    # District poverty gap drives beneficiary poverty (deeper poverty districts
    # enroll needier caseloads), then the series is calibrated to 41% national.
    pov_raw = []
    ext_raw = []
    for i, name in enumerate(district_names):
        pov_gap = (poverty_series[i] - poverty_anchor)
        pov_raw.append(
            ANCHORS["poverty_among_beneficiaries"] + pov_gap * 0.9
            + seed_data.stable_jitter(name, "vup-popvty") * JITTER_POP
        )
        ext_raw.append(
            ANCHORS["extreme_among_beneficiaries"] + pov_gap * 0.42
            + seed_data.stable_jitter(name, "vup-extreme") * JITTER_POP * 0.5
        )
    pov_cal = seed_data.calibrate_series(
        pov_raw, weights_raw, ANCHORS["poverty_among_beneficiaries"], *BOUNDS["poverty_among_beneficiaries"])
    ext_cal = seed_data.calibrate_series(
        ext_raw, weights_raw, ANCHORS["extreme_among_beneficiaries"], *BOUNDS["extreme_among_beneficiaries"])

    # ---- operational efficiency ------------------------------------------
    timeliness_raw = [
        ANCHORS["payment_timeliness_pct"]
        - seed_data.stable_jitter(d, "vup-timeliness") * JITTER_POP
        + (df_series["mobile_money"][i] - seed_data.TARGETS["mobile_money"]) * 0.22
        for i, d in enumerate(district_names)
    ]
    timeliness = seed_data.calibrate_series(
        timeliness_raw, weights_raw, ANCHORS["payment_timeliness_pct"], *BOUNDS["payment_timeliness_pct"])

    def channel_series(key, covariate, cov_target, sens):
        raw = []
        for i, name in enumerate(district_names):
            cov_gap = (covariate[i] - cov_target) / max(1e-6, cov_target)
            raw.append(
                ANCHORS[key] + cov_gap * sens
                + seed_data.stable_jitter(name, f"vup-{key}") * JITTER_POP * 0.6
            )
        return seed_data.calibrate_series(raw, weights_raw, ANCHORS[key], *BOUNDS[key])

    sacco = channel_series("sacco_disbursement_pct", df_series["formal_savings"],
                           seed_data.TARGETS["formal_savings"], 4.5)
    momo = channel_series("momo_disbursement_pct", df_series["mobile_money"],
                          seed_data.TARGETS["mobile_money"], 7.0)
    cash = [round(min(BOUNDS["cash_disbursement_pct"][1],
                      max(BOUNDS["cash_disbursement_pct"][0],
                          100.0 - a - b)), 1)
            for a, b in zip(sacco, momo)]

    rows = {}
    for i, name in enumerate(district_names):
        poverty_v = pov_cal[i]
        extreme_v = min(ext_cal[i], poverty_v - 2.0)   # extreme strictly inside poverty
        rows[name] = {
            "survey_year": VUP_YEAR,   # not itself a column; stripped at seeding
            "beneficiaries_ds": component_values["beneficiaries_ds"][i],
            "beneficiaries_cpw": component_values["beneficiaries_cpw"][i],
            "beneficiaries_epw": component_values["beneficiaries_epw"][i],
            "beneficiaries_nsds": component_values["beneficiaries_nsds"][i],
            "beneficiaries_fs": component_values["beneficiaries_fs"][i],
            "poverty_rate_among_beneficiaries": poverty_v,
            "extreme_among_beneficiaries": round(extreme_v, 1),
            "payment_timeliness_pct": timeliness[i],
            "sacco_disbursement_pct": sacco[i],
            "momo_disbursement_pct": momo[i],
            "cash_disbursement_pct": cash[i],
        }
    checks = {c: sum(component_values[c]) for c in NATIONAL_COMPONENTS}
    return rows, checks


def seed_vup(engine, drop_vup_first=False):
    """Seed `district_vup_metrics` (create-if-missing, upsert rows)."""
    from sqlalchemy.orm import sessionmaker

    from models import Base, DistrictVupMetrics, Region

    if drop_vup_first:
        DistrictVupMetrics.__table__.drop(engine, checkfirst=True)
    Base.metadata.create_all(engine, tables=[DistrictVupMetrics.__table__])

    rows, checks = build_panel()
    district_names = [d for d, *_ in seed_data.DISTRICTS]

    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = factory()
    try:
        regions = session.query(Region).all()
        region_map = {r.district: r.id for r in regions}
        missing = [d for d in district_names if d not in region_map]
        if missing:
            raise RuntimeError(
                "regions table lacks districts - run seed_data.py first: missing "
                + ", ".join(missing)
            )
        for name in district_names:
            payload = {k: v for k, v in rows[name].items() if k != "survey_year"}
            existing = (
                session.query(DistrictVupMetrics)
                .filter_by(region_id=region_map[name], survey_year=VUP_YEAR)
                .one_or_none()
            )
            if existing is None:
                session.add(DistrictVupMetrics(
                    region_id=region_map[name], survey_year=VUP_YEAR, **payload,
                ))
            else:
                for k, v in payload.items():
                    setattr(existing, k, v)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
    return rows, checks, {name: region_map[name] for name in district_names}


VUP_COLUMNS = (
    "beneficiaries_ds", "beneficiaries_cpw", "beneficiaries_epw",
    "beneficiaries_nsds", "beneficiaries_fs",
    "poverty_rate_among_beneficiaries", "extreme_among_beneficiaries",
    "payment_timeliness_pct", "sacco_disbursement_pct",
    "momo_disbursement_pct", "cash_disbursement_pct",
)


def national_check(engine):
    from sqlalchemy import text as sql_text

    return engine.connect().execute(sql_text("""
        SELECT SUM(t.beneficiaries_ds + t.beneficiaries_cpw + t.beneficiaries_epw
                   + t.beneficiaries_nsds + t.beneficiaries_fs) AS total,
               SUM(CAST(t.poverty_rate_among_beneficiaries AS real) * r.population_weight) / SUM(r.population_weight) AS pov,
               SUM(CAST(t.payment_timeliness_pct AS real) * r.population_weight) / SUM(r.population_weight) AS tim,
               COUNT(*) AS rows
        FROM district_vup_metrics t JOIN regions r ON t.region_id = r.id
        WHERE t.survey_year = :yr
    """), {"yr": VUP_YEAR}).fetchone()


def print_summary(rows, checks, checkrow):
    print("\n=== VUP 2025 seed summary ===")
    for component, total in NATIONAL_COMPONENTS.items():
        print(f"  {component:<22} {checks[component]:>9,d} (national total {total:,})")
    print("  poverty among beneficiaries:",
          f"{sum(r['poverty_rate_among_beneficiaries'] * seed_data.weight_of(d) for d, r in rows.items()) / sum(seed_data.weight_of(d) for d in rows):.2f}",
          f"(anchor {ANCHORS['poverty_among_beneficiaries']})")
    if checkrow is not None:
        print(f"  DB check: total={checkrow[0]:,} pov={checkrow[1]:.2f} timeliness={checkrow[2]:.2f} rows={checkrow[3]}")
    print()


def main():
    parser = argparse.ArgumentParser(description="Seed the VUP 2025 layer (district_vup_metrics)")
    parser.add_argument("--url", default=os.getenv("DATABASE_URL"))
    parser.add_argument("--drop-vup-first", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    rows, checks = build_panel()
    if args.dry_run or not args.url:
        if not args.url and not args.dry_run:
            print("No --url given; running dry-run.", file=sys.stderr)
        print_summary(rows, checks, None)
        return 0

    engine = create_engine(
        args.url, pool_pre_ping=True,
        connect_args=({} if args.url.startswith("sqlite") else {"connect_timeout": 5}),
    )
    rows, checks, _ids = seed_vup(engine, drop_vup_first=args.drop_vup_first)
    print_summary(rows, checks, national_check(engine))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
