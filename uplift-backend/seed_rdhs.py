#!/usr/bin/env python3
"""RDHS 2025 seeder — non-destructive companion to seed_data.py / seed_cfsva.py.

Fills `district_rdhs_metrics` ONLY. Existing tables (regions/indicators/
survey_metrics/policy/CFSVA tables) are untouched. Requires `regions` to exist
(seed_data.py first), because rows link via the SAME region ids.

Source of truth is the lightweight district panel produced by preprocess_rdhs.py:

    db/rdhs/rdhs_2025_district_panel.json   (committed; ~23 KB)

so no 41 MB .dta files are needed at seeding time — judges can reproduce the
pipeline from raw microdata with preprocess_rdhs.py, then re-run this seeder.

Usage:
    python3 seed_rdhs.py --url $DATABASE_URL --dry-run
    python3 seed_rdhs.py --url $DATABASE_URL --drop-rdhs-first
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from sqlalchemy import create_engine

HERE = Path(__file__).resolve().parent
DEFAULT_PANEL = HERE.parent / "db" / "rdhs" / "rdhs_2025_district_panel.json"

SURVEY_YEAR = 2025
SURVEY_NAME = "RDHS 2025"

# Metric columns persisted per district (exact panel keys -> table columns).
METRIC_COLUMNS = [
    "households",
    "births",
    "children_measured",
    "electricity_pct",
    "improved_water_pct",
    "improved_sanitation_pct",
    "bank_account_pct",
    "mobile_fintech_pct",
    "mobile_phone_pct",
    "insurance_pct",
    "urban_pct",
    "wealth_q1",
    "wealth_q2",
    "wealth_q3",
    "wealth_q4",
    "wealth_q5",
    "wealth_p20_pct",
    "wealth_p40_pct",
    "wealth_p60p_pct",
    "imr_per_1000",
    "u5mr_per_1000",
    "stunting_pct",
    "underweight_pct",
    "wasting_pct",
]


def load_panel(path: Path | None = None) -> dict:
    panel_path = path or DEFAULT_PANEL
    if not panel_path.exists():
        alt = Path("/home/it-eng/Downloads/Microdata/Microdata") / panel_path.name
        if alt.exists():
            panel_path = alt
        else:
            raise FileNotFoundError(
                f"RDHS panel not found at {panel_path}. Generate it with: "
                "python3 preprocess_rdhs.py (needs RWHR91FL.dta + RWBR91FL.dta)"
            )
    payload = json.loads(panel_path.read_text(encoding="utf-8"))
    rows = payload.get("districts")
    if not isinstance(rows, list) or len(rows) != 30:
        raise ValueError(
            f"{panel_path} does not contain 30 district rows — re-run preprocess_rdhs.py"
        )
    return payload


def seed_rdhs(engine, drop_rdhs_first: bool = False, panel_path: Path | None = None):
    """Create/populate district_rdhs_metrics; returns (payload, region_ids)."""
    from models import DistrictRdhsMetrics, Region
    from sqlalchemy.orm import sessionmaker

    payload = load_panel(panel_path)

    if drop_rdhs_first:
        DistrictRdhsMetrics.__table__.drop(engine, checkfirst=True)
    DistrictRdhsMetrics.__table__.create(engine, checkfirst=True)

    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = factory()
    region_ids: dict[str, int] = {}
    try:
        regions = session.query(Region).all()
        region_map = {r.district.lower(): r.id for r in regions}
        missing = [d["district"] for d in payload["districts"] if d["district"].lower() not in region_map]
        if missing:
            raise RuntimeError(
                "regions table lacks districts: run seed_data.py first — missing "
                + ", ".join(missing)
            )

        for row in payload["districts"]:
            region_id = region_map[row["district"].lower()]
            region_ids[row["district"]] = region_id
            family = {col: row.get(col) for col in METRIC_COLUMNS}
            for col in ("households", "births", "children_measured"):
                family[col] = int(family[col] or 0)
            for col, val in list(family.items()):
                if col not in ("households", "births", "children_measured") and val is not None:
                    family[col] = float(val)

            existing = (
                session.query(DistrictRdhsMetrics)
                .filter_by(region_id=region_id, survey_year=SURVEY_YEAR)
                .one_or_none()
            )
            if existing is None:
                session.add(DistrictRdhsMetrics(region_id=region_id, survey_year=SURVEY_YEAR, **family))
            else:
                for field, val in family.items():
                    setattr(existing, field, val)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
    return payload, region_ids


def national_check(engine):
    from sqlalchemy import text

    query = text("""
        SELECT COUNT(*) AS rows,
               SUM(t.households) AS households,
               SUM(t.births) AS births,
               SUM(t.bank_account_pct * r.population_weight) / SUM(r.population_weight) AS bank,
               SUM(t.mobile_fintech_pct * r.population_weight) / SUM(r.population_weight) AS fintech,
               SUM(t.insurance_pct * r.population_weight) / SUM(r.population_weight) AS insurance,
               SUM(t.electricity_pct * r.population_weight) / SUM(r.population_weight) AS electricity,
               SUM(t.imr_per_1000 * r.population_weight) / SUM(r.population_weight) AS imr,
               SUM(t.stunting_pct * r.population_weight) / SUM(r.population_weight) AS stunting
        FROM district_rdhs_metrics t JOIN regions r ON t.region_id = r.id
        WHERE t.survey_year = :yr
    """)
    return engine.connect().execute(query, {"yr": SURVEY_YEAR}).fetchone()


def print_summary(payload, checkrow):
    print("\n=== RDHS 2025 seed summary ===")
    counts = payload.get("counts", {})
    print(f"  source     : {payload.get('sources')}")
    print(f"  districts  : {counts.get('districts')}")
    print(f"  households : {counts.get('households'):,}")
    print(f"  births     : {counts.get('births'):,}")
    if checkrow is not None:
        (rows, households, births, bank, fintech, insurance, electricity, imr, stunting) = checkrow
        print(
            f"  DB check   : rows={rows}, households={households:,}, births={births:,}"
            if rows is not None else "  DB check   : empty"
        )
        if bank is not None:
            print(
                f"  national   : bank {float(bank):.1f}% · fintech {float(fintech):.1f}% · "
                f"insurance {float(insurance):.1f}% · electricity {float(electricity):.1f}% · "
                f"IMR {float(imr):.1f}/1000 · stunting {float(stunting):.1f}% "
                "(population-weighted)"
            )
    print()


def main():
    parser = argparse.ArgumentParser(
        description="Seed the RDHS 2025 layer (district_rdhs_metrics table)"
    )
    parser.add_argument("--url", default=os.getenv("DATABASE_URL"))
    parser.add_argument("--panel", type=Path, default=None, help="Override panel JSON path")
    parser.add_argument("--drop-rdhs-first", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    try:
        payload = load_panel(args.panel)
    except (FileNotFoundError, ValueError) as exc:
        print(f"[seed_rdhs] {exc}", file=sys.stderr)
        return 1

    if args.dry_run or not args.url:
        print(
            f"[seed_rdhs] panel OK: {payload['counts']['districts']} districts, "
            f"{payload['counts']['households']:,} households, {payload['counts']['births']:,} births"
            f" — showing dry-run only."
        )
        print("[seed_rdhs] method:", json.dumps(payload.get("method", {}), indent=1))
        return 0

    engine = create_engine(
        args.url,
        pool_pre_ping=True,
        connect_args=({} if args.url.startswith("sqlite") else {"connect_timeout": 5}),
    )
    _, region_ids = seed_rdhs(engine, drop_rdhs_first=args.drop_rdhs_first, panel_path=args.panel)
    print_summary(payload, national_check(engine))
    print(f"[seed_rdhs] {len(region_ids)} district rows written to district_rdhs_metrics"
          + (" (table verified)" if table_exists(engine, "district_rdhs_metrics") else ""))
    return 0


def table_exists(engine, name: str) -> bool:
    from sqlalchemy import inspect

    return inspect(engine).has_table(name)


if __name__ == "__main__":
    raise SystemExit(main())
