#!/usr/bin/env python3
"""LFS 2025 labour module integration tests.

Runs the full labour-market flow on SQLite:
    python3 test_labour.py
"""

import os
import sys

TEST_DB = "/tmp/opencode/uplift-labour-test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import seed_data  # noqa: E402
import seed_lfs  # noqa: E402
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

# --- 1. BASELINE: /api/metrics count stays 600 before the LFS vintage ---------
r = client.get("/api/metrics")
check("baseline /api/metrics count == 600", r.status_code == 200 and r.json()["count"] == 600)

# --- 2. LFS layer seeds (tables + survey_metrics 2025 vintage across 27 more) --
seed_lfs.seed_lfs(engine)

r = client.get("/api/metrics")
check("/api/metrics gains the 2025 vintage (600 -> 750)", r.status_code == 200 and r.json()["count"] == 750,
      str(r.json().get("count")))
vintage_2025 = [row for row in r.json()["data"] if row["survey_year"] == 2025]
check("2025 vintage covers 30 districts x 5 LFS codes (150 rows)", len(vintage_2025) == 150,
      str(len(vintage_2025)))
check("2025 vintage all category 'Labour Force'", vintage_2025 and all(
    row["category"] == "Labour Force" for row in vintage_2025))

# --- 3. LABOUR endpoints ------------------------------------------------------
r = client.get("/api/labour/indicators")
body = r.json()
check("/api/labour/indicators catalog >= 14 entries", r.status_code == 200 and body["count"] >= 14, str(body.get("count")))
check("official national hierarchy present", body["national_hierarchy"]["unemployment_rate"] == 12.4
      and body["national_hierarchy"]["youth_neet_rate"] == 24.5
      and body["national_hierarchy"]["lfpr_gender_gap_pp"] == 14.3)
check("dimension metadata lists 3 dimensions", len(body["dimensions"]) == 3)

r = client.get("/api/labour/districts")
body = r.json()
check("/api/labour/districts -> 30 wide rows", r.status_code == 200 and body["count"] == 30)
sample = body["data"][0]
check("wide row carries gender split + TVET + disability",
      all(k in sample for k in ("unemployment_rate_male", "unemployment_rate_female",
                                "tvet_unemployment_rate", "general_education_unemployment_rate",
                                "disability_lfpr", "youth_neet_rate", "inactivity_rate")))
# weighted national anchors
weights = {d["district"]: d["population_weight"] for d in client.get("/api/districts").json()["data"]}


def wmean(rows, key):
    tot = acc = 0.0
    for row in rows:
        w = weights.get(row["district"])
        if row.get(key) is None or not w:
            continue
        acc += row[key] * w
        tot += w
    return acc / tot


rows = body["data"]
check("national unemployment calibrated to 12.4 +-0.4", abs(wmean(rows, "unemployment_rate") - 12.4) < 0.4,
      f"{wmean(rows, 'unemployment_rate'):.2f}")
check("national youth NEET calibrated to 24.5 +-0.4", abs(wmean(rows, "youth_neet_rate") - 24.5) < 0.4,
      f"{wmean(rows, 'youth_neet_rate'):.2f}")
check("LFPR gender gap ~14.3 pp", abs(wmean(rows, "lfpr_gender_gap_pp") - 14.3) < 0.35,
      f"{wmean(rows, 'lfpr_gender_gap_pp'):.2f}")
check("male LFPR > female LFPR everywhere", all(r["lfpr_male"] >= r["lfpr_female"] for r in rows))
check("employment_ratio identity holds", all(
    abs(r["employment_ratio"] - (r["lfpr"] * (100 - r["unemployment_rate"]) / 100)) < 0.15 for r in rows))
check("inactivity = 100 - lfpr", all(abs(r["inactivity_rate"] - (100 - r["lfpr"])) < 0.11 for r in rows))

# --- 4. vulnerability geography: Southern worst cases on inactivity/NEET ------
r = client.get("/api/labour/summary")
body = r.json()
check("/api/labour/summary leagues present", r.status_code == 200 and all(
    k in body["leagues"] for k in ("unemployment_worst", "inactivity_worst", "youth_neet_worst")))
inact_top = [d["district"] for d in body["leagues"]["inactivity_worst"][:6]]
scope = {"Nyaruguru", "Gisagara", "Ruhango", "Nyamagabe"}
check("Nyaruguru/Gisagara/Ruhango family appears top inactivity", bool(set(inact_top) & scope), inact_top)
neet_top = [d["district"] for d in body["leagues"]["youth_neet_worst"][:6]]
check("NEET worst also surfaces the same family", bool(set(neet_top) & scope), neet_top)
check("summary echoes official anchors", body["official"]["unemployment_rate"] == 12.4)

