#!/usr/bin/env python3
"""RDHS 2025 integration tests — the 'do not break anything' safety net.

Runs the FULL three-dataset flow on SQLite:
    python3 test_rdhs.py
"""

import json
import os
import sys

TEST_DB = "/tmp/opencode/uplift-rdhs-api.db"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import seed_data  # noqa: E402
import seed_rdhs  # noqa: E402
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

# Ground truth: the committed panel artifact (the exact source of the seed).
PANEL = json.loads(
    (seed_rdhs.DEFAULT_PANEL).read_text(encoding="utf-8")
)["districts"]
PANEL_BY_DISTRICT = {d["district"]: d for d in PANEL}

# --- 1. BASELINE: dashboard API BEFORE RDHS layer is touched ------------------
r = client.get("/api/metrics")
check("baseline /api/metrics count == 600", r.status_code == 200 and r.json()["count"] == 600)
r = client.get("/api/districts")
check("baseline /api/districts count == 30", r.status_code == 200 and r.json()["count"] == 30)

# --- 2. RDHS layer seeds (create_all; no destructive DDL) ---------------------
seed_rdhs.seed_rdhs(engine)
seed_cfsva.seed_cfsva(engine)  # both companion layers must coexist cleanly

# --- 3. EXISTING ENDPOINTS UNCHANGED AFTER SEEDING ----------------------------
r = client.get("/api/metrics")
check("/api/metrics STILL 600 (RDHS rows NOT mixed in)", r.status_code == 200 and r.json()["count"] == 600
      and not any(row["category"].startswith("Living Standards") for row in r.json()["data"]))
r = client.get("/api/districts")
check("/api/districts STILL 30", r.status_code == 200 and r.json()["count"] == 30)
r = client.get("/api/insights/national")
check("/api/insights/national still healthy", r.status_code == 200 and r.json()["insights"])
r = client.post("/api/v1/simulate", json={"driver_deltas": {"mobile_money": 2}, "horizon_years": 2})
check("/api/v1/simulate still healthy", r.status_code == 200)
r = client.get("/api/cfsva/metrics")
check("/api/cfsva/metrics STILL 270 after adding RDHS layer", r.status_code == 200 and r.json()["count"] == 270)

# --- 4. NEW RDHS endpoints ----------------------------------------------------
r = client.get("/api/rdhs/indicators")
body = r.json()
check("/api/rdhs/indicators catalog 17 entries + national means", r.status_code == 200
      and body["count"] == 17
      and all(i["national_mean"] is not None for i in body["data"]))
check("survey echoed as RDHS 2025", body.get("survey") == "RDHS 2025")
check("method notes exposed", isinstance(body.get("method"), dict) and bool(body["method"]))

r = client.get("/api/rdhs/metrics")
body = r.json()
check("/api/rdhs/metrics -> 510 rows (30x17)", r.status_code == 200 and body["count"] == 510)
check("rows carry category 'Living Standards (RDHS 2025)'", body["data"] and all(
    row["category"] == "Living Standards (RDHS 2025)" for row in body["data"]))
check("row contract matches /api/metrics", all(
    set(row) >= {"province", "district", "area_type", "indicator_code", "indicator_name", "category", "unit", "survey_year", "value"}
    for row in body["data"]
))
check("no fabricated zeros: None only where panel is None", all(
    (row["value"] is None) == (PANEL_BY_DISTRICT[row["district"]].get(row["indicator_code"]) is None)
    for row in body["data"]
))

r = client.get("/api/rdhs/districts")
body = r.json()
check("/api/rdhs/districts 30 rows", r.status_code == 200 and body["count"] == 30)
check("counts block echoes microdata scale", body["counts"]["districts"] == 30
      and body["counts"]["households"] == 14427)

# --- 5. seeded values ROUND-TRIP against the panel artifact -------------------
def api_row(name):
    return next(d for d in client.get("/api/rdhs/districts").json()["data"] if d["district"] == name)

roundtrip_ok = True
for name in ("Nyarugenge", "Gasabo", "Karongi", "Rusizi", "Gatsibo", "Bugesera"):
    api_d = api_row(name)
    panel_d = PANEL_BY_DISTRICT[name]
    for key in ("bank_account_pct", "mobile_fintech_pct", "electricity_pct",
                "insurance_pct", "wealth_p40_pct", "imr_per_1000", "stunting_pct"):
        api_v = api_d.get(key)
        panel_v = panel_d.get(key)
        if panel_v is None:
            roundtrip_ok = roundtrip_ok and api_v is None
        elif api_v is None or abs(api_v - panel_v) > 0.001:
            roundtrip_ok = False
check("API values == panel values (6 districts x 7 keys)", roundtrip_ok)

ny_karongi = api_row("Karongi")
ny_nyar = api_row("Nyarugenge")
check("kigali electricity > rural electricity (real-data sanity)",
      ny_nyar["electricity_pct"] > ny_karongi["electricity_pct"] + 5,
      f"{ny_nyar['electricity_pct']} vs {ny_karongi['electricity_pct']}")

r = client.get("/api/rdhs/districts/karongi")
check("case-insensitive district row + method notes", r.status_code == 200 and r.json()["method"])
r = client.get("/api/rdhs/districts/13")
check("numeric id lookup works", r.status_code == 200 and r.json()["district"])
r = client.get("/api/rdhs/districts/deep-space-9")
check("unknown -> 404 rdhs_district_not_found", r.status_code == 404 and r.json()["code"] == "rdhs_district_not_found")

# --- 6. IDEMPOTENT re-seed (updates, never duplicates) -------------------------
seed_rdhs.seed_rdhs(engine)
r = client.get("/api/rdhs/metrics")
check("re-seed keeps 510 RDHS rows", r.status_code == 200 and r.json()["count"] == 510)

print(f"\n{len(failures)} FAILURES" if failures else "\nALL RDHS INTEGRATION TESTS PASSED")
sys.exit(1 if failures else 0)
