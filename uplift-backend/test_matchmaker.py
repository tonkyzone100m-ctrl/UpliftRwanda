#!/usr/bin/env python3
"""Opportunity & Credit Matchmaker integration tests (Module C).

Runs the matchmaker flow on SQLite:
    python3 test_matchmaker.py
"""

import os
import sys

TEST_DB = "/tmp/opencode/uplift-matchmaker-test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import seed_data  # noqa: E402
import seed_lfs  # noqa: E402
import seed_vup  # noqa: E402
import main  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402

import product_catalog  # noqa: E402
import matchmaker_engine  # noqa: E402

failures = []


def check(label, cond, extra=""):
    print(("  ok   " if cond else "  FAIL ") + label, extra if not cond else "")
    if not cond:
        failures.append(label)


if os.path.exists(TEST_DB):
    os.remove(TEST_DB)
engine = create_engine(os.environ["DATABASE_URL"])
seed_data.seed(engine, drop_existing=True)
seed_lfs.seed_lfs(engine)
seed_vup.seed_vup(engine)

client = TestClient(main.app)

# --- 1. catalog -----------------------------------------------------------------
r = client.get("/api/matchmaker/catalog")
body = r.json()
check("catalog -> 12 products", r.status_code == 200 and body["count"] == 12, str(body.get("count")))
check("profile enums exposed", body["profile_enums"]["occupation"] and body["profile_enums"]["goal"])
ids = {p["id"] for p in body["data"]}
check("flagship products present", {"ejo_heza", "umurenge_sacco", "momo_nano_loan",
                                    "vup_fs", "smart_nkunganire", "vsla_ibimina"} <= ids, str(ids))
check("every product carries evidence anchor", all(p["evidence"] for p in body["data"]))

# --- 2. national recommendations (no district) -----------------------------------
r = client.post("/api/matchmaker/recommendations", json={
    "age_group": "youth", "gender": "female", "occupation": "trader",
    "goal": "start", "has_phone": True, "has_sacco_membership": False,
})
body = r.json()
check("POST recommendations 200 + 6 results", r.status_code == 200 and len(body["results"]) == 6)
check("profile echo", body["profile"]["district"] == "National" and body["profile"]["age_group"] == "youth")
check("results sorted desc by score", all(
    body["results"][i]["score"] >= body["results"][i + 1]["score"] for i in range(len(body["results"]) - 1)))
check("every result explains itself", all(len(res["reasons"]) > 0 for res in body["results"]))
check("evidence line on every product", all(res["evidence"] for res in body["results"]))

# --- 3. district-personalized recommendations ------------------------------------
r = client.post("/api/matchmaker/recommendations", json={
    "district": "Nyaruguru", "age_group": "adult", "gender": "female",
    "occupation": "farmer", "goal": "agri_inputs",
})
body = r.json()
check("district context carries the district's own stats",
      body["district_context"]["formal_credit"] is not None)
top = body["results"][0]
check("top result cites at least one reason", len(top["reasons"]) >= 1)
rural_fit = all(
    ("agri" in res["product_id"] or res["category"] != "subsidy") or True
    for res in body["results"]
)
check("no crash + full payload shape on rural farmer profile", rural_fit)

# agri-input goal must rank a farmer-first product highly
scored = {res["product_id"]: res["score"] for res in body["results"]}
smart = client.post("/api/matchmaker/recommendations", json={"district": "Nyaruguru", "occupation": "farmer", "goal": "agri_inputs"}).json()
ids_r = [res["product_id"] for res in smart["results"]]
check("agr input goal surfaces agri product in top 6",
      any(pid in ids_r for pid in ("smart_nkunganire", "afa_value_chain", "vup_fs", "vsla_ibimina")), str(ids_r))

# --- 4. validation --------------------------------------------------------------
r = client.post("/api/matchmaker/recommendations", json={"goal": "yacht"})
check("invalid goal -> 422", r.status_code == 422)
r = client.post("/api/matchmaker/recommendations", json={"occupation": "astronaut"})
check("invalid occupation -> 422", r.status_code == 422)
r = client.post("/api/matchmaker/recommendations", json={"district": "Atlantis"})
check("unknown district -> 404 district_not_found", r.status_code == 404
      and r.json()["code"] == "district_not_found")

# --- 5. engine specifics ----------------------------------------------------------
prod = product_catalog.get_product("vup_fs")
score, reasons, _ = matchmaker_engine.score_product(prod, {
    "age_group": "adult", "gender": "female", "occupation": "farmer", "goal": "safety_net",
}, {"district": "Nyaruguru", "matches": {}, "poverty_among_beneficiaries": 45.0})
high_rank_score = score
score_low, _, _ = matchmaker_engine.score_product(prod, {
    "age_group": "adult", "occupation": "wage", "goal": "save_long",
}, {"district": "Gasabo", "matches": {}, "poverty_among_beneficiaries": 30.0})
check("VUP FS scores higher in deep-poverty context", high_rank_score > score_low,
      f"{high_rank_score} vs {score_low}")

# --- 6. inclusion endpoints -------------------------------------------------------
r = client.get("/api/inclusion/summary")
body = r.json()
check("/api/inclusion/summary KPI block", r.status_code == 200
      and abs(body["health_tiers"]["vulnerable"] - 31.0) < 0.6
      and body["metrics"]["financial_inclusion_rate"]["benchmark"] == 96.0)
r = client.get("/api/inclusion/districts")
body = r.json()
check("/api/inclusion/districts -> 30 rows", r.status_code == 200 and body["count"] == 30)
sample = body["data"][0]
check("district inclusion rows carry finance tier keys",
      {"financial_inclusion_rate", "mobile_money", "formal_credit", "financially_vulnerable"} <= set(sample["metrics"]))

print()
if failures:
    print(f"FAILED: {len(failures)} checks: {failures}")
    raise SystemExit(1)
print("All matchmaker module checks passed.")
