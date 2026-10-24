#!/usr/bin/env python3
"""LFS 2025 seeder — labour-market layer (Module A: Labour Market Intelligence).

NON-DESTRUCTIVE companion to seed_data.py. Fills:
  * district_lfs_metrics   — wide panel, one row per district x 2025 vintage
  * district_lfs_segments  — long/tidy disaggregation (gender / education /
                             disability x indicator)
and completes the official 2025 survey_metrics vintage for the 5 canonical
LFS indicator codes across ALL 30 districts (the ministerial CSV
ingest covered only 6 districts, so /api/metrics vintages become consistent —
upserting, never destructive: no existing row is deleted).

Calibration contract (population-weighted national means hit EXACTLY):
  * unemployment_rate ................... 12.4%  (OFFICIAL RLFS 2025 headline)
  * youth_neet_rate (16-30) ............. 24.5%  (OFFICIAL RLFS 2025 NEET)
  * LFPR gap (male - female) ............ 14.3 pp (OFFICIAL RLFS 2025)
  * employment_ratio = lfpr x (1 - unemployment/100)  (derived identity)
  * inactivity = 100 - lfpr             (derived identity)
TVET-vs-General unemployment, disability rates and the high-vulnerability
Southern districts (Nyaruguru, Gisagara, Ruhango) are profiled per archetype
plus named overrides, exactly like the FinScope/EICV7 calibration.

How the district numbers are produced
-------------------------------------
1. Each district inherits its FinScope/EICV7 socio-economic archetype
   (kigali_core → deep_rural) expressed as percentage-point deviations.
2. Deterministic md5 jitter of ±0.7 pp adds texture (reproducible runs).
3. Series are CALIBRATED so the population-weighted national mean lands on
   the anchor; identities above keep employment_ratio/inactivity internally
   consistent instead of being independently jittered.

Usage:
    python3 seed_lfs.py --url $DATABASE_URL --dry-run
    python3 seed_lfs.py --url $DATABASE_URL --drop-lfs-first
"""

from __future__ import annotations

import argparse
import os
import sys

from sqlalchemy import create_engine

import seed_data

LFS_YEAR = 2025

# ---------------------------------------------------------------------------
# 1. Official national anchors (population-weighted calibration targets)
# ---------------------------------------------------------------------------

ANCHORS = {
    # OFFICIAL RLFS 2025 headline (hackathon brief + most recent NISR bulletin)
    "unemployment_rate": 12.4,
    "youth_neet_rate": 24.5,
    "lfpr_gender_gap_pp": 14.3,
    # OFFICIAL-edit microdata sample vintage (MEAL 2025 ministerial ingest):
    # the six ingested districts averaged ~52.7 — kept as the panel-scale alias.
    "labor_underutilization_rate": 52.6,
    "informal_employment_rate": 85.6,   # TUNABLE
    "time_underemployment_rate": 5.1,   # TUNABLE
    "youth_unemployment_rate": 13.9,    # TUNABLE
    "lfpr": 66.3,                       # ages 16+ (TUNABLE)
    "unemployment_gender_gap_pp": 3.6,  # female exceeds male (TUNABLE pp)
    # Education outcomes: TVET graduates outperform general-stream leavers
    "tvet_unemployment_rate": 7.9,
    "primary_unemployment_rate": 9.8,
    "secondary_general_unemployment_rate": 16.8,
    "tertiary_unemployment_rate": 5.5,
    "lfpr_primary": 62.6,
    "lfpr_secondary_general": 57.9,
    "lfpr_tvet": 72.4,
    "lfpr_tertiary": 75.1,
    # Disability-status split (rate reduction among persons with disability)
    "disability_lfpr": 53.5,
    "without_disability_lfpr": 67.1,
    "disability_unemployment_rate": 18.9,
    "without_disability_unemployment_rate": 12.0,
    "youth_neet_gender_gap_pp": 4.2,    # female exceeds male (TUNABLE pp)
}

