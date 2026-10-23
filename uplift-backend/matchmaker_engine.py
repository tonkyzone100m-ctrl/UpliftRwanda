"""Matchmaker scoring engine (Module C) — explainable rule-based fit.

Given a citizen profile and the district's calibrated statistics, scores the
product catalog and returns EVERY recommendation with human-readable reasons
so community leaders can defend the advice in front of the household.

Scoring model (0-100):
  goal alignment ............ 40%   chosen livelihood goal vs product goal_fit
  segment alignment ......... 30%   age/gender/occupation/area vs segment_fit
  activity alignment ........ 15%   economic activity vs activity_fit
  access & digital readiness . 15%   phone/SACCO membership vs product digital-ness
Guardrails (contextual, not hard gates):
  * credit products without SACCO membership get a savings-history nudge
  * VUP programme windows are boosted where beneficiary poverty is deep
  * ultra-small reservation tickets soften extreme-poverty exclusion
The three highest-scoring reasons and the top district-context insight are
attached to every result — recommendations always show their math.
"""

from __future__ import annotations

from typing import Any, Optional

import product_catalog

WEIGHTS = {"goal": 0.40, "segment": 0.30, "activity": 0.15, "access": 0.15}

SEGMENT_LABELS = {
    "youth": "Youth", "adult": "Adult",
    "farmer": "Farmer", "trader": "Trader", "artisan": "Artisan",
    "service": "Service worker", "wage": "Wage earner",
    "self_employed": "Self-employed", "unemployed": "Between jobs", "mixed": "Mixed activity",
}
GOAL_LABELS = {
    "start": "Start a business", "expand": "Grow an existing business",
    "agri_inputs": "Farm inputs (seeds/fertilizer)", "education": "Education costs",
    "housing": "Housing / land", "safety_net": "Income safety net",
    "save_long": "Save for the long term", "emergency_borrow": "Bridge an emergency",
}
ACTIVITY_LABELS = {
    "agri": "Agriculture", "trade": "Trade", "service": "Services",
    "artisan": "Artisanry", "wage": "Wage work", "mixed": "Mixed activities",
}


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def score_product(product: dict, profile: dict, context: Optional[dict]) -> tuple[float, list[dict], dict]:
    """Returns (score 0-100, reasons[{kind, text, points}], boosts used)."""
    reasons: list[dict] = []
    boosts: dict[str, Any] = {}

    goal = profile.get("goal") or "expand"
    seg_age = "youth" if profile.get("age_group", "adult") == "youth" else "adult"
    gender = profile.get("gender")
    occupation = profile.get("occupation", "mixed")

    # -- goal alignment -------------------------------------------------------
    gf = product["goal_fit"].get(goal, 0.35)
    goal_score = _clamp01(gf)
    if goal_score >= 0.85:
        reasons.append({
            "kind": "fit", "points": round(goal_score * WEIGHTS["goal"], 3),
            "text": f"Purpose-built for your goal: {GOAL_LABELS.get(goal, goal)}",
        })

    # -- segment alignment ----------------------------------------------------
    sf = product["segment_fit"]
    seg_parts = [sf.get(seg_age, 0.6), sf.get(occupation, 0.65)]
    if gender == "female" and sf.get("woman") is not None:
        seg_parts.append(sf["woman"])
        if sf["woman"] >= 0.95:
            reasons.append({
                "kind": "fit", "points": 0.06,
                "text": "Women-focused window (collateral-flexible terms)",
            })
    if seg_age == "youth" and sf.get("youth", 0) >= 0.9:
        reasons.append({
            "kind": "fit", "points": 0.05,
            "text": "First-jobber friendly — youth onboarding without heavy paperwork",
        })
    area_key = "urban" if profile.get("urban") else "rural"
    seg_parts.append(sf.get(area_key, 0.8))
    segment_score = _clamp01(sum(seg_parts) / len(seg_parts))

    # -- activity alignment ---------------------------------------------------
    activity = profile.get("activity") or (
        {"farmer": "agri", "trader": "trade", "artisan": "artisan",
         "service": "service", "wage": "wage"}.get(occupation, "mixed"))
    af = product["activity_fit"].get(activity, 0.5)
    activity_score = _clamp01(af)
    if activity_score >= 0.9:
        reasons.append({
            "kind": "fit", "points": round(activity_score * WEIGHTS["activity"], 3),
            "text": f"Designed around {ACTIVITY_LABELS.get(activity, activity)} realities",
        })

    # -- access & digital -----------------------------------------------------
    has_phone = bool(profile.get("has_phone", True))
    has_sacco = bool(profile.get("has_sacco_membership", False))
    digital_ready = has_phone and product.get("digital", False)
    access_parts = [0.7]
    if product.get("digital", False):
        access_parts.append(1.0 if digital_ready else 0.35)
    else:
        access_parts.append(0.9)
    if product["category"] == "credit" and has_sacco:
        access_parts.append(1.0)
        access_parts.append(0.9)
    access_score = _clamp01(sum(access_parts) / len(access_parts))
    if product["category"] == "credit" and not has_sacco and "SACCO" not in product["provider"]:
        reasons.append({
            "kind": "guardrail", "points": 0.0,
            "text": "No SACCO membership yet — consider Ibimina/VSLA first to build savings history",
        })
    if digital_ready and product.get("digital", False):
        reasons.append({
            "kind": "fit", "points": 0.04,
            "text": "Fully digital — open and transact from your phone",
        })

    raw = (
        WEIGHTS["goal"] * goal_score
        + WEIGHTS["segment"] * segment_score
        + WEIGHTS["activity"] * activity_score
        + WEIGHTS["access"] * access_score
    )
    score = round(100.0 * raw, 1)

    # -- district-context boosts + reasons ------------------------------------
    if context:
        matches = context.get("matches", {})
        # deep beneficiary poverty → prefer VUP windows
        pov_vup = context.get("poverty_among_beneficiaries")
        if pov_vup is not None and pov_vup >= 41 and product["id"].startswith("vup_"):
            bump = 4.0
            score = round(min(99.0, score + bump), 1)
            boosts["vup_depth"] = bump
            reasons.append({
                "kind": "context", "points": bump / 100.0,
                "text": f"{context['district']}: beneficiary poverty is {pov_vup:.1f}% (national 41%) — the VUP window targets exactly this cohort",
            })
        # low formal credit → don't punish micro-first products, boost them
        formal_credit = matches.get("formal_credit")
        if formal_credit is not None and formal_credit < 24 and product["category"] in ("credit", "programme"):
            bump = 3.0
            score = round(min(99.0, score + bump), 1)
            boosts["credit_gap"] = bump
            reasons.append({
                "kind": "context", "points": bump / 100.0,
                "text": f"{context['district']}: formal credit reaches only {formal_credit:.1f}% of adults — collateral-flexible doors matter here",
            })
        # low mobile money → digital products carry an onboarding note
        mm = matches.get("mobile_money")
        if mm is not None and mm < 70 and product.get("digital", False):
            bump = 2.5
            score = round(min(99.0, score + bump), 1)
            boosts["digital_gap"] = bump
            reasons.append({
                "kind": "context", "points": bump / 100.0,
                "text": f"{context['district']}: mobile-money use is {mm:.1f}% (below the 77% national norm) — agent help available at activation",
            })
        # savings-absorbed cash economy → savings vehicles fit first
        fs = matches.get("formal_savings")
        if fs is not None and fs < 59 and product["category"] == "savings":
            bump = 3.5
            score = round(min(99.0, score + bump), 1)
            boosts["savings_gap"] = bump
            reasons.append({
                "kind": "context", "points": bump / 100.0,
                "text": f"{context['district']}: formal savings only {fs:.1f}% (national 59%) — a savings habit is the highest-return first move",
            })

    # reorder: fit reasons, context, guardrails; cap the noise
    order = {"fit": 0, "context": 1, "guardrail": 2}
    reasons = sorted(reasons, key=lambda r: (order.get(r["kind"], 3), -r["points"]))[:4]
    return score, reasons, boosts


def match(profile: dict, context: Optional[dict], top_n: int = 6) -> list[dict]:
    """Score the full catalog. Returns ranked results with explanations."""
    results = []
    for product in product_catalog.CATALOG:
        score, reasons, boosts = score_product(product, profile, context)
        results.append({
            "product_id": product["id"],
            "name": product["name"],
            "provider": product["provider"],
            "category": product["category"],
            "description": product["description"],
            "requirements": product["requirements"],
            "ticket_rwf": product["ticket_rwf"],
            "tenure": product["tenure"],
            "collateral": product["collateral"],
            "digital": product["digital"],
            "evidence": product["evidence"],
            "score": score,
            "reasons": [{k: v for k, v in r.items()} for r in reasons],
            "district_boosts": boosts,
        })
    results.sort(key=lambda r: r["score"], reverse=True)
    return results[:top_n]
