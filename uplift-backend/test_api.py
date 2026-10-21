#!/usr/bin/env python3
"""End-to-end API + seeding verification for UpliftRwanda.

Runs the full stack against a temporary SQLite database:
    python3 test_api.py
"""

import os
import sys

TEST_DB = "/tmp/opencode/uplift-api-test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import seed_data  # noqa: E402
import main  # noqa: E402  (imports after env var is set)
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402

failures = []


def check(label, condition, extra=""):
    if condition:
        print(f"  ok   {label}")
    else:
        failures.append(label)
        print(f"  FAIL {label} {extra}")


def main_flow():
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)

    engine = create_engine(os.environ["DATABASE_URL"])
    n_regions, n_indicators, n_metrics, _series = seed_data.seed(engine, drop_existing=True)
    print(f"seeded: {n_regions} regions / {n_indicators} indicators / {n_metrics} metric rows")
    client = TestClient(main.app)

    print("\n--- core endpoints ---")
    r = client.get("/")
    check("GET / -> 200", r.status_code == 200, r.text[:120])

    r = client.get("/api/health")
    check("GET /api/health -> 200 connected", r.status_code == 200 and r.json()["status"] == "ok", r.text[:160])

    r = client.get("/api/metrics")
    body = r.json()
    check("GET /api/metrics -> 200", r.status_code == 200)
    check("metrics count == 600 (20 indicators x 30 districts)", body.get("count") == 600, str(body.get("count")))
    check("metrics contract keys", all(
        set(row) >= {"province", "district", "area_type", "indicator_code",
                     "indicator_name", "category", "unit", "survey_year", "value"}
        for row in body.get("data", [])
    ))
    check("metrics values in [0,100]", all(0 <= row["value"] <= 100 for row in body["data"]))
    check("metrics year == 2024", all(row["survey_year"] == 2024 for row in body["data"]))

    r = client.get("/api/indicators")
    catalog = r.json()
    check("GET /api/indicators -> 20 with benchmarks", r.status_code == 200 and catalog["count"] == 20
          and next(i for i in catalog["data"] if i["indicator_code"] == "financial_inclusion_rate")["official_benchmark"] == 96.0)

    r = client.get("/api/districts")
    districts = r.json()["data"]
    check("GET /api/districts -> 30", r.status_code == 200 and len(districts) == 30)
    karongi_id = next(d["id"] for d in districts if d["district"] == "Karongi")
    nyarugenge_id = next(d["id"] for d in districts if d["district"] == "Nyarugenge")

    print("\n--- policy insights (Karongi = deep-rural stress case) ---")
    r = client.get("/api/districts/Karongi/insights")
    body = r.json()
    check("GET insights by name -> 200", r.status_code == 200)
    ids = [i["id"] for i in body["insights"]]
    check("mobile-money flagged (< 75%)", "mobile-money" in ids, ids)
    mm = next(i for i in body["insights"] if i["id"] == "mobile-money")
    check("mobile-money has pillar + data backing", mm["pillar"].startswith("NST2") and mm["data"])
    check("poverty flagged (> 30%)", "poverty-critical" in ids)
    check("vulnerability flagged (> 30%)", "vulnerability-share" in ids)
    check("climate resilience present", "climate-resilience" in ids)
    severities = [i["severity"] for i in body["insights"]]
    rank = {"critical": 0, "attention": 1, "strength": 2, "info": 3}
    check("insights sorted by severity", all(
        rank[severities[i]] >= rank[severities[i - 1]] for i in range(1, len(severities))
    ), severities)
    check("thresholds echoed", body["thresholds"]["mobile_money_floor"] == 75.0
          and body["thresholds"]["vulnerability_share_flag"] == 30.0)
    check("benchmark echoes FinScope 96", body["benchmarks"]["financial_inclusion_rate"] == 96.0)

    print("\n--- policy insights (Nyarugenge = urban strength case) ---")
    r = client.get(f"/api/districts/{nyarugenge_id}/insights")
    body = r.json()
    check("GET insights by numeric id -> 200", r.status_code == 200)
    ids = [i["id"] for i in body["insights"]]
    check("no critical insights for Nyarugenge", not any(
        i["severity"] == "critical" for i in body["insights"]), ids)
    check("inclusion strength fires (>= 96%)", "inclusion-strength" in ids, ids)

    print("\n--- national view ---")
    r = client.get("/api/insights/national")
    body = r.json()
    ids = [i["id"] for i in body["insights"]]
    check("GET /api/insights/national -> 200 with insights", r.status_code == 200 and body["insights"])
    check("national vulnerability share flagged (> 30%)", "vulnerability-share" in ids, ids)
    check("national mobile money NOT flagged (76.99 >= 75)", "mobile-money" not in ids, ids)
    mm_mean = body["metrics"]["mobile_money"]
    check("population-weighted national mobile-money ~ 77", abs(mm_mean - 77.0) < 0.5, mm_mean)

    print("\n--- failure paths (clean JSON, never raw 500s) ---")
    r = client.get("/api/districts/Unknownville/insights")
    check("unknown district -> 404 + hint", r.status_code == 404 and "hint" in str(r.json()), r.json())

    good_engine, good_sessionmaker = main.engine, main.SessionLocal
    broker = create_engine("sqlite:////nonexistent-dir/api-test-broken.db", connect_args={})
    main.engine = broker
    main.SessionLocal = __import__("sqlalchemy.orm", fromlist=["sessionmaker"]).sessionmaker(broker, autoflush=False)
    r = client.get("/api/metrics")
    body = r.json()
    check("broken DB -> 503 (not 500)", r.status_code == 503, r.status_code)
    check("broken DB payload clean", body.get("code") == "database_unavailable" and "hint" in body, body)
    r = client.get("/api/health")
    check("health on broken DB -> 503 degraded", r.status_code == 503 and r.json()["status"] == "degraded")

    print("\n--- seed idempotency (second run updates, never duplicates) ---")
    main.engine, main.SessionLocal = good_engine, good_sessionmaker
    r0 = client.get("/api/metrics")
    seed_data.seed(engine, drop_existing=False)
    r1 = client.get("/api/metrics")
    check("re-seed keeps 600 rows", r0.json()["count"] == r1.json()["count"] == 600)


if __name__ == "__main__":
    main_flow()
    print()
    if failures:
        print(f"{len(failures)} FAILURES ❌ -> {failures}")
        sys.exit(1)
    print("ALL API TESTS PASSED ✅")