BOUNDS = {
    "unemployment_rate": (5.0, 22.0),
    "youth_neet_rate": (12.0, 38.0),
    "labor_underutilization_rate": (32.0, 68.0),
    "informal_employment_rate": (55.0, 96.0),
    "time_underemployment_rate": (2.0, 9.5),
    "youth_unemployment_rate": (7.0, 26.0),
    "lfpr": (52.0, 76.0),
    "unemployment_gender_gap_pp": (1.0, 7.5),
    "tvet_unemployment_rate": (3.0, 15.0),
    "primary_unemployment_rate": (4.0, 16.0),
    "secondary_general_unemployment_rate": (9.0, 26.0),
    "tertiary_unemployment_rate": (2.0, 12.0),
    "lfpr_primary": (52.0, 70.0),
    "lfpr_secondary_general": (46.0, 66.0),
    "lfpr_tvet": (62.0, 80.0),
    "lfpr_tertiary": (66.0, 84.0),
    "disability_lfpr": (38.0, 65.0),
    "without_disability_lfpr": (56.0, 74.0),
    "disability_unemployment_rate": (10.0, 32.0),
    "without_disability_unemployment_rate": (5.0, 22.0),
    "youth_neet_gender_gap_pp": (1.5, 8.0),
    "lfpr_gender_gap_pp": (9.0, 18.0),
}

JITTER_PP = 1.4  # ±0.7 pp deterministic texture

# ---------------------------------------------------------------------------
# 2. Archetype deviations (percentage points) + named vulnerable districts
# ---------------------------------------------------------------------------

# Urban labour markets: higher unemployment (job seekers converge on cities)
# but higher participation, lower informality and lower NEET. Deep rural:
# subsistence farming absorbs labour (low measured unemployment, high
# inactivity, high informality, high youth NEET).
DEVIATIONS = {
    "employment_ratio":        {"kigali_core": +1.4, "secondary_city": +0.7, "commercial_rural": +0.1,
                               "emerging_rural": -0.9, "deep_rural": -2.1},
    "unemployment_rate":       {"kigali_core": +2.4, "secondary_city": +1.1, "commercial_rural": -1.6,
                               "emerging_rural": -2.3, "deep_rural": -2.9},
    "labor_underutilization_rate": {"kigali_core": -1.9, "secondary_city": -0.6, "commercial_rural": +0.6,
                               "emerging_rural": +1.8, "deep_rural": +2.6},
    "informal_employment_rate": {"kigali_core": -13.5, "secondary_city": -6.5, "commercial_rural": +2.5,
                               "emerging_rural": +5.0, "deep_rural": +8.0},
    "time_underemployment_rate": {"kigali_core": -1.2, "secondary_city": -0.4, "commercial_rural": +0.4,
                               "emerging_rural": +0.9, "deep_rural": +1.5},
    "youth_unemployment_rate": {"kigali_core": +1.6, "secondary_city": +0.8, "commercial_rural": -1.9,
                               "emerging_rural": -2.8, "deep_rural": -3.2},
    "youth_neet_rate":         {"kigali_core": -0.9, "secondary_city": -0.4, "commercial_rural": +0.6,
                               "emerging_rural": +1.9, "deep_rural": +3.2},
    "lfpr":                    {"kigali_core": +2.8, "secondary_city": +1.4, "commercial_rural": -0.6,
                               "emerging_rural": -2.0, "deep_rural": -3.8},
    # Gender LFPR gap narrows in urban markets (services absorb women) and
    # widens in deep rural (subsistence assignments to men, care burden).
    "lfpr_gender_gap_pp":      {"kigali_core": -1.4, "secondary_city": -0.7, "commercial_rural": +0.2,
                               "emerging_rural": +0.9, "deep_rural": +1.6},
    "unemployment_gender_gap_pp": {"kigali_core": +0.9, "secondary_city": +0.5, "commercial_rural": +0.1,
                               "emerging_rural": -0.3, "deep_rural": -0.5},
    "tvet_unemployment_rate":  {"kigali_core": -0.9, "secondary_city": -0.4, "commercial_rural": +0.1,
                               "emerging_rural": +0.8, "deep_rural": +1.2},
    "secondary_general_unemployment_rate": {"kigali_core": +1.6, "secondary_city": +0.8, "commercial_rural": -1.2,
                               "emerging_rural": -1.9, "deep_rural": -2.4},
    "primary_unemployment_rate": {"kigali_core": -0.4, "secondary_city": -0.1, "commercial_rural": +0.3,
                               "emerging_rural": +0.9, "deep_rural": +1.3},
    "tertiary_unemployment_rate": {"kigali_core": +0.7, "secondary_city": +0.3, "commercial_rural": -0.3,
                               "emerging_rural": -0.5, "deep_rural": -0.6},
    "lfpr_primary":            {"kigali_core": -2.4, "secondary_city": -1.0, "commercial_rural": +0.6,
                               "emerging_rural": +2.0, "deep_rural": +3.4},
    "lfpr_secondary_general":  {"kigali_core": -2.1, "secondary_city": -0.8, "commercial_rural": +0.4,
                               "emerging_rural": +1.6, "deep_rural": +2.8},
    "lfpr_tvet":               {"kigali_core": +1.9, "secondary_city": +0.9, "commercial_rural": -0.5,
                               "emerging_rural": -1.7, "deep_rural": -2.8},
    "lfpr_tertiary":           {"kigali_core": +1.4, "secondary_city": +0.6, "commercial_rural": -0.4,
                               "emerging_rural": -1.3, "deep_rural": -2.2},
    # Disability: participation gap narrows in urban markets
    "disability_lfpr":         {"kigali_core": -2.6, "secondary_city": -1.1, "commercial_rural": +0.7,
                               "emerging_rural": +2.2, "deep_rural": +3.6},
    "without_disability_lfpr": {"kigali_core": +3.1, "secondary_city": +1.5, "commercial_rural": -0.7,
                               "emerging_rural": -2.2, "deep_rural": -4.1},
    "disability_unemployment_rate": {"kigali_core": -1.6, "secondary_city": -0.6, "commercial_rural": +0.4,
                               "emerging_rural": +1.1, "deep_rural": +1.8},
    "without_disability_unemployment_rate": {"kigali_core": +2.6, "secondary_city": +1.2, "commercial_rural": -1.7,
                               "emerging_rural": -2.5, "deep_rural": -3.1},
    "youth_neet_gender_gap_pp": {"kigali_core": -0.7, "secondary_city": -0.3, "commercial_rural": +0.1,
                               "emerging_rural": +0.4, "deep_rural": +0.8},
}

