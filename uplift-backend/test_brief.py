#!/usr/bin/env python3
"""Executive Policy Brief generator integration tests.

Runs the brief flow (PDF + CSV) on SQLite:
    python3 test_brief.py
"""

import os
import sys

TEST_DB = "/tmp/opencode/uplift-brief-test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import seed_data  # noqa: E402
import seed_lfs  # noqa: E402
import seed_vup  # noqa: E402
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
seed_cfsva.seed_cfsva(engine)
seed_lfs.seed_lfs(engine)
seed_vup.seed_vup(engine)

client = TestClient(main.app)

# --- 1. report assembly ----------------------------------------------------------
import brief_report  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

session = sessionmaker(bind=engine)()
report = brief_report.build_report(session, "Nyaruguru")[0]
session.close()
check("report builds for Nyaruguru", report is not None and report["meta"]["district"] == "Nyaruguru")
section_ids = {s["id"] for s in report["sections"]}
check("core sections present", {"headline", "labour", "vup"} <= section_ids, str(section_ids))
labour_rows = next(s["rows"] for s in report["sections"] if s["id"] == "labour")
check("labour section carries unemployment + TVET rows", any(
    "Unemployment" in r["label"] for r in labour_rows) and any(
    "TVET" in r["label"] for r in labour_rows))
vup_rows = next(s["rows"] for s in report["sections"] if s["id"] == "vup")
check("VUP section lists 5 components", sum(
    1 for r in vup_rows if r["label"].startswith("Beneficiaries — ")) == 5)
check("recommendations generated", len(report["recommendations"]) >= 1)
check("verdicts present", len(report["verdicts"]) >= 1)

# --- 2. national report ----------------------------------------------------------
session = sessionmaker(bind=engine)()
national = brief_report.build_report(session, "national")[0]
session.close()
check("national report builds", national is not None and national["meta"]["scope"] == "national")
national_labour = next((s["rows"] for s in national["sections"] if s["id"] == "labour"), [])
check("national labour rows present", len(national_labour) >= 5, str(len(national_labour)))

# --- 3. CSV endpoint -------------------------------------------------------------
r = client.get("/api/brief/Nyaruguru.csv")
check("CSV download content-type + disposition", r.status_code == 200
      and r.headers["content-type"].startswith("text/csv")
      and "upliftrwanda-brief-nyaruguru.csv" in r.headers.get("content-disposition", ""))
lines = [l for l in r.text.strip().splitlines() if l]
check("CSV header + data rows", lines[0].startswith("scope,district,province,section") and len(lines) > 15,
      str(len(lines)))
check("CSV includes recommendation rows", any("recommendations" in l for l in lines))

# --- 4. PDF endpoints ------------------------------------------------------------
r = client.get("/api/brief/Nyaruguru.pdf")
check("PDF endpoint 200 + media type", r.status_code == 200
      and r.headers["content-type"] == "application/pdf")
check("PDF magic bytes (%PDF)", r.content[:4] == b"%PDF", r.content[:8])
check("PDF multi-page payload (>5KB)", len(r.content) > 5_000, str(len(r.content)))

r = client.get("/api/brief/national")
check("national default = PDF", r.status_code == 200 and r.content[:4] == b"%PDF")
r = client.get("/api/brief/national.pdf")
check("national.pdf alias works", r.status_code == 200 and r.content[:4] == b"%PDF")

# --- 5. edge cases ----------------------------------------------------------------
r = client.get("/api/brief/atlantis.pdf")
check("unknown district -> 404", r.status_code == 404 and r.json()["code"] == "district_not_found")
r = client.get("/api/brief/Karongi?format=csv")
check("?format=csv honours", r.status_code == 200 and r.headers["content-type"].startswith("text/csv"))
r = client.get("/api/brief/Nyaruguru.docx")
check("unsupported -> 400 unsupported_format", r.status_code == 400
      and r.json()["code"] == "unsupported_format")
r = client.get("/api/brief/")
check("empty ref -> 404/400 not 500", r.status_code in (400, 404))

# --- 6. existing surfaces untouched ----------------------------------------------
r = client.get("/api/metrics")
check("metrics still healthy", r.status_code == 200)
r = client.get("/api/insights/national")
check("insights still healthy", r.status_code == 200 and r.json()["insights"])

print()
if failures:
    print(f"FAILED: {len(failures)} checks: {failures}")
    raise SystemExit(1)
print("All brief module checks passed.")
