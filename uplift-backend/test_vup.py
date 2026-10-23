#!/usr/bin/env python3
"""VUP beneficiary & operations module integration tests (Module B).

Runs the full VUP flow on SQLite:
    python3 test_vup.py
"""

import os
import sys

TEST_DB = "/tmp/opencode/uplift-vup-test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import seed_data  # noqa: E402
import seed_vup  # noqa: E402
import main  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402

failures = []


def check(label, cond, extra=""):
    print(("  ok   " if cond else "  FAIL ") + label, extra if not cond else "")
    if not cond:
        failures.append(label)


if os.path.exists(TEST_DB):
    os.remove(TEST_DB)
engine = create_engine(os.environ["DATABASE_URL"])
seed_data.seed(engine, drop_existing=True)

client = TestClient(main.app)

# --- 1. seed + table creation (additive only) ---------------------------------
seed_vup.seed_vup(engine)
check("vup layer seeds cleanly", True)

# --- 2. component totals are exact --------------------------------------------
rows = client.get("/api/vup/districts").json()["data"]
check("/api/vup/districts -> 30 rows", client.get("/api/vup/districts").status_code == 200 and len(rows) == 30)
for component, expected in seed_vup.NATIONAL_COMPONENTS.items():
    total = sum(row[component] for row in rows)
    check(f"{component} district split sums exactly to {expected:,}", total == expected, f"{total:,}")
check("component caseloads are non-negative ints",
      all(row[c] >= 0 for row in rows for c in (k for k in seed_vup.NATIONAL_COMPONENTS)))

weights = {d["district"]: d["population_weight"] for d in client.get("/api/districts").json()["data"]}


def wmean(rows, key):
    picked = [(row, row[key]) for row in rows if weights.get(row["district"])]
    acc = sum(v * weights[row["district"]] for row, v in picked)
    tot = sum(weights[row["district"]] for row, v in picked)
    return acc / tot


pov = wmean(rows, "poverty_rate_among_beneficiaries")
check("poverty among beneficiaries ~41% (official anchor)", abs(pov - 41.0) < 0.4, f"{pov:.2f}")
ext = wmean(rows, "extreme_among_beneficiaries")
check("extreme share calibrated (~12.5)", abs(ext - 12.5) < 0.4, f"{ext:.2f}")
check("extreme strictly inside poverty", all(
    row["extreme_among_beneficiaries"] < row["poverty_rate_among_beneficiaries"] for row in rows))
tim = wmean(rows, "payment_timeliness_pct")
check("payment timeliness ~91%", abs(tim - 91.0) < 1.0, f"{tim:.2f}")
check("disbursement channels sum to 100 per district", all(
    abs(row["sacco_disbursement_pct"] + row["momo_disbursement_pct"] + row["cash_disbursement_pct"] - 100.0) < 0.11
    for row in rows))

# --- 3. vulnerability geography ------------------------------------------------
poor_district = "Nyaruguru"
rich_district = "Gasabo"
pov_row = next(row for row in rows if row["district"] == poor_district)
rich_row = next(row for row in rows if row["district"] == rich_district)
check("deep-rural beneficiary poverty above Kigali core",
      pov_row["poverty_rate_among_beneficiaries"] > rich_row["poverty_rate_among_beneficiaries"] + 6)
check("caseload per 1000 computed", all(row.get("caseload_per_1000") and row["caseload_per_1000"] > 2 for row in rows))

# --- 4. endpoints ---------------------------------------------------------------
r = client.get("/api/vup/indicators")
body = r.json()
check("/api/vup/indicators 11 columns", r.status_code == 200 and body["count"] == 11, str(body.get("count")))
check("national totals + anchors echoed", body["national_totals"]["beneficiaries_ds"] == seed_vup.NATIONAL_COMPONENTS["beneficiaries_ds"])
basis = {i["column"]: i["basis"] for i in body["data"]}
check("poverty row labelled OFFICIAL", basis["poverty_rate_among_beneficiaries"].startswith("OFFICIAL"))
check("timeliness labelled MODELLED", basis["payment_timeliness_pct"].startswith("MODELLED"))

r = client.get("/api/vup/summary")
body = r.json()
check("/api/vup/summary totals + poverty + channels", r.status_code == 200
      and body["national"]["component_totals"]["beneficiaries_fs"] == seed_vup.NATIONAL_COMPONENTS["beneficiaries_fs"]
      and body["national"]["disbursement_mix"]["umurenge_sacco"] is not None)
check("summary leagues non-empty", body["leagues"]["poverty_among_beneficiaries_worst"]
      and body["leagues"]["payment_timeliness_worst"])

r = client.get("/api/vup/districts/Karongi")
body = r.json()
check("district profile by name", r.status_code == 200 and body["district"] == "Karongi"
      and "national_means" in body and body["national_means"]["poverty_rate_among_beneficiaries"])
r = client.get("/api/vup/districts/5")
check("district profile by id", r.status_code == 200)
r = client.get("/api/vup/districts/mars")
check("unknown -> 404 vup_district_not_found", r.status_code == 404 and r.json()["code"] == "vup_district_not_found")

r = client.get("/api/vup/metrics")
body = r.json()
first = body["data"][0]
check("/api/vup/metrics standard row contract", all(
    k in first for k in ("province", "district", "indicator_code", "category", "unit", "survey_year", "value")))
check("vup metrics category labelled", first["category"] == "VUP Social Protection")
check("vup metrics 330 rows (11 x 30)", body["count"] == 330, str(body.get("count")))

print()
if failures:
    print(f"FAILED: {len(failures)} checks: {failures}")
    raise SystemExit(1)
print("All VUP module checks passed.")