# High-vulnerability Southern districts (hackathon brief: Nyaruguru, Gisagara,
# Ruhango) — nudged so they surface at the worst ranks for inactivity/NEET.
OVERRIDES = {
    "Nyaruguru": {"lfpr": -2.4, "youth_neet_rate": +2.2, "informal_employment_rate": +1.5},
    "Gisagara":  {"lfpr": -2.8, "youth_neet_rate": +1.8, "labor_underutilization_rate": +1.4},
    "Ruhango":   {"lfpr": -2.2, "youth_neet_rate": +1.4},
    "Nyamagabe": {"lfpr": -1.6, "youth_neet_rate": +1.2},  # Nyamagabe also chronically vulnerable
}

# ---------------------------------------------------------------------------
# 3. Panel builder + calibration
# ---------------------------------------------------------------------------


def _dev(district, arch, key):
    return DEVIATIONS.get(key, {}).get(arch, 0.0)


def _jittered(district, key, base, lo, hi):
    j = seed_data.stable_jitter(district, f"lfs-{key}") * JITTER_PP
    v = base + j
    if district in OVERRIDES and key in OVERRIDES[district]:
        v += OVERRIDES[district][key]
    return min(hi, max(lo, v))


def build_raw_profiles():
    """District -> {anchor-key: uncalibrated plausible value} for LFS fields."""
    profiles = {}
    for district, province, area, pop, arch, _ov in seed_data.DISTRICTS:
        raw = {}
        for key in ANCHORS:
            lo, hi = BOUNDS[key]
            raw[key] = min(hi, max(lo, _dev(district, arch, key) + _jittered(district, key, ANCHORS[key], lo, hi)))
        profiles[district] = raw
    return profiles


FEMALE_SHARE = 0.50  # adult composition approximation used for the gender split


def _calibrate(weights, names, values, key, decimals=1):
    return seed_data.calibrate_series(
        values, weights, ANCHORS[key], *BOUNDS[key], decimals=decimals
    )


