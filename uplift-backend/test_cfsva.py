#!/usr/bin/env python3
"""CFSVA 2024 integration tests — the 'do not break anything' safety net.

Runs the FULL dual-dataset flow on SQLite:
    python3 test_cfsva.py
"""

import os
import sys

TEST_DB = "/tmp/opencode/uplift-cfsva-api.db"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import seed_data  # noqa: E402
import seed_cfsva  # noqa: E402
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

# --- 1. BASELINE: dashboard API BEFORE CFSVA layer is touched ------------------
r = client.get("/api/metrics")
check("baseline /api/metrics count == 600", r.status_code == 200 and r.json()["count"] == 600)
r = client.get("/api/districts")
check("baseline /api/districts count == 30", r.status_code == 200 and r.json()["count"] == 30)

# --- 2. CFSVA layer seeds (create_all; no destructive DDL) ---------------------
seed_cfsva.seed_cfsva(engine)

# --- 3. EXISTING ENDPOINTS UNCHANGED AFTER SEEDING ----------------------------
r = client.get("/api/metrics")
check("/api/metrics STILL 600 (CFSVA rows NOT mixed in)", r.status_code == 200 and r.json()["count"] == 600
      and not any(row["category"] == "Food Security" for row in r.json()["data"]))
r = client.get("/api/districts")
check("/api/districts STILL 30", r.status_code == 200 and r.json()["count"] == 30)
r = client.get("/api/insights/national")
check("/api/insights/national still healthy", r.status_code == 200 and r.json()["insights"])
r = client.post("/api/v1/simulate", json={"driver_deltas": {"mobile_money": 2}, "horizon_years": 2})
check("/api/v1/simulate still healthy", r.status_code == 200)

# --- 4. NEW CFSVA endpoints ----------------------------------------------------
r = client.get("/api/cfsva/indicators")
check("/api/cfsva/indicators 9 entries + anchors + status split", r.status_code == 200 and r.json()["count"] == 9
      and all(i["national_anchor"] is not None for i in r.json()["data"]))
r = client.get("/api/cfsva/metrics")
body = r.json()
check("/api/cfsva/metrics -> 270 rows (30x9)", r.status_code == 200 and body["count"] == 270)
check("rows carry category 'Food Security'", body["data"] and all(row["category"] == "Food Security" for row in body["data"]))
check("row contract matches /api/metrics", all(
    set(row) >= {"province", "district", "area_type", "indicator_code", "indicator_name", "category", "unit", "survey_year", "value"}
    for row in body["data"]
))
r = client.get("/api/cfsva/districts")
check("/api/cfsva/districts 30 rows", r.status_code == 200 and r.json()["count"] == 30)
r = client.get("/api/cfsva/districts/karongi")
check("case-insensitive district row + anchors", r.status_code == 200 and r.json()["national_anchors"])
r = client.get("/api/cfsva/districts/deep-space-9")
check("unknown -> 404 cfsva_district_not_found", r.status_code == 404 and r.json()["code"] == "cfsva_district_not_found")

# --- 5. spatial sanity ----------------------------------------------------------
karongi = [d for d in client.get("/api/cfsva/districts").json()["data"] if d["district"] == "Karongi"][0]
nyarugenge = [d for d in client.get("/api/cfsva/districts").json()["data"] if d["district"] == "Nyarugenge"][0]
check("deep-rural stunting > kigali", karongi["stunting_pct"] > nyarugenge["stunting_pct"] + 3,
      f"{karongi['stunting_pct']} vs {nyarugenge['stunting_pct']}")
check("kigali FCS > deep-rural FCS", nyarugenge["food_consumption_score"] > karongi["food_consumption_score"])

# --- 5b. OFFICIAL provincial FIES split (W23 / S16 / K4 / E14; N residual) -------
weights = {d["district"]: d["population_weight"] for d in client.get("/api/districts").json()["data"]}
prov_dists = {}
for d in client.get("/api/districts").json()["data"]:
    prov_dists.setdefault(d["province"], []).append(d["district"])
cfsva_rows = client.get("/api/cfsva/districts").json()["data"]


def prov_mean(prov, field):
    dists = prov_dists[prov]
    vals = [next(c[field] for c in cfsva_rows if c["district"] == x) for x in dists]
    ws = [weights[x] for x in dists]
    return sum(v * w for v, w in zip(vals, ws)) / sum(ws)


national_fies = sum(
    prov_mean(p, "fies_moderate_severe_pct") * sum(weights[d] for d in dists)
    for p, dists in prov_dists.items()
) / sum(weights.values())
check("provincial FIES: Western 23%", abs(prov_mean("Western Province", "fies_moderate_severe_pct") - 23.0) < 0.35,
      f"{prov_mean('Western Province', 'fies_moderate_severe_pct'):.2f}")
check("provincial FIES: Southern 16%", abs(prov_mean("Southern Province", "fies_moderate_severe_pct") - 16.0) < 0.35,
      f"{prov_mean('Southern Province', 'fies_moderate_severe_pct'):.2f}")
check("provincial FIES: Kigali 4%", abs(prov_mean("Kigali City", "fies_moderate_severe_pct") - 4.0) < 0.35,
      f"{prov_mean('Kigali City', 'fies_moderate_severe_pct'):.2f}")
check("provincial FIES: Eastern 14%", abs(prov_mean("Eastern Province", "fies_moderate_severe_pct") - 14.0) < 0.35,
      f"{prov_mean('Eastern Province', 'fies_moderate_severe_pct'):.2f}")
check("national FIES lands ~17% (83% secure)", abs(national_fies - 17.0) < 0.35, f"{national_fies:.2f}")
check("severe FIES ~1% nationally", abs(
    sum(next(c["fies_severe_pct"] for c in cfsva_rows if c["district"] == d) * weights[d] for d in weights) / sum(weights.values()) - 1.0
) < 0.25)
r = client.get("/api/cfsva/indicators")
status = r.json().get("national_status_split")
check("status split 83/16/1 exposed", status and
      status["food_secure_pct"] == 83.0 and
      status["moderately_insecure_pct"] == 16.0 and
      status["severely_insecure_pct"] == 1.0)
stunting_national = sum(
    next(c["stunting_pct"] for c in cfsva_rows if c["district"] == d) * weights[d] for d in weights
) / sum(weights.values())
check("stunting baseline 30%", abs(stunting_national - 30.0) < 0.35, f"{stunting_national:.2f}")

# --- 6. IDEMPOTENT re-seed (updates, never duplicates) -------------------------
seed_cfsva.seed_cfsva(engine)
r = client.get("/api/cfsva/metrics")
check("re-seed keeps 270 CFSVA rows", r.status_code == 200 and r.json()["count"] == 270)

print(f"\n{len(failures)} FAILURES" if failures else "\nALL CFSVA INTEGRATION TESTS PASSED")
sys.exit(1 if failures else 0)
