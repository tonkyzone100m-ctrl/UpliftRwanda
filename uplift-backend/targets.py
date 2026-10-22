"""Ministerial baseline targets for the policy engine.

Official NISR statistic benchmarks (FinScope 2024 / EICV7 headline rates) are
NOT tunable — they are measured facts. What ministers may legally adjust are
the intervention flag-lines derived from those statistics (poverty guardrail,
mobile-money floor, vulnerability flag bands, ...).
"""

from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session

from models import NationalTarget
from policy import (
    CLIMATE_ATTENTION,
    CLIMATE_CRITICAL,
    CREDIT_FLOOR,
    EXTREME_POVERTY_FLOOR,
    INCLUSION_ATTENTION,
    INCLUSION_CRITICAL,
    MOBILE_MONEY_CRITICAL,
    MOBILE_MONEY_FLOOR,
    POVERTY_LIMIT,
    SAVINGS_FLOOR,
    SP_FLOOR,
    VULNERABILITY_SHARE_CRITICAL,
    VULNERABILITY_SHARE_FLAG,
)

TARGET_DEFAULTS: dict[str, float] = {
    "poverty_limit": POVERTY_LIMIT,
    "vulnerability_share_flag": VULNERABILITY_SHARE_FLAG,
    "vulnerability_share_critical": VULNERABILITY_SHARE_CRITICAL,
    "mobile_money_floor": MOBILE_MONEY_FLOOR,
    "mobile_money_critical": MOBILE_MONEY_CRITICAL,
    "inclusion_attention": INCLUSION_ATTENTION,
    "inclusion_critical": INCLUSION_CRITICAL,
    "climate_attention": CLIMATE_ATTENTION,
    "climate_critical": CLIMATE_CRITICAL,
    "savings_floor": SAVINGS_FLOOR,
    "credit_floor": CREDIT_FLOOR,
    "sp_floor": SP_FLOOR,
    "extreme_poverty_floor": EXTREME_POVERTY_FLOOR,
}


def validate_targets(payload: dict) -> tuple[dict[str, float], list[str]]:
    """Whitelist + range check. Returns (clean, errors)."""
    clean: dict[str, float] = {}
    errors: list[str] = []
    for key, raw in (payload or {}).items():
        if key not in TARGET_DEFAULTS:
            errors.append(f"Unknown target '{key}' — allowed keys: {', '.join(sorted(TARGET_DEFAULTS))}.")
            continue
        try:
            value = float(raw)
        except (TypeError, ValueError):
            errors.append(f"Target '{key}' must be a number, got {raw!r}.")
            continue
        if not 0.0 <= value <= 100.0:
            errors.append(f"Target '{key}' out of range (0-100): {value}.")
            continue
        clean[key] = round(value, 2)
    ordered_criticals = (
        ("vulnerability_share_flag", "vulnerability_share_critical"),
        ("mobile_money_critical", "mobile_money_floor"),
        ("inclusion_critical", "inclusion_attention"),
        ("climate_attention", "climate_critical"),
    )
    for lower_key, upper_key in ordered_criticals:
        lower = clean.get(lower_key, TARGET_DEFAULTS[lower_key])
        upper = clean.get(upper_key, TARGET_DEFAULTS[upper_key])
        if lower >= upper:
            errors.append(
                f"Incoherent band: '{lower_key}' ({lower}) must stay below '{upper_key}' ({upper})."
            )
    return clean, errors


def effective_targets(db: Session) -> dict[str, float]:
    """Official defaults merged with stored ministerial overrides."""
    merged = dict(TARGET_DEFAULTS)
    for row in db.execute(select(NationalTarget)).scalars().all():
        if row.target_key in TARGET_DEFAULTS:
            merged[row.target_key] = float(row.value)
    return merged


def targets_metadata(db: Session) -> list[dict]:
    """Per-key status for the console: official default vs ministerial override."""
    rows = {
        r.target_key: r
        for r in db.execute(select(NationalTarget)).scalars().all()
        if r.target_key in TARGET_DEFAULTS
    }
    meta = []
    for key, default in TARGET_DEFAULTS.items():
        row = rows.get(key)
        meta.append(
            {
                "target_key": key,
                "official_default": default,
                "current": float(row.value) if row else default,
                "is_overridden": row is not None,
                "updated_by": row.updated_by if row else None,
                "updated_at": row.updated_at if row else None,
            }
        )
    return meta


def now_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