def build_panel():
    """Calibrated wide + segment panel.

    Returns (wide: {district: {col: value}}, segments: {dim: (...)}-ready rows).
    """
    profiles = build_raw_profiles()
    district_names = [d for d, *_ in seed_data.DISTRICTS]
    weights = [seed_data.weight_of(d) for d in district_names]

    def series_for(key, decimals=1):
        vals = [profiles[d][key] for d in district_names]
        return _calibrate(weights, district_names, vals, key, decimals=decimals)

    wide = {d: {} for d in district_names}

    # --- headline participation / unemployment / employer identity ------
    unemployment = series_for("unemployment_rate")
    lfpr = series_for("lfpr")
    youth_unemployment = series_for("youth_unemployment_rate")
    youth_neet = series_for("youth_neet_rate")
    gender_gap = series_for("lfpr_gender_gap_pp")
    unemp_gap = series_for("unemployment_gender_gap_pp")
    neet_gap = series_for("youth_neet_gender_gap_pp")
    underutil = series_for("labor_underutilization_rate")
    informal = series_for("informal_employment_rate")
    time_underemployment = series_for("time_underemployment_rate")

    # education participation + unemployment segments
    tvet_u = series_for("tvet_unemployment_rate")
    general_u = series_for("secondary_general_unemployment_rate")
    primary_u = series_for("primary_unemployment_rate")
    tertiary_u = series_for("tertiary_unemployment_rate")
    lfpr_tv = series_for("lfpr_tvet")
    lfpr_gen = series_for("lfpr_secondary_general")
    lfpr_pri = series_for("lfpr_primary")
    lfpr_ter = series_for("lfpr_tertiary")

    disability_l = series_for("disability_lfpr")
    disability_u = series_for("disability_unemployment_rate")
    nodis_l = series_for("without_disability_lfpr")
    nodis_u = series_for("without_disability_unemployment_rate")

    for i, district in enumerate(district_names):
        u = unemployment[i]
        l = lfpr[i]
        gap = gender_gap[i]
        g_u = unemp_gap[i]
        g_n = neet_gap[i]
        employed_ratio = round(l * (100.0 - u) / 100.0, 1)
        wide[district].update({
            "survey_year": LFS_YEAR,
            "unemployment_rate": u,
            "employment_ratio": employed_ratio,
            "lfpr": l,
            "inactivity_rate": round(100.0 - l, 1),
            "labor_underutilization_rate": underutil[i],
            "informal_employment_rate": informal[i],
            "time_underemployment_rate": time_underemployment[i],
            "youth_unemployment_rate": youth_unemployment[i],
            "youth_neet_rate": youth_neet[i],
            "lfpr_male": round(l + FEMALE_SHARE * gap, 1),
            "lfpr_female": round(l - (1 - FEMALE_SHARE) * gap, 1),
            "unemployment_rate_male": round(u - FEMALE_SHARE * g_u, 1),
            "unemployment_rate_female": round(u + (1 - FEMALE_SHARE) * g_u, 1),
            "youth_neet_male": round(max(6.0, youth_neet[i] - FEMALE_SHARE * g_n), 1),
            "youth_neet_female": round(min(58.0, youth_neet[i] + (1 - FEMALE_SHARE) * g_n), 1),
            "tvet_unemployment_rate": tvet_u[i],
            "general_education_unemployment_rate": general_u[i],
            "disability_lfpr": disability_l[i],
            "disability_unemployment_rate": disability_u[i],
        })

    # --- long/tidy disaggregation rows ----------------------------------
    def emp(lfpr_value, u_value):
        return round(lfpr_value * (100.0 - u_value) / 100.0, 1)

    segments = []  # (district, dimension, segment, indicator, value)
    for i, district in enumerate(district_names):
        d = wide[district]
        # gender (4 indicators x 2 segments)
        for seg, lkey, ukey in (("male", "lfpr_male", "unemployment_rate_male"),
                                ("female", "lfpr_female", "unemployment_rate_female")):
            l_v, u_v = d[lkey], d[ukey]
            segments += [
                (district, "gender", seg, "lfpr", l_v),
                (district, "gender", seg, "unemployment", u_v),
                (district, "gender", seg, "employment_ratio", emp(l_v, u_v)),
            ]
        # NEET only for gender segments (youth cohort)
        segments += [
            (district, "gender", "male", "neet", d["youth_neet_male"]),
            (district, "gender", "female", "neet", d["youth_neet_female"]),
        ]
        # education (3 indicators x 4 segments; TVET/General mirror wide columns)
        pairs = [
            ("primary", lfpr_pri[i], primary_u[i]),
            ("secondary_general", lfpr_gen[i], general_u[i]),
            ("tvet", lfpr_tv[i], tvet_u[i]),
            ("tertiary", lfpr_ter[i], tertiary_u[i]),
        ]
        for seg, l_v, u_v in pairs:
            segments += [
                (district, "education", seg, "lfpr", round(l_v, 1)),
                (district, "education", seg, "unemployment", round(u_v, 1)),
                (district, "education", seg, "employment_ratio", emp(l_v, u_v)),
            ]
        # disability (3 indicators x 2 segments)
        for seg, l_v, u_v in (
            ("with_disability", disability_l[i], disability_u[i]),
            ("without_disability", nodis_l[i], nodis_u[i]),
        ):
            segments += [
                (district, "disability", seg, "lfpr", round(l_v, 1)),
                (district, "disability", seg, "unemployment", round(u_v, 1)),
                (district, "disability", seg, "employment_ratio", emp(l_v, u_v)),
            ]
    return wide, segments


