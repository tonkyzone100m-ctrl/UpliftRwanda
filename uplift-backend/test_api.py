#!/usr/bin/env python3
"""End-to-end API + seeding verification for UpliftRwanda.

Runs the full stack against a temporary SQLite database:
    python3 test_api.py
"""

import os
import sys

TEST_DB = "/tmp/opencode/uplift-api-test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"
os.environ["UPLIFT_ADMIN_USERNAME"] = "nisr_test_admin"
os.environ["UPLIFT_ADMIN_PASSWORD"] = "test-minister-pass"
os.environ["UPLIFT_JWT_SECRET"] = "test-signing-secret-for-pytest"
os.environ["UPLIFT_TOKEN_TTL_MINUTES"] = "60"

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
    check("GET /api/indicators -> 25 incl. LFS extension, benchmarks intact", r.status_code == 200
          and catalog["count"] == 25
          and any(i["indicator_code"] == "lfpr" for i in catalog["data"])
          and any(i["indicator_code"] == "youth_unemployment" for i in catalog["data"])
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
    # Evict pooled connections bound to the pre-swap sqlite inode: the suite
    # deleted and recreated the file, so pooled handles serve orphaned data
    # (reads "work", writes raise readonly until disposed).
    good_engine.dispose()
    r0 = client.get("/api/metrics")
    seed_data.seed(engine, drop_existing=False)
    r1 = client.get("/api/metrics")
    check("re-seed keeps 600 rows", r0.json()["count"] == r1.json()["count"] == 600)


def auth_flow():
    import auth  # noqa: E402 (configured via env exported before main import)

    client = TestClient(main.app)
    print("\n--- public core (no token required) ---")
    r = client.get("/api/metrics")
    check("GET /api/metrics stays public", r.status_code == 200)
    r = client.get("/api/insights/national")
    check("GET /api/insights/national stays public", r.status_code == 200)
    r = client.post("/api/v1/simulate", json={"driver_deltas": {}, "horizon_years": 1})
    check("POST simulation stays public (pure compute, no writes)", r.status_code == 200, r.text[:120])

    print("\n--- write route protection ---")
    r = client.post("/api/admin/seed")
    body = r.json()
    check("POST /api/admin/seed without token -> 401", r.status_code == 401, r.text[:120])
    check("401 payload is clean JSON with code", body["detail"]["code"] == "not_authenticated")
    check("401 advertises WWW-Authenticate: Bearer", r.headers.get("www-authenticate") == "Bearer", str(r.headers.get("www-authenticate")))
    auth.reset_rate_limiter()

    print("\n--- login flow ---")
    r = client.post("/api/auth/login", json={"username": "nisr_test_admin", "password": "wrong-password"})
    body = r.json()
    check("wrong password -> 401 invalid_credentials",
          r.status_code == 401 and body["detail"]["code"] == "invalid_credentials")
    r = client.post("/api/auth/login", json={"username": "nisr_test_admin", "password": "test-minister-pass"})
    body = r.json()
    check("correct credentials -> 200", r.status_code == 200, r.text[:120])
    check("token contract", body.get("token_type") == "bearer" and len(body.get("access_token", "")) > 40
          and isinstance(body.get("expires_in"), int) and body["expires_in"] > 0)
    token = body["access_token"]
    auth_header = {"Authorization": f"Bearer {token}"}

    r = client.get("/api/auth/me", headers=auth_header)
    body = r.json()
    check("GET /api/auth/me -> session echoes admin", r.status_code == 200
          and body["username"] == "nisr_test_admin" and body["role"] == "admin", r.text[:140])

    r = client.get("/api/auth/me")
    check("GET /api/auth/me without token -> 401", r.status_code == 401)
    r = client.get("/api/auth/me", headers={"Authorization": "Bearer tampered.token.here"})
    check("GET /api/auth/me with tampered token -> 401", r.status_code == 401
          and r.json()["detail"]["code"] in ("invalid_token", "token_expired"))

    print("\n--- protected seed with real token ---")
    r = client.post("/api/admin/seed", headers=auth_header, json=None)
    body = r.json()
    check("POST /api/admin/seed with token -> success", r.status_code == 200 and body["status"] == "success", r.text[:160])
    check("seed reports all layers", body["seeded"]["metric_rows"] == 600 and body["cfsva"]["seeded"])
    r = client.get("/api/metrics")
    check("re-seeded dashboard intact (600 rows)", r.json().get("count") == 600)

    print("\n--- brute-force rate limiting ---")
    auth.reset_rate_limiter()
    for _ in range(5):
        client.post("/api/auth/login", json={"username": "nisr_test_admin", "password": "nope"})
    r = client.post("/api/auth/login", json={"username": "nisr_test_admin", "password": "nope"})
    body = r.json()
    check("6th failed attempt in window -> 429", r.status_code == 429 and body["detail"]["code"] == "too_many_attempts")
    r = client.get("/api/metrics")
    check("rate limit never touches public reads", r.status_code == 200)
    auth.reset_rate_limiter()


def admin_mutations():
    client = TestClient(main.app)

    import auth  # noqa: E402

    login = client.post(
        "/api/auth/login",
        json={"username": "nisr_test_admin", "password": "test-minister-pass"},
    )
    auth_header = {"Authorization": f"Bearer {login.json()['access_token']}"}

    print("\n--- national baseline targets ---")
    r = client.get("/api/targets")
    body = r.json()
    check("GET /api/targets -> public, defaults active", r.status_code == 200
          and body["targets"]["poverty_limit"] == 30.0
          and all(not e["is_overridden"] for e in body["entries"]), r.text[:140])

    r = client.post("/api/admin/targets", json={"targets": {"poverty_limit": 10.0}})
    check("POST /api/admin/targets without token -> 401", r.status_code == 401)

    r = client.post("/api/admin/targets", json={"targets": {"nonsense_metric": 5}}, headers=auth_header)
    body = r.json()
    check("unknown target key -> 422 with explicit errors", r.status_code == 422
          and body["code"] == "invalid_targets" and body["errors"], r.text[:160])

    r = client.post("/api/admin/targets", json={"targets": {"poverty_limit": 10.0}, "reason": "stress test"}, headers=auth_header)
    body = r.json()
    check("target override -> success", r.status_code == 200 and body["applied"] == {"poverty_limit": 10.0}, r.text[:160])
    r = client.get("/api/districts/Karongi/insights")
    body = r.json()
    check("policy engine consumes ministerial cutoff (10%)",
          body["thresholds"]["poverty_limit"] == 10.0
          and body["using_baseline_targets"] is False
          and body["active_target_overrides"] == {"poverty_limit": 10.0}, body.get("thresholds"))
    check("poverty still flagged under new cutoff", any(i["id"] == "poverty-critical" for i in body["insights"]))

    r = client.post("/api/admin/targets", json={"targets": {"climate_attention": 95, "climate_critical": 65}}, headers=auth_header)
    check("incoherent band -> 422", r.status_code == 422 and "must stay below" in r.text, r.text[:160])

    r = client.post("/api/admin/targets", json={"reset_to_official": True}, headers=auth_header)
    body = r.json()
    check("reset to official -> defaults live again", r.status_code == 200
          and body["action"] == "reset_to_official" and body["targets"]["poverty_limit"] == 30.0)
    r = client.get("/api/districts/Karongi/insights")
    check("insights return to baseline thresholds", r.json()["thresholds"]["poverty_limit"] == 30.0)

    print("\n--- microdata upload (ministerial write) ---")
    r = client.post("/api/admin/microdata", json={"rows": [
        {"district": "Karongi", "indicator_code": "poverty_headcount", "survey_year": 2024, "value": 22.0},
    ]})
    check("upload without token -> 401", r.status_code == 401)

    before = client.get("/api/metrics").json()["count"]
    r = client.post("/api/admin/microdata", headers=auth_header, json={"rows": [
        {"district": "Karongi", "indicator_code": "poverty_headcount", "survey_year": 2024, "value": 23.5},
        {"district": "Karongi", "indicator_code": "poverty_headcount", "survey_year": 2025, "value": 21.0},
        {"district": "Atlantis", "indicator_code": "poverty_headcount", "survey_year": 2024, "value": 10.0},
        {"district": "Karongi", "indicator_code": "financial_inclusion_rate", "survey_year": 2024, "value": 130.0},
        {"district": "Karongi", "indicator_code": "not_a_real_code", "survey_year": 2024, "value": 1.0},
    ]})
    body = r.json()
    check("upload contract: 1 inserted / 1 updated / 3 rejected",
          r.status_code == 200 and body["status"] == "partial"
          and body["inserted"] == 1 and body["updated"] == 1 and body["rejected"] == 3, r.text[:240])
    check("rows_processed mirrors accepted tuples", body["rows_processed"] == 2, r.text[:120])
    after = client.get("/api/metrics").json()["count"]
    check("dashboard grew by exactly 1 row", after == before + 1, f"{before} -> {after}")
    karongi_poverty = next(row for row in client.get("/api/metrics").json()["data"]
                          if row["district"] == "Karongi" and row["indicator_code"] == "poverty_headcount"
                          and row["survey_year"] == 2024)
    check("upsert overwrote the 2024 value", karongi_poverty["value"] == 23.5, karongi_poverty)
    r = client.post("/api/admin/microdata", headers=auth_header, json={"rows": [
        {"district": "Karongi", "indicator_code": "poverty_headcount", "survey_year": 2024, "value": 20.0},
        {"district": "Karongi", "indicator_code": "poverty_headcount", "survey_year": 2024, "value": 24.0},
    ]})
    body = r.json()
    check("duplicate tuple in one payload collapses (last wins)", r.status_code == 200
          and body["rows_processed"] == 1 and body["updated"] == 1, r.text[:160])
    karongi_poverty = next(row for row in client.get("/api/metrics").json()["data"]
                          if row["district"] == "Karongi" and row["indicator_code"] == "poverty_headcount"
                          and row["survey_year"] == 2024)
    check("duplicate last-wins value stored (24.0)", karongi_poverty["value"] == 24.0, karongi_poverty)
    r = client.get("/api/metrics")
    body = r.json()
    check("metrics counts reflect all vintages (600x2024 + 1x2025)",
          body["count"] == 601 and body["years"] == [2024, 2025]
          and body["count_by_year"] == {"2024": 600, "2025": 1}, r.text[:200])
    r = client.post("/api/admin/microdata", headers=auth_header, json={"rows": [
        {"district": "Karongi", "indicator_code": "EMPLOYMENT_RATIO", "survey_year": 2025, "value": 44.9},
        {"district": "Karongi", "indicator_code": "UNEMPLOYMENT_RATE", "survey_year": 2025, "value": 13.8},
        {"district": "Karongi", "indicator_code": "LFPR", "survey_year": 2025, "value": 52.1},
        {"district": "Gicumbi", "indicator_code": "unemployment_rate", "survey_year": 2025, "value": 12.9},
    ]})
    body = r.json()
    check("2025 LFS codes ingest case-insensitively (4 inserted, 0 rejected)",
          r.status_code == 200 and body["status"] == "success"
          and body["rows_processed"] == 4 and body["inserted"] == 4 and body["rejected"] == 0, r.text[:200])
    r = client.get("/api/metrics")
    body = r.json()
    check("metrics counts grow with LFS vintage (605 total, 5x2025)",
          body["count"] == 605 and body["count_by_year"] == {"2024": 600, "2025": 5}, r.text[:200])
    r = client.get("/api/districts/Karongi/insights")
    body = r.json()
    check("Karongi insights carry LFS indicators at 2025 vintage",
          body["vintage_years"]["lfpr"] == 2025 and body["metrics"]["lfpr"] == 52.1
          and body["metrics"].get("unemployment_rate") == 13.8, r.text[:180])
    r = client.post("/api/admin/microdata", headers=auth_header, json={"rows": []})
    check("empty upload -> 422", r.status_code == 422)
    r = client.post("/api/admin/microdata", headers=auth_header, json={"rows": [
        {"district": "X" * 65, "indicator_code": "poverty_headcount", "survey_year": 2025, "value": 10.0},
    ]})
    check("oversized field -> whole-request 422 (client pre-validates per-row)", r.status_code == 422, r.text[:140])

    auth.reset_rate_limiter()


if __name__ == "__main__":
    main_flow()
    auth_flow()
    admin_mutations()
    print()
    if failures:
        print(f"{len(failures)} FAILURES ❌ -> {failures}")
        sys.exit(1)
    print("ALL API TESTS PASSED")