r = client.get("/api/labour/districts/Gasabo")
body = r.json()
check("district profile by name + ranks", r.status_code == 200 and body["district"] == "Gasabo"
      and body["ranks"]["unemployment_rate"])
kigali_rows = client.get("/api/labour/districts").json()["data"]
gasabo = next(r0 for r0 in kigali_rows if r0["district"] == "Gasabo")
gisagara = next(r0 for r0 in kigali_rows if r0["district"] == "Gisagara")
check("urban unemployment above deep-rural unemployment (structure)",
      gasabo["unemployment_rate"] > gisagara["unemployment_rate"] + 2,
      f"{gasabo['unemployment_rate']} vs {gisagara['unemployment_rate']}")
check("deep-rural informality above urban", gisagara["informal_employment_rate"] > gasabo["informal_employment_rate"])
r = client.get("/api/labour/districts/5")
check("district profile by numeric id -> 200", r.status_code == 200)
r = client.get("/api/labour/districts/atlantis")
check("unknown -> 404 district_not_found", r.status_code == 404 and r.json()["code"] == "district_not_found")

# --- 5. disaggregation dimensions --------------------------------------------
for dim, expected_segments in (("gender", {"male", "female"}),
                               ("education", {"primary", "secondary_general", "tvet", "tertiary"}),
                               ("disability", {"with_disability", "without_disability"})):
    r = client.get(f"/api/labour/disaggregation?dimension={dim}")
    body = r.json()
    if dim == "education":
        n_rows = 30 * len(expected_segments) * 3
        check(f"education rows -> {n_rows}", r.status_code == 200 and body["count"] == n_rows, str(body.get("count")))
    else:
        check(f"{dim} rows non-empty", r.status_code == 200 and body["count"] > 0, str(body.get("count")))
    segs = {row["segment"] for row in body.get("data", [])}
    check(f"{dim} segments match", expected_segments <= segs, str(segs))

r = client.get("/api/labour/disaggregation?dimension=gender&district=Nyaruguru&indicator=unemployment")
body = r.json()
check("gender unemployment filter works (2 segments)", body["count"] == 2
      and {row["segment"] for row in body["data"]} == {"male", "female"}, str(body.get("count")))
female_val = next(row["value"] for row in body["data"] if row["segment"] == "female")
male_val = next(row["value"] for row in body["data"] if row["segment"] == "male")
check("female unemployment premium positive", female_val > male_val, f"{female_val} vs {male_val}")

# TVET segment vs general segment — every district TVET < general unemployment
r = client.get("/api/labour/disaggregation?dimension=education")
tv_map = {}
for row in r.json()["data"]:
    if row["indicator"] == "unemployment":
        tv_map.setdefault(row["district"], {})[row["segment"]] = row["value"]
tvet_adv = all(v["tvet"] < v["secondary_general"] for v in tv_map.values())
check("TVET unemployment < general everywhere", tvet_adv,
      str([d for d, v in tv_map.items() if v["tvet"] >= v["secondary_general"]])[:80])

# disability participation below baseline
r = client.get("/api/labour/disaggregation?dimension=disability&indicator=lfpr")
dis_map = {}
for row in r.json()["data"]:
    dis_map.setdefault(row["district"], {})[row["segment"]] = row["value"]
check("disabled LFPR below baseline everywhere", all(
    v["with_disability"] < v["without_disability"] for v in dis_map.values()))

# --- 6. metrics feed + existing endpoints untouched ---------------------------
r = client.get("/api/labour/metrics")
body = r.json()
first = body["data"][0]
check("/api/labour/metrics uses the standard row contract", all(
    k in first for k in ("province", "district", "indicator_code", "indicator_name",
                         "category", "unit", "survey_year", "value")))
check("labour metrics labelled", first["category"] == "Labour Market (LFS 2025)")

r = client.get("/api/districts/Gasabo/insights")
check("policy engine still healthy after LFS vintage", r.status_code == 200 and r.json()["insights"])
r = client.get("/api/insights/national")
check("national insights healthy", r.status_code == 200 and r.json()["insights"])
r = client.post("/api/v1/simulate", json={"driver_deltas": {"mobile_money": 2}, "horizon_years": 2})
check("simulation still healthy", r.status_code == 200)

print()
if failures:
    print(f"FAILED: {len(failures)} checks: {failures}")
    raise SystemExit(1)
print("All LFS labour module checks passed.")