WIDE_SURVEY_CODES = {
    "unemployment_rate": "unemployment_rate",
    "employment_ratio": "employment_ratio",
    "lfpr": "lfpr",
    "youth_unemployment_rate": "youth_unemployment",
    "labor_underutilization_rate": "labor_underutilization",
}


def _ensure_catalog_codes(session, engine):
    """Get-or-create the 5 canonical LFS codes in the indicators catalog."""
    from models import Indicator

    from seed_data import LFS_INDICATORS

    known = {code for (code,) in session.query(Indicator.indicator_code).all()}
    for code, name, category, unit, description in LFS_INDICATORS:
        if code not in known:
            session.add(Indicator(indicator_code=code, indicator_name=name,
                                  category=category, unit=unit, description=description))
    return session


def seed_lfs(engine, drop_lfs_first=False, upsert_survey_vintage=True):
    """Seed district_lfs_metrics + segments (+ 2025 survey_metrics vintage)."""
    from sqlalchemy.orm import sessionmaker

    from models import Base, DistrictLfsMetrics, DistrictLfsSegment, Indicator, Region, SurveyMetric

    if drop_lfs_first:
        DistrictLfsSegment.__table__.drop(engine, checkfirst=True)
        DistrictLfsMetrics.__table__.drop(engine, checkfirst=True)
    Base.metadata.create_all(engine, tables=[
        DistrictLfsSegment.__table__, DistrictLfsMetrics.__table__,
    ])

    wide, segment_rows = build_panel()
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

        # 0) catalog codes must exist before survey_metrics can reference them
        _ensure_catalog_codes(session, engine)
        session.flush()
        indicator_map = {
            code: id for id, code in
            session.query(Indicator.id, Indicator.indicator_code).all()
        }

        # 1) survey_metrics 2025 vintage (upsert all 30 districts; replaces the
        #    partial 6-district ministerial ingest with a consistent panel).
        vintage_rows = 0
        if upsert_survey_vintage:
            for district in district_names:
                w = wide[district]
                for wcol, code in WIDE_SURVEY_CODES.items():
                    ind_id = indicator_map.get(code)
                    if ind_id is None:
                        continue
                    value = float(w[wcol])
                    existing = (
                        session.query(SurveyMetric)
                        .filter_by(
                            region_id=region_map[district],
                            indicator_id=ind_id,
                            survey_year=LFS_YEAR,
                        )
                        .one_or_none()
                    )
                    if existing is None:
                        session.add(SurveyMetric(
                            region_id=region_map[district], indicator_id=ind_id,
                            survey_year=LFS_YEAR, value=value,
                        ))
                    else:
                        existing.value = value
                    vintage_rows += 1

        # 2) wide panel
        for district in district_names:
            w = wide[district]
            fields = {k: v for k, v in w.items() if k != "survey_year"}
            existing = (
                session.query(DistrictLfsMetrics)
                .filter_by(region_id=region_map[district], survey_year=LFS_YEAR)
                .one_or_none()
            )
            if existing is None:
                session.add(DistrictLfsMetrics(
                    region_id=region_map[district], survey_year=LFS_YEAR, **fields,
                ))
            else:
                for k, v in fields.items():
                    setattr(existing, k, v)

        # 3) long disaggregation rows
        for district, dimension, segment, indicator, value in segment_rows:
            existing = (
                session.query(DistrictLfsSegment)
                .filter_by(
                    region_id=region_map[district], survey_year=LFS_YEAR,
                    dimension=dimension, segment=segment, indicator=indicator,
                )
                .one_or_none()
            )
            if existing is None:
                session.add(DistrictLfsSegment(
                    region_id=region_map[district], survey_year=LFS_YEAR,
                    dimension=dimension, segment=segment,
                    indicator=indicator, value=float(value),
                ))
            else:
                existing.value = float(value)

        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
    return district_names, wide, segment_rows, vintage_rows


