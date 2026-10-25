"""JWT-gated administrative mutation routes for UpliftRwanda.

Every route here requires a Bearer access token (auth.require_admin).
Analytical read routes stay public by design - world-readable intelligence,
credential-gated writes.
"""

from __future__ import annotations

import logging
import math
from typing import Any

from fastapi import Depends, APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from auth import get_current_admin
from models import NationalTarget, Region, Indicator, SurveyMetric
from main import get_db
from targets import TARGET_DEFAULTS, effective_targets, targets_metadata, validate_targets, now_stamp

logger = logging.getLogger("uplift_admin")

router = APIRouter(prefix="/api", tags=["ministerial-admin"])

_MAX_UPLOAD_ROWS = 5000


@router.get("/targets")
def get_national_targets(db: Session = Depends(get_db)):
    """Public: current effective policy targets (official defaults + overrides)."""
    return {
        "status": "success",
        "defaults": TARGET_DEFAULTS,
        "targets": effective_targets(db),
        "entries": targets_metadata(db),
    }


class TargetsUpdate(BaseModel):
    targets: dict[str, Any] = Field(default_factory=dict)
    reason: str = Field(default="", max_length=240)
    reset_to_official: bool = False


@router.post("/admin/targets")
def update_national_targets(
    payload: TargetsUpdate,
    db: Session = Depends(get_db),
    admin: dict = Depends(get_current_admin),
):
    """Ministerial override of the policy-engine baseline (JWT required)."""
    clean, errors = validate_targets(payload.targets)
    if payload.reset_to_official:
        deleted = db.query(NationalTarget).delete()
        db.commit()
        logger.info("Targets reset to official defaults by %s (%s rows)", admin["username"], deleted)
        return {
            "status": "success",
            "action": "reset_to_official",
            "removed_overrides": deleted,
            "targets": effective_targets(db),
            "entries": targets_metadata(db),
        }
    if errors:
        return JSONResponse(
            status_code=422,
            content={
                "status": "error",
                "code": "invalid_targets",
                "detail": "Some targets were rejected.",
                "errors": errors,
                "rejected_keys": [k for k in payload.targets if k not in clean],
            },
        )
    if not clean:
        return JSONResponse(
            status_code=422,
            content={
                "status": "error",
                "code": "empty_update",
                "detail": "Provide a non-empty targets map, or set reset_to_official=true.",
            },
        )
    stamp = now_stamp()
    existing = {
        row.target_key: row
        for row in db.execute(select(NationalTarget)).scalars().all()
        if row.target_key in clean
    }
    for key, value in clean.items():
        row = existing.get(key)
        if row:
            row.value = value
            row.updated_by = admin["username"]
            row.updated_at = stamp
        else:
            db.add(NationalTarget(
                target_key=key,
                value=value,
                updated_by=admin["username"],
                updated_at=stamp,
            ))
    db.commit()
    logger.info(
        "Policy targets updated by %s: %s (%s)",
        admin["username"], clean, payload.reason or "no reason given",
    )
    return {
        "status": "success",
        "applied": clean,
        "reason": payload.reason,
        "targets": effective_targets(db),
        "entries": targets_metadata(db),
    }


class MicrodataRow(BaseModel):
    district: str = Field(min_length=1, max_length=64)
    indicator_code: str = Field(min_length=1, max_length=64)
    survey_year: int = Field(ge=1990, le=2100)
    value: float


class MicrodataUpload(BaseModel):
    rows: list[MicrodataRow] = Field(max_length=_MAX_UPLOAD_ROWS)


@router.post("/admin/microdata")
def upload_microdata(
    payload: MicrodataUpload,
    db: Session = Depends(get_db),
    admin: dict = Depends(get_current_admin),
):
    """Ministerial microdata ingestion (JWT required).

    Upsert semantics: one observation per (district, indicator_code, survey_year).
    A single dynamic `INSERT ... ON CONFLICT ON CONSTRAINT
    uq_metric_region_indicator_year DO UPDATE SET value = EXCLUDED.value`
    statement covers both dialects (PostgreSQL prod, SQLite tests); duplicate
    tuples inside one payload collapse, last value wins. Off-domain values are
    rejected per-indicator using the catalog unit.
    """
    if not payload.rows:
        return JSONResponse(status_code=422, content={
            "status": "error", "code": "empty_upload", "detail": "No rows supplied.",
        })
    regions = {
        r.district.strip().lower(): r for r in db.execute(select(Region)).scalars().all()
    }
    indicators = {
        i.indicator_code.strip().lower(): i for i in db.execute(select(Indicator)).scalars().all()
    }
    errors: list[dict[str, Any]] = []
    prepared: list[tuple[Region, Indicator, int, float]] = []
    for n, row in enumerate(payload.rows, start=1):
        region = regions.get(row.district.strip().lower())
        if region is None:
            errors.append({"row": n, "district": row.district, "error": "Unknown district."})
            continue
        indicator = indicators.get(row.indicator_code.strip().lower())
        if indicator is None:
            errors.append({"row": n, "indicator_code": row.indicator_code, "error": "Unknown indicator_code (catalog lookup failed)."})
            continue
        value = row.value
        if not math.isfinite(value):
            errors.append({"row": n, "value": row.value, "error": "Value must be finite."})
            continue
        unit = (indicator.unit or "").lower()
        upper = 112.0 if ("index" in unit or "score" in unit or unit == "pts") else 100.0
        if value < 0 or value > upper:
            errors.append({
                "row": n, "value": value,
                "error": f"Out of domain for {indicator.indicator_code} (unit '{indicator.unit}'): expected 0-{upper:.0f}.",
            })
            continue
        prepared.append((region, indicator, row.survey_year, value))

    unique: dict[tuple[int, int, int], float] = {}
    for region, indicator, year, value in prepared:
        unique[(region.id, indicator.id, year)] = value
    upsert_rows = [
        {"region_id": rid, "indicator_id": iid, "survey_year": year, "value": value}
        for (rid, iid, year), value in unique.items()
    ]

    existing_keys = set(
        db.execute(
            select(SurveyMetric.region_id, SurveyMetric.indicator_id, SurveyMetric.survey_year)
        ).all()
    )
    inserted = sum(1 for key in unique if key not in existing_keys)
    updated = len(unique) - inserted

    if upsert_rows:
        try:
            con = db.connection()
            insert_choice = pg_insert if con.dialect.name == "postgresql" else sqlite_insert
            conflict_target = (
                {"constraint": "uq_metric_region_indicator_year"}
                if con.dialect.name == "postgresql"
                else {"index_elements": ["region_id", "indicator_id", "survey_year"]}
            )
            base = insert_choice(SurveyMetric)
            stmt = base.on_conflict_do_update(
                **conflict_target,
                set_={"value": base.excluded.value},
            )
            for start in range(0, len(upsert_rows), 500):
                db.execute(stmt, upsert_rows[start : start + 500])
            db.commit()
        except SQLAlchemyError as exc:
            db.rollback()
            logger.error("Microdata upload failed for %s: %s", admin["username"], exc)
            return JSONResponse(status_code=500, content={
                "status": "error",
                "code": "upload_persist_failed",
                "detail": "The upload could not be committed; nothing was written.",
            })
    logger.info(
        "Microdata upload by %s: %s inserted / %s updated / %s rejected",
        admin["username"], inserted, updated, len(errors),
    )
    return {
        "status": "success" if not errors else "partial",
        "rows_processed": len(unique),
        "inserted": inserted,
        "updated": updated,
        "rejected": len(errors),
        "errors": errors[:50],
    }
