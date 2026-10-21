#!/usr/bin/env python3
"""Offline verification of /api/v1/simulate against a seeded SQLite DB."""

import os
import sys

TEST_DB = "/tmp/opencode/uplift-sim-test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import seed_data  # noqa: E402
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
seed = create_engine(os.environ["DATABASE_URL"])
seed_data.seed(seed, drop_existing=True)
client = TestClient(main.app)

# --- regression integrity ----------------------------------------------------
# A zero-delta scenario must return the baseline values unchanged.
r = client.post("/api/v1/simulate", json={"driver_deltas": {}, "horizon_years": 2})
b = r.json()["national"]
check("200 zero-delta", r.status_code == 200)
check("inclusion unchanged", b["financially_vulnerable"]["path"][-1] == b["financially_vulnerable"]["baseline"],
      str(b))
check("extreme poverty unchanged", b["extreme_poverty_rate"]["path"][0] == b["extreme_poverty_rate"]["baseline"])

# --- headline scenario: user's own example ------------------------------------
r = client.post("/api/v1/simulate", json={"driver_deltas": {"mobile_money": 5, "formal_credit": 3}, "horizon_years": 2})
d = r.json()
check("200 headline", r.status_code == 200)
if r.status_code == 200:
    b = d["national"]
    xp = b["extreme_poverty_rate"]
    fh = b["financial_health"]
    check("headline: extreme poverty DOWN", xp["path"][-1] < xp["baseline"], str(xp))
    check("headline: financial health UP", fh["path"][-1] > fh["baseline"], str(fh))
    check("horizon ramp applied", xp["path"][0] != xp["path"][-1], str(xp))
    check("bands present", "extreme_poverty_rate" in d["uncertainty_bands"])
    check("coefficients exposed", {"mobile_money", "formal_credit"} <= set(d["model"]["coefficients"]["extreme_poverty_rate"]))
    check("training_rows = 30", d["model"]["training_rows"] == 30)

# --- district targeting + validation paths ------------------------------------
r = client.post("/api/v1/simulate", json={"driver_deltas": {"social_protection": 4}, "horizon_years": 3, "district": "karongi"})
check("200 district (case-insensitive)", r.status_code == 200 and "district" in r.json())
r = client.post("/api/v1/simulate", json={"driver_deltas": {"mobile_money": 2}, "district": "Nowhere-land"})
check("unknown district -> 404", r.status_code == 404 and r.json()["code"] == "district_not_found")
r = client.post("/api/v1/simulate", json={"driver_deltas": {"poverty_headcount": 9}, "horizon_years": 9})
check("invalid horizon rejected", r.status_code in (409, 422), str(r.status_code))
r = client.get("/api/v1/simulate/coefficients")
check("coefficients endpoint", r.status_code == 200 and r.json()["model"]["districts"] == 30)

print(f"\n{len(failures)} FAILURES" if failures else "\nALL SIMULATION TESTS PASSED")
sys.exit(1 if failures else 0)