# ---------------------------------------------------------------------------
# 4. Verification helpers + CLI
# ---------------------------------------------------------------------------


def national_check(engine):
    from sqlalchemy import text as sql_text

    cols = ["unemployment_rate", "youth_neet_rate", "lfpr", "employment_ratio",
            "labor_underutilization_rate", "informal_employment_rate"]
    cols_sql = ", ".join(
        f"SUM(CAST(t.{c} AS real) * r.population_weight) / SUM(r.population_weight) AS {c}"
        for c in cols
    )
    return engine.connect().execute(sql_text(f"""
        SELECT {cols_sql}, COUNT(*) AS rows
        FROM district_lfs_metrics t JOIN regions r ON t.region_id = r.id
        WHERE t.survey_year = :yr
    """), {"yr": LFS_YEAR}).fetchone()


def gender_check(engine):
    from sqlalchemy import text as sql_text

    return engine.connect().execute(sql_text("""
        SELECT SUM(CAST(t.lfpr_male AS real) * r.population_weight) / SUM(r.population_weight) - 
               SUM(CAST(t.lfpr_female AS real) * r.population_weight) / SUM(r.population_weight) AS gap
        FROM district_lfs_metrics t JOIN regions r ON t.region_id = r.id
        WHERE t.survey_year = :yr
    """), {"yr": LFS_YEAR}).fetchone()


def print_summary(wide, checks):
    print("\n=== LFS 2025 seed summary ===")
    cols = ["unemployment_rate", "youth_neet_rate", "lfpr", "employment_ratio",
            "inactivity_rate", "labor_underutilization_rate", "informal_employment_rate"]
    weights = [seed_data.weight_of(d) for d, *_ in seed_data.DISTRICTS]
    names = [d for d, *_ in seed_data.DISTRICTS]
    totals = sum(weights)
    print("Population-weighted national means (calibrated):")
    for col in cols:
        mean = sum(wide[d][col] * w for d, w in zip(names, weights)) / totals
        print(f"  {col:<30} {mean:7.2f}")
    if checks:
        gap = checks["gender_gap"]
        print(f"  lfpr_gender_gap_pp             {gap:7.2f} (anchor 14.3)")


def main():
    parser = argparse.ArgumentParser(description="Seed the LFS 2025 layer (district_lfs_metrics + segments)")
    parser.add_argument("--url", default=os.getenv("DATABASE_URL"))
    parser.add_argument("--drop-lfs-first", action="store_true")
    parser.add_argument("--no-survey-vintage", action="store_true",
                        help="skip the survey_metrics 2025 vintage upsert")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    wide, segment_rows = build_panel()
    if args.dry_run or not args.url:
        if not args.url and not args.dry_run:
            print("No --url given; running dry-run.", file=sys.stderr)
        print_summary(wide, None)
        print(f"segment rows: {len(segment_rows)}")
        return 0

    engine = create_engine(
        args.url, pool_pre_ping=True,
        connect_args=({} if args.url.startswith("sqlite") else {"connect_timeout": 5}),
    )
    names, wide_out, segments, vintage_rows = seed_lfs(
        engine, drop_lfs_first=args.drop_lfs_first,
        upsert_survey_vintage=not args.no_survey_vintage,
    )
    gap_row = gender_check(engine)
    checkrow = national_check(engine)
    checks = {"gender_gap": float(gap_row[0]) if gap_row else None}
    print_summary(wide_out, checks)
    print(f"survey_metrics 2025 vintage rows upserted: {vintage_rows}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
