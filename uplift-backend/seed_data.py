#!/usr/bin/env python3
"""UpliftRwanda database seeder - FinScope 2024 / EICV7 calibration.

Seats the `regions`, `indicators` and `survey_metrics` tables with a
district-level decomposition of the OFFICIAL national benchmarks:

    FinScope 2024 (NISR / AFI):
      * Overall financial inclusion........... 96% of adults (7.8m)
      * Transactional account uptake.......... 77% (6.2m)
      * Mobile wallet uptake.................. 77% (5.8-6.3m)
      * Formal credit usage................... 24% (1.8m)
      * Formal savings uptake................. 59% (4.8m)
      * Climate shock exposure................ 69% (floods/droughts/storms)
      * Financial health: 10% healthy / 57% coping / 31% vulnerable / 3% extreme
    EICV7 (NISR, 2023/24):
      * poverty headcount..................... 27.4% (headline)
      * extreme poverty....................... 4.5% (headline-derived)
      * social protection programme reach..... 61.3% (composite)

How the district numbers are produced
-------------------------------------
1. Each of the 30 districts is profiled with a socio-economic archetype
   (kigali_core, secondary_city, commercial_rural, emerging_rural, deep_rural)
   expressed as a percentage-point deviation from the national benchmark, plus
   named overrides for documented district realities (drought-prone
   Bugesera/Kirehe, landslide-prone Gakenke, Lake-Kivu coffee/fishing belts).
2. A deterministic (md5-hash) jitter of +-0.6 pp adds district texture without
   masquerading as randomness - repeated runs produce identical tables.
3. Every indicator series is then CALIBRATED so that its population-weighted
   national mean (approximate NISR 2022 census weights) lands exactly on the
   official benchmark - guaranteeing the table aggregates back to the cited
   FinScope/EICV7 statistics.
4. Composite indicators are derived so the data is internally consistent:
      financial_inclusion_rate = transactional_account + informal_gap (77 + 19 = 96)
      financial_exclusion_rate = 100 - inclusion                      (4)
      extremely_vulnerable     = vulnerable * (3 / 31)
      financially_coping       = 100 - healthy - vulnerable - extreme
        (the cited 57% coping reflects rounding in the published report -
         the four cited tiers sum to 101; our rows sum to exactly 100.)

Usage
-----
    python3 seed_data.py                                  # env DATABASE_URL or --url
    python3 seed_data.py --url sqlite:///test.db --drop-existing
    python3 seed_data.py --dry-run                        # validate without writing
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys

# ============================================================================
# 1. Official national benchmarks (population-weighted calibration targets)
# ============================================================================

TARGETS = {
    # FinScope 2024
    "transactional_account": 77.0,   # 6.2m adults
    "mobile_money": 77.0,            # 5.8-6.3m adults
    "formal_credit": 24.0,           # 1.8m adults
    "formal_savings": 59.0,          # 4.8m adults
    "formal_inclusion": 92.0,        # OFFICIAL: 7.5m adults formally served
    "climate_shock": 69.0,
    "informal_gap": 19.0,            # derived: inclusion(96) - accounts(77)
    "financial_health": 10.0,
    "vulnerability": 31.0,
    # EICV7 (2023/24)
    "poverty": 27.4,                 # headline
    "extreme_poverty": 4.5,          # headline-derived
    "social_protection": 61.3,       # composite
    "vup_public_works": 21.0,        # TUNABLE: VUP public-works participation share (EICV7 VUP)
    "vup_direct_support": 9.5,       # TUNABLE: VUP direct-support (grants) share (EICV7 VUP)
    # EICV7 living conditions / infrastructure
    "electricity_access": 72.0,
    "improved_water": 90.0,
    "modern_flooring": 25.0,         # TUNABLE
}

BOUNDS = {  # safe plausibility ranges (applied pre-calibration)
    "poverty": (14.0, 46.0),
    "extreme_poverty": (2.0, 10.5),
    "transactional_account": (55.0, 96.0),
    "mobile_money": (50.0, 95.0),
    "formal_credit": (12.0, 40.0),
    "formal_savings": (35.0, 82.0),
    "formal_inclusion": (84.0, 99.0),
    "social_protection": (40.0, 84.0),
    "vup_public_works": (8.0, 45.0),
    "vup_direct_support": (3.0, 22.0),
    "climate_shock": (35.0, 90.0),
    "financial_health": (4.0, 18.0),
    "vulnerability": (20.0, 42.0),
    "informal_gap": (8.0, 26.0),
    "electricity_access": (35.0, 99.0),
    "improved_water": (70.0, 99.0),
    "modern_flooring": (8.0, 65.0),
}

# ============================================================================
# 2. Socio-economic archetypes (percentage-point deviations from benchmarks)
# ============================================================================

ARCHETYPES = {
    "kigali_core":       dict(poverty=-6.4, extreme_poverty=-1.9, transactional_account=+9.5, mobile_money=+10.0,
                              formal_credit=+10.0, formal_savings=+9.0, social_protection=+7.5, climate_shock=-13.0,
                              financial_health=+3.6, vulnerability=-5.0, informal_gap=-6.5,
                              formal_inclusion=+3.0, vup_public_works=-6.5, vup_direct_support=-2.5,
                              electricity_access=+18.0, improved_water=+7.0, modern_flooring=+12.0),
    "secondary_city":    dict(poverty=+0.8, extreme_poverty=+0.1, transactional_account=+4.5, mobile_money=+5.5,
                              formal_credit=+4.5, formal_savings=+6.0, social_protection=+3.0, climate_shock=-4.5,
                              financial_health=+1.6, vulnerability=-2.4, informal_gap=-2.0,
                              formal_inclusion=+1.5, vup_public_works=-1.5, vup_direct_support=-0.5,
                              electricity_access=+8.0, improved_water=+2.5, modern_flooring=+4.0),
    "commercial_rural":  dict(poverty=+2.4, extreme_poverty=+0.7, transactional_account=+0.5, mobile_money=+1.5,
                              formal_credit=+1.0, formal_savings=+2.0, social_protection=+1.0, climate_shock=+1.5,
                              financial_health=+0.2, vulnerability=-0.6, informal_gap=+0.5,
                              formal_inclusion=0.0, vup_public_works=0.0, vup_direct_support=0.0,
                              electricity_access=-1.0, improved_water=0.0, modern_flooring=0.0),
    "emerging_rural":    dict(poverty=+4.4, extreme_poverty=+1.4, transactional_account=-3.5, mobile_money=-3.0,
                              formal_credit=-2.5, formal_savings=-2.5, social_protection=-2.0, climate_shock=+4.0,
                              financial_health=-1.0, vulnerability=+1.6, informal_gap=+2.0,
                              formal_inclusion=-2.5, vup_public_works=+2.5, vup_direct_support=+1.5,
                              electricity_access=-6.0, improved_water=-2.5, modern_flooring=-4.0),
    "deep_rural":        dict(poverty=+7.0, extreme_poverty=+2.4, transactional_account=-7.0, mobile_money=-8.0,
                              formal_credit=-6.5, formal_savings=-7.0, social_protection=-5.5, climate_shock=+8.5,
                              financial_health=-2.2, vulnerability=+3.8, informal_gap=+3.5,
                              formal_inclusion=-4.5, vup_public_works=+5.0, vup_direct_support=+3.5,
                              electricity_access=-12.0, improved_water=-5.0, modern_flooring=-8.0),
}

# ============================================================================
# 3. The 30 administrative districts
#    (province, area type, NISR 2022 census population [millions], archetype)
# ============================================================================

DISTRICTS = [
    ("Nyarugenge", "Kigali City", "urban",     0.433, "kigali_core",       {"formal_credit": +4.0}),
    ("Gasabo",     "Kigali City", "urban",     0.879, "kigali_core",       {"formal_credit": +3.0, "financial_health": +1.4}),
    ("Kicukiro",   "Kigali City", "urban",     0.479, "kigali_core",       {"formal_savings": +3.0}),
    ("Nyagatare",  "Eastern Province", "mixed", 0.548, "secondary_city",   {"formal_savings": +1.0}),
    ("Rwamagana",  "Eastern Province", "rural", 0.449, "commercial_rural", {}),
    ("Ngoma",      "Eastern Province", "rural", 0.368, "commercial_rural", {}),
    ("Kayonza",    "Eastern Province", "rural", 0.445, "emerging_rural",   {}),
    ("Gatsibo",    "Eastern Province", "rural", 0.434, "emerging_rural",   {}),
    ("Bugesera",   "Eastern Province", "rural", 0.478, "emerging_rural",   {"climate_shock": +9.0, "mobile_money": -6.0}),
    ("Kirehe",     "Eastern Province", "rural", 0.424, "deep_rural",       {"climate_shock": +5.0, "poverty": +2.0}),
    ("Musanze",    "Northern Province", "mixed", 0.532, "secondary_city",  {"mobile_money": +2.0}),
    ("Rulindo",    "Northern Province", "rural", 0.404, "commercial_rural", {}),
    ("Gicumbi",    "Northern Province", "rural", 0.455, "commercial_rural", {"climate_shock": +2.5}),
    ("Burera",     "Northern Province", "rural", 0.396, "deep_rural",       {"poverty": +0.5}),
    ("Gakenke",    "Northern Province", "rural", 0.353, "deep_rural",       {"climate_shock": +5.0, "formal_savings": -3.0}),
    ("Huye",       "Southern Province", "mixed", 0.470, "secondary_city",  {"poverty": -1.0}),
    ("Muhanga",    "Southern Province", "mixed", 0.397, "secondary_city",  {"formal_credit": +1.5, "poverty": -0.7}),
    ("Kamonyi",    "Southern Province", "rural", 0.605, "commercial_rural", {}),
    ("Ruhango",    "Southern Province", "rural", 0.382, "commercial_rural", {}),
    ("Nyanza",     "Southern Province", "rural", 0.331, "commercial_rural", {}),
    ("Nyamagabe",  "Southern Province", "rural", 0.527, "deep_rural",      {"poverty": +1.0, "social_protection": +2.0}),
    ("Nyaruguru",  "Southern Province", "rural", 0.325, "deep_rural",      {"formal_credit": -2.5, "formal_savings": -3.0}),
    ("Gisagara",   "Southern Province", "rural", 0.381, "deep_rural",      {"formal_savings": -2.5, "mobile_money": -3.0}),
    ("Rubavu",     "Western Province", "mixed", 0.431, "secondary_city",   {"mobile_money": +2.0}),
    ("Rusizi",     "Western Province", "mixed", 0.397, "secondary_city",   {"poverty": +1.5}),
    ("Karongi",    "Western Province", "rural", 0.321, "deep_rural",       {"climate_shock": +4.0, "poverty": +1.5}),
    ("Nyamasheke", "Western Province", "rural", 0.426, "deep_rural",       {"climate_shock": +5.5, "poverty": +1.0}),
    ("Rutsiro",    "Western Province", "rural", 0.369, "deep_rural",       {"climate_shock": +6.0}),
    ("Ngororero",  "Western Province", "rural", 0.410, "deep_rural",       {"formal_credit": -2.0, "poverty": +0.5}),
    ("Nyabihu",    "Western Province", "rural", 0.326, "emerging_rural",   {}),
]

# ============================================================================
# 4. Indicator catalog (registry order = dashboard ordering)
# ============================================================================

INDICATOR_REGISTRY = [
    # (code, name, category, unit, description)
    ("financial_inclusion_rate", "Financial Inclusion Rate", "Financial Inclusion", "%",
     "Share of adults served by formal + informal mechanisms (FinScope 2024: 96%)"),
    ("formal_inclusion", "Formal Inclusion Rate", "Financial Inclusion", "%",
     "Share of adults formally served - bank, MFI, mobile wallet or SACCO (FinScope 2024: 92%)"),
    ("transactional_account", "Transactional Account Ownership", "Financial Inclusion", "%",
     "Adults holding a bank, mobile wallet or other transactional account (FinScope 2024: 77%)"),
    ("mobile_money", "Mobile Money Usage", "Financial Inclusion", "%",
     "Adults using mobile wallets (FinScope 2024: 77%)"),
    ("financial_exclusion_rate", "Financial Exclusion Rate", "Financial Inclusion", "%",
     "Adults excluded from all financial mechanisms (FinScope 2024: 4%)"),
    ("formal_credit", "Formal Credit Usage", "Financial Inclusion", "%",
     "Adults borrowing from formal institutions (FinScope 2024: 24%)"),
    ("formal_savings", "Formal Savings Uptake", "Financial Inclusion", "%",
     "Adults saving formally / semi-formally (FinScope 2024: 59%)"),
    ("poverty_headcount", "Poverty Headcount Rate", "Poverty Dynamics", "%",
     "Population below the national basic-needs poverty line (EICV7: 27.4%)"),
    ("extreme_poverty_rate", "Extreme Poverty Rate", "Poverty Dynamics", "%",
     "Population below the food-poverty line (EICV7: 4.5%)"),
    ("social_protection", "Social Protection Coverage", "Social Protection", "%",
     "Households reached by at least one social protection programme (EICV7: 61.3%)"),
    ("vup_public_works", "VUP Public Works Participation", "Social Protection", "%",
     "Household members engaged in VUP public works (EICV7 VUP; TUNABLE: 21%)"),
    ("vup_direct_support", "VUP Direct Support Reach", "Social Protection", "%",
     "Households receiving VUP direct support grants (EICV7 VUP; TUNABLE: 9.5%)"),
    ("climate_shock", "Climate Shock Exposure", "Climate Resilience", "%",
     "Adults hit by floods, droughts or storms in the last 12 months (FinScope 2024: 69%)"),
    ("financial_health", "Financially Healthy Share", "Financial Health", "%",
     "Adults that are financially healthy (FinScope 2024: 10%)"),
    ("financially_coping", "Financially Coping Share", "Financial Health", "%",
     "Adults that are financially coping (FinScope 2024: 57%)"),
    ("financially_vulnerable", "Financially Vulnerable Share", "Financial Health", "%",
     "Adults that are financially vulnerable (FinScope 2024: 31%)"),
    ("extremely_vulnerable", "Extremely Vulnerable Share", "Financial Health", "%",
     "Adults that are extremely vulnerable (FinScope 2024: 3%)"),
    ("electricity_access", "Electricity Access", "Living Conditions", "%",
     "Households with electricity (grid or solar) (EICV7: 72%)"),
    ("improved_water", "Improved Water Source Access", "Living Conditions", "%",
     "Households accessing improved water sources (EICV7: 90%)"),
    ("modern_flooring", "Modern Solid Flooring", "Living Conditions", "%",
     "Households with solid modern flooring (cement/carpet) (EICV7; TUNABLE: 25%)"),
]

SURVEY_YEAR = 2024

# 2025 Labour Force Survey extension: catalog-only entries (no baseline
# survey_metrics rows), so the LFS codes pass the /api/admin/microdata
# catalog lookup and appear on the dashboard as soon as a 2025 CSV lands.
LFS_INDICATORS = [
    ("employment_ratio", "Employment-to-Population Ratio", "Labour Force", "%",
     "Share of working-age adults that are employed (NISR LFS vintage)"),
    ("unemployment_rate", "Unemployment Rate", "Labour Force", "%",
     "Share of the labour force without work but available and searching (NISR LFS vintage)"),
    ("lfpr", "Labour Force Participation Rate", "Labour Force", "%",
     "Share of working-age adults in or actively seeking work (NISR LFS vintage)"),
    ("youth_unemployment", "Youth Unemployment Rate", "Labour Force", "%",
     "Share of the youth labour force (15-30) without work but available and searching (NISR RLFS 2025 vintage)"),
    ("labor_underutilization", "Labour Underutilization Rate", "Labour Force", "%",
     "Combined time-related underemployment + unemployed + potential labour force (NISR RLFS 2025 vintage)"),
]

XVL_RATIO = 3.0 / 31.0    # extreme : vulnerable national ratio (3% / 31%)
JITTER_AMPLITUDE = 1.2    # +-0.6 pp deterministic texture

HEALTH_TIER_SERIES_KEYS = (
    "financial_health",          # Financially Healthy Share
    "financially_coping",        # Financially Coping Share
    "financially_vulnerable",    # Financially Vulnerable Share
    "extremely_vulnerable",      # Extremely Vulnerable Share
)

# ============================================================================
# 5. Profile builder + population-weighted calibration
# ============================================================================


def stable_jitter(district, key):
    """Deterministic jitter in [-0.5, 0.5] per (district, indicator).

    Reproducible across runs and platforms (md5 of a stable token) keeps the
    generated dataset byte-stable for regressions and exports.
    """
    token = f"{district}|{key}".encode("utf-8")
    digest = hashlib.md5(token).digest()
    return (int.from_bytes(digest[:2], "big") / 65535.0) - 0.5


def weight_of(district_name):
    for d, _, _, pop, _, _ in DISTRICTS:
        if d == district_name:
            return pop
    raise KeyError(district_name)


def build_raw_profiles():
    """District -> {benchmark-key: plausible value} BEFORE calibration."""
    profiles = {}
    for district, province, area, pop, arch, overrides in DISTRICTS:
        if arch not in ARCHETYPES:
            raise ValueError(f"unknown archetype {arch!r} for {district}")
        raw = {}
        for key, target in TARGETS.items():
            dev = ARCHETYPES[arch].get(key, 0.0)
            extra = overrides.get(key, 0.0)
            jitter = stable_jitter(district, key) * JITTER_AMPLITUDE
            lo, hi = BOUNDS[key]
            raw[key] = min(hi, max(lo, target + dev + extra + jitter))
        profiles[district] = raw
    return profiles


def calibrate_series(values, weights, target, lo, hi, decimals=1, max_iters=8):
    """Scale a series so that its population-weighted mean hits `target`."""
    vals = [float(v) for v in values]
    total_w = sum(weights)
    for _ in range(max_iters):
        wmean = sum(v * w for v, w in zip(vals, weights)) / total_w
        factor = target / wmean
        if abs(factor - 1.0) < 5e-4:
            break
        vals = [min(hi, max(lo, v * factor)) for v in vals]
    return [round(v, decimals) for v in vals]


def weighted_mean(values):
    weights = [weight_of(d) for d, *_ in DISTRICTS]
    return sum(v * w for v, w in zip(values, weights)) / sum(weights)


def build_dataset():
    """Produces (region_rows, indicator_defs, metric_rows, series) fully calibrated."""
    profiles = build_raw_profiles()
    weights = [weight_of(d) for d, *_ in DISTRICTS]
    district_names = [d for d, *_ in DISTRICTS]

    calibrated = {}
    for key in TARGETS:
        series = [profiles[d][key] for d in district_names]
        lo, hi = BOUNDS[key]
        calibrated[key] = calibrate_series(series, weights, TARGETS[key], lo, hi)

    # ---- derived composite indicators -----------------------------------
    inclusion = [
        round(a + g, 1)
        for a, g in zip(calibrated["transactional_account"], calibrated["informal_gap"])
    ]
    exclusion = [round(max(1.0, 100.0 - inc), 1) for inc in inclusion]
    extreme_vulnerable = [round(v * XVL_RATIO, 1) for v in calibrated["vulnerability"]]

    # reconciliation: the four financial-health tiers must sum to exactly 100
    coping = [
        round(max(0.0, 100.0 - h - v - x), 1)
        for h, v, x in zip(
            calibrated["financial_health"], calibrated["vulnerability"], extreme_vulnerable
        )
    ]

    SERIES = {
        "financial_inclusion_rate": inclusion,
        "formal_inclusion": calibrated["formal_inclusion"],
        "transactional_account": calibrated["transactional_account"],
        "mobile_money": calibrated["mobile_money"],
        "financial_exclusion_rate": exclusion,
        "formal_credit": calibrated["formal_credit"],
        "formal_savings": calibrated["formal_savings"],
        "poverty_headcount": calibrated["poverty"],
        "extreme_poverty_rate": calibrated["extreme_poverty"],
        "social_protection": calibrated["social_protection"],
        "vup_public_works": calibrated["vup_public_works"],
        "vup_direct_support": calibrated["vup_direct_support"],
        "climate_shock": calibrated["climate_shock"],
        "financial_health": calibrated["financial_health"],
        "financially_coping": coping,
        "financially_vulnerable": calibrated["vulnerability"],
        "extremely_vulnerable": extreme_vulnerable,
        "electricity_access": calibrated["electricity_access"],
        "improved_water": calibrated["improved_water"],
        "modern_flooring": calibrated["modern_flooring"],
    }

    region_rows = [
        {"province": prov, "district": dist, "area_type": area, "population_weight": pop}
        for dist, prov, area, pop, _arch, _ov in DISTRICTS
    ]
    indicator_defs = [
        {"indicator_code": code, "indicator_name": name, "category": cat,
         "unit": unit, "description": desc}
        for code, name, cat, unit, desc in INDICATOR_REGISTRY
    ]

    metric_rows = []
    for idx, district in enumerate(district_names):
        for code, _name, _cat, _unit, _desc in INDICATOR_REGISTRY:
            metric_rows.append({
                "district": district,
                "indicator_code": code,
                "survey_year": SURVEY_YEAR,
                "value": SERIES[code][idx],
            })

    return region_rows, indicator_defs, metric_rows, SERIES


def validation_report(series):
    """Weighted means vs official targets - shown at the end of a seed run."""
    return [(code, weighted_mean(values)) for code, values in series.items()]


def ensure_indicator_catalog(engine) -> int:
    """Register missing catalog rows (the LFS extension) into any database state."""
    from sqlalchemy.orm import sessionmaker

    from models import Indicator

    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = factory()
    added = 0
    try:
        known = {code for (code,) in session.query(Indicator.indicator_code).all()}
        for code, name, category, unit, description in LFS_INDICATORS:
            if code not in known:
                session.add(Indicator(
                    indicator_code=code,
                    indicator_name=name,
                    category=category,
                    unit=unit,
                    description=description,
                ))
                added += 1
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
    return added


def seed(engine, drop_existing=False):
    from sqlalchemy.orm import sessionmaker

    from models import Base, Indicator, Region, SurveyMetric

    if drop_existing:
        Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

    regions, indicators, metrics, series = build_dataset()

    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = factory()
    try:
        region_map: dict[str, int] = {}
        indicator_map: dict[str, int] = {}

        for spec in regions:
            name = spec["district"]
            existing = session.query(Region).filter_by(district=name).one_or_none()
            if existing is None:
                row = Region(**spec)
                session.add(row)
                session.flush()
                region_map[name] = row.id
            else:
                existing.province = spec["province"]
                existing.area_type = spec["area_type"]
                existing.population_weight = spec["population_weight"]
                region_map[name] = existing.id

        for spec in indicators:
            code = spec["indicator_code"]
            existing = session.query(Indicator).filter_by(indicator_code=code).one_or_none()
            if existing is None:
                row = Indicator(**spec)
                session.add(row)
                session.flush()
                indicator_map[code] = row.id
            else:
                existing.indicator_name = spec["indicator_name"]
                existing.category = spec["category"]
                existing.unit = spec["unit"]
                existing.description = spec["description"]
                indicator_map[code] = existing.id

        for row in metrics:
            existing = (
                session.query(SurveyMetric)
                .filter_by(
                    region_id=region_map[row["district"]],
                    indicator_id=indicator_map[row["indicator_code"]],
                    survey_year=row["survey_year"],
                )
                .one_or_none()
            )
            if existing is None:
                session.add(SurveyMetric(
                    region_id=region_map[row["district"]],
                    indicator_id=indicator_map[row["indicator_code"]],
                    survey_year=row["survey_year"],
                    value=row["value"],
                ))
            else:
                existing.value = row["value"]

        session.commit()
        lfs_added = ensure_indicator_catalog(engine)
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    return len(regions), len(indicators) + lfs_added, len(metrics), series


def print_summary(series, regions, indicators, metrics):
    print("\n=== UpliftRwanda seed summary ===")
    print(f"regions: {regions} | indicators: {indicators} | survey_metrics rows: {metrics}")
    print("\nPopulation-weighted national means (calibrated):")
    print(f"  {'indicator':<34} {'seeded mean':>12}")
    for code, value in validation_report(series):
        print(f"  {code:<34} {value:>11.2f}%")
    tier_sums = [
        sum(series[code][i] for code in HEALTH_TIER_SERIES_KEYS)
        for i in range(len(DISTRICTS))
    ]
    tier_avg = sum(tier_sums) / len(tier_sums)
    status = "OK" if all(abs(s - 100.0) < 0.05 for s in tier_sums) else "MISMATCH"
    print(f"  financial-health tier sum (avg): {tier_avg:.1f}% [{status}] (must be exactly 100)")
    print()


def main():
    parser = argparse.ArgumentParser(description="Seed uplift_rwanda_db with FinScope 2024 / EICV7 data")
    parser.add_argument("--url", default=os.getenv("DATABASE_URL"),
                        help="SQLAlchemy URL; defaults to $DATABASE_URL (postgres)")
    parser.add_argument("--drop-existing", action="store_true",
                        help="drop & recreate all tables first")
    parser.add_argument("--dry-run", action="store_true",
                        help="compute & validate, but write nothing")
    args = parser.parse_args()

    regions, indicators, metrics, series = build_dataset()

    if args.dry_run or not args.url:
        if not args.url and not args.dry_run:
            print("No --url given; running dry-run against defaults.", file=sys.stderr)
        print_summary(series, len(regions), len(indicators), len(metrics))
        return 0

    from sqlalchemy import create_engine

    connect_args = {} if args.url.startswith("sqlite") else {"connect_timeout": 5}
    engine = create_engine(args.url, pool_pre_ping=True, connect_args=connect_args)
    n_r, n_i, n_m, s = seed(engine, drop_existing=args.drop_existing)
    print_summary(s, n_r, n_i, n_m)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
