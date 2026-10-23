"""Executive Policy Brief endpoints (Module D).

Endpoints
---------
GET /api/brief/{ref}.pdf / .csv / ?format=   -> executive brief for any district
                                                (ref "national" = all 30 districts)

PDF is rendered with reportlab (brief_pdf.py); CSV is a tidy dataset of every
row (section, indicator, value, reference) so analysts can rejoin in Excel.
Read-only, public: no personal data, only survey aggregates.
"""

from __future__ import annotations

import csv
import io
import re
from typing import Optional

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse, Response

from insights_api import get_db
from brief_pdf import render as render_pdf
from brief_report import build_report

router = APIRouter(prefix="/api/brief", tags=["brief"])

SLUG_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_\-]{0,60}$")


def _slug(ref: str) -> str:
    name = re.sub(r"[^A-Za-z0-9]+", "-", ref.strip() or "national").strip("-").lower()
    return name or "national"


def _csv_from_report(report) -> str:
    """Tidy single-file CSV: one row per indicator with section + reference."""
    buf = io.StringIO(newline="")
    writer = csv.writer(buf, quoting=csv.QUOTE_MINIMAL)
    writer.writerow([
        "scope", "district", "province", "section", "section_source", "indicator",
        "value", "unit", "national_reference", "note", "generated_at",
    ])
    meta = report["meta"]
    for section in report["sections"]:
        for row in section["rows"]:
            writer.writerow([
                meta["scope"], meta["district"], meta["province"],
                section["title"], section.get("subtitle") or "",
                row["label"], row["value"], row["unit"],
                row.get("benchmark"), row.get("note"), meta["generated_at"],
            ])
    for rec in report["recommendations"]:
        writer.writerow([meta["scope"], meta["district"], meta["province"],
                         "recommendations", "", rec, "", "text", "", "", meta["generated_at"]])
    return buf.getvalue()


def _serve(ref: str, fmt: str, db):
    """Shared assembly + rendering path for both file extensions."""
    if len(ref) > 61 or ("/" in ref) or ("<" in ref) or ("%" in ref) or (
            ref != "national" and not ref.strip().isdigit() and not SLUG_RE.match(ref)):
        return JSONResponse(status_code=400, content={
            "status": "error", "code": "invalid_brief_ref",
            "detail": "Provide a district name, numeric id, or 'national'.",
            "hint": "GET /api/brief/Nyaruguru.pdf · GET /api/brief/national.csv",
        })
    report, hint = build_report(db, ref)
    if report is None:
        return JSONResponse(status_code=404, content={
            "status": "error", "code": "district_not_found",
            "detail": f"No district matching '{ref}'.", "hint": hint,
        })
    if not report["sections"]:
        return JSONResponse(status_code=503, content={
            "status": "error", "code": "empty_brief",
            "detail": "No survey layers are seeded yet, so the brief has no rows.",
            "hint": "Run: python3 seed_data.py && python3 seed_lfs.py && python3 seed_vup.py",
        })
    download = _slug(ref)
    if fmt == "csv":
        payload = _csv_from_report(report)
        return Response(
            content=payload,
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="upliftrwanda-brief-{download}.csv"'},
        )
    payload = render_pdf(report)
    return Response(
        content=payload,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="upliftrwanda-brief-{download}.pdf"'},
    )


@router.get("/national")
def brief_national(format: Optional[str] = "pdf", db=Depends(get_db)):
    return _serve("national", (format or "pdf").lower(), db)


@router.get("/{ref_path}")
def brief_file(ref_path: str, format: Optional[str] = None, db=Depends(get_db)):
    """District brief; `.pdf`/`.csv` extensions work, as does ?format=."""
    ref, fmt = ref_path, format or "pdf"
    if "." in ref:
        base, _, ext = ref.rpartition(".")
        if ext.lower() == "pdf":
            ref, fmt = base, "pdf"
        elif ext.lower() == "csv":
            ref, fmt = base, "csv"
        elif base:
            return JSONResponse(status_code=400, content={
                "status": "error", "code": "unsupported_format",
                "detail": f"Format '.{ext}' is not supported (use pdf or csv).",
            })
    fmt = fmt.lower()
    if fmt not in ("pdf", "csv"):
        return JSONResponse(status_code=400, content={
            "status": "error", "code": "unsupported_format",
            "detail": f"Format '{fmt}' is not supported (use pdf or csv).",
        })
    return _serve(ref, fmt, db)
