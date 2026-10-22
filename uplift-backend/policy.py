"""UpliftRwanda policy recommendation engine (backend rules module).

Evaluates district-level indicator values against the OFFICIAL national
benchmarks (FinScope 2024 / EICV7) and the dataset's own population-weighted
national means, then emits targeted interventions aligned with NST2 and
Vision 2050.

Flag lines:
    * financial vulnerability share ... flag when > 30% of adults
    * mobile money usage ............. flag when < 75% of adults
    * climate shock exposure ......... flag when above the 69% national rate
    * poverty headcount .............. flag when > 30%
    * plus formal inclusion / credit / savings / social-protection guards

Every insight is returned as a stable JSON dict consumed by the React
dashboard (`PolicyInsights` panel).
"""

from __future__ import annotations

import logging
from typing import Any

SEVERITY_RANK = {"critical": 0, "attention": 1, "strength": 2, "info": 3}

RULE_LOGGER = logging.getLogger("uplift_policy")

# Official national benchmarks (FinScope 2024 / EICV7 headline statistics)

NATIONAL_BENCHMARKS: dict[str, float] = {
    "financial_inclusion_rate": 96.0,     # 96% of adults financially included
    "transactional_account": 77.0,        # 77% hold a transactional account
    "mobile_money": 77.0,                 # 77% use mobile wallets
    "financial_exclusion_rate": 4.0,      # 4% remain excluded
    "formal_credit": 24.0,                # 24% borrow formally
    "formal_savings": 59.0,               # 59% save formally
    "climate_shock": 69.0,                # 69% experienced climate shocks
    "financial_health": 10.0,          # 10% financially healthy
    "financially_coping": 57.0,           # 57% financially coping
    "vulnerability_share": 34.0,          # 31% vulnerable + 3% extremely vulnerable
    "poverty_headcount": 27.4,            # EICV7 headline poverty
    "extreme_poverty_rate": 4.5,          # EICV7 extreme poverty
    "social_protection": 61.3,            # EICV7 programme reach
}

# Explicit intervention thresholds
VULNERABILITY_SHARE_FLAG = 30.0         # flag districts above 30% vulnerability
VULNERABILITY_SHARE_CRITICAL = 37.0     # escalate above 37%
MOBILE_MONEY_FLOOR = 75.0               # flag districts below 75% mobile money
MOBILE_MONEY_CRITICAL = 65.0
POVERTY_LIMIT = 30.0                    # flag districts above 30% poverty
INCLUSION_ATTENTION = 95.0              # >1.5 pp below the 96% national rate
INCLUSION_CRITICAL = 90.0
CLIMATE_ATTENTION = 69.0                # national exposure rate
CLIMATE_CRITICAL = 80.0
SAVINGS_FLOOR = 55.0
CREDIT_FLOOR = 21.0
SP_FLOOR = 58.0
EXTREME_POVERTY_FLOOR = 6.0

INDICATOR_LABELS = {
    "financial_inclusion_rate": "Formal + informal inclusion",
    "transactional_account": "Transactional account ownership",
    "mobile_money": "Mobile money usage",
    "financial_exclusion_rate": "Financial exclusion",
    "formal_credit": "Formal credit usage",
    "formal_savings": "Formal savings uptake",
    "poverty_headcount": "Poverty headcount",
    "extreme_poverty_rate": "Extreme poverty",
    "social_protection": "Social protection coverage",
    "climate_shock": "Climate shock exposure",
    "financial_health": "Financially healthy",
    "financially_coping": "Financially coping",
    "financially_vulnerable": "Financially vulnerable",
    "extremely_vulnerable": "Extremely vulnerable",
    "vulnerability_share": "Financial vulnerability (vulnerable + extremely)",
}


def _pct(value: float) -> str:
    return f"{value:.1f}%"


def _delta(district: float, benchmark: float) -> str:
    return f"{district - benchmark:+.1f} pp"


def vulnerability_share(metrics: dict[str, float]) -> float | None:
    """Share of adults that are (financially vulnerable + extremely vulnerable)."""
    primary = metrics.get("financially_vulnerable")
    extreme = metrics.get("extremely_vulnerable")
    if primary is None:
        return None
    if extreme is None:
        return primary
    return primary + extreme


def _compare(metric: str, metrics: dict[str, float]) -> str:
    value = metrics[metric]
    benchmark = NATIONAL_BENCHMARKS[metric]
    return (
        f"{INDICATOR_LABELS[metric]}: {_pct(value)} nationally {_pct(benchmark)}"
        f" ({_delta(value, benchmark)} vs official benchmark)."
    )


# Rule definitions


def _rule_poverty(m, nat, t):
    if m.get("poverty_headcount") is None:
        return None
    pov = m["poverty_headcount"]
    if pov > t["poverty_limit"]:
        data_lines = [
            _compare("poverty_headcount", m),
            f"Flagged rule: poverty headcount > {t["poverty_limit"]:.0f}%.",
        ]
        mean_pov = nat.get("poverty_headcount")
        if mean_pov is not None:
            data_lines.append(f"Dataset national mean: {_pct(mean_pov)}.")
        return {
            "id": "poverty-critical",
            "severity": "critical",
            "pillar": "NST2 · Social Protection",
            "title": "Declare targeted poverty-reduction response",
            "description": (
                f"Poverty headcount is {_pct(pov)}, above the 30% NSSP response "
                "guardrail, versus the EICV7 national headline of "
                f"{_pct(NATIONAL_BENCHMARKS['poverty_headcount'])}. Anchor a district "
                "poverty-reduction compact prioritizing VUP Classic Plus, direct "
                "support graduations and productive-inclusion packages."
            ),
            "data": data_lines,
        }
    national = nat.get("poverty_headcount")
    if national is not None and pov > national:
        return {
            "id": "poverty-relative",
            "severity": "attention",
            "pillar": "NST2 · Social Protection",
            "title": "Close the poverty gap against the national mean",
            "description": (
                f"Poverty stands at {_pct(pov)} — above the dataset national mean of "
                f"{_pct(national)} though within the 30% guardrail. Deploy labour-"
                "intensive public works and asset-transfers ahead of rain seasons."
            ),
            "data": [
                f"Poverty headcount: {_pct(pov)} vs national mean {_pct(national)} "
                f"({_delta(pov, national)}).",
            ],
        }
    if national is not None and pov <= national - 2.0:
        return {
            "id": "poverty-strength",
            "severity": "strength",
            "pillar": "Vision 2050 · Prosperity",
            "title": "On-trajectory poverty performance",
            "description": (
                f"Poverty at {_pct(pov)} is at least 2 pp below the national mean "
                f"({_pct(national)}). Sustain registry upkeep to keep graduation "
                "gains irreversible."
            ),
            "data": [f"Poverty headcount: {_pct(pov)} vs national mean {_pct(national)}."],
        }
    return None


def _rule_vulnerability(m, nat, t) -> dict[str, Any] | None:
    share = vulnerability_share(m)
    if share is None:
        return None
    national = nat.get("vulnerability_share", NATIONAL_BENCHMARKS["vulnerability_share"])
    if share <= t["vulnerability_share_flag"]:
        if share <= national - 3.0:
            return {
                "id": "vulnerability-strength",
                "severity": "strength",
                "pillar": "Vision 2050 · Prosperity",
                "title": "Model households for financial resilience",
                "description": (
                    f"Financial vulnerability share is {_pct(share)} — comfortably under "
                    f"the 30% national flag line. Document this district's "
                    "consumption-smoothing practices for cross-district learning."
                ),
                "data": [
                    f"Vulnerability share (vulnerable + extremely): {_pct(share)} "
                    f"vs national {_pct(national)} ({_delta(share, national)}).",
                ],
            }
        return None
    severity = "critical" if share > t["vulnerability_share_critical"] else "attention"
    return {
        "id": "vulnerability-share",
        "severity": severity,
        "pillar": "NST2 · Social Protection",
        "title": "Scale up consumption-smoothing support",
        "description": (
            f"{_pct(share)} of adults are financially vulnerable or extreme "
            f"(national flag line: {t["vulnerability_share_flag"]:.0f}%). Reinforce shock-"
            "responsive cash transfers, hedge informal-group savings with "
            "graduation support and prioritise the district in the next VUP cycle."
        ),
        "data": [
            f"Vulnerability share: {_pct(share)} vs national {_pct(national)} "
            f"({_delta(share, national)}).",
            f"Flagged rule: vulnerability share > {t["vulnerability_share_flag"]:.0f}%.",
        ],
    }


def _rule_mobile_money(m, nat, t) -> dict[str, Any] | None:
    value = m.get("mobile_money")
    if value is None:
        return None
    national = nat.get("mobile_money", NATIONAL_BENCHMARKS["mobile_money"])
    if value < t["mobile_money_floor"]:
        severity = "critical" if value < t["mobile_money_critical"] else "attention"
        return {
            "id": "mobile-money",
            "severity": severity,
            "pillar": "NST2 · Economic Transformation",
            "title": "Deepen mobile-money adoption corridors",
            "description": (
                f"Mobile-money usage is {_pct(value)}, below the {t["mobile_money_floor"]:.0f}% "
                f"flag floor (national rate {_pct(NATIONAL_BENCHMARKS['mobile_money'])}). "
                "Partner with MTN MoMo / Airtel Money on fee-free government pay-ins, "
                "agent coverage at markets, and GSM registration drives."
            ),
            "data": [
                f"Mobile money usage: {_pct(value)} vs national mean {_pct(national)} "
                f"({_delta(value, national)}).",
                f"Flagged rule: mobile money < {t["mobile_money_floor"]:.0f}%.",
            ],
        }
    if national is not None and value >= national + 3.0:
        return {
            "id": "mobile-money-strength",
            "severity": "strength",
            "pillar": "Vision 2050 · Modern Rwandan",
            "title": "Digital-finance leader in the dataset",
            "description": (
                f"Mobile-money usage of {_pct(value)} is well above the national mean "
                f"({_pct(national)}). Fixture for interoperable e-commerce and "
                "fuel-supplier payments roll-out."
            ),
            "data": [
                f"Mobile money usage: {_pct(value)} vs national mean {_pct(national)} "
                f"({_delta(value, national)}).",
            ],
        }
    return None


def _rule_inclusion(m, nat, t) -> dict[str, Any] | None:
    value = m.get("financial_inclusion_rate")
    if value is None:
        return None
    national = nat.get("financial_inclusion_rate", NATIONAL_BENCHMARKS["financial_inclusion_rate"])
    if value < t["inclusion_critical"] or value < t["inclusion_attention"]:
        severity = "critical" if value < t["inclusion_critical"] else "attention"
        return {
            "id": "inclusion-gap",
            "severity": severity,
            "pillar": "NST2 · Economic Transformation",
            "title": "Accelerate formal financial inclusion",
            "description": (
                f"Formal + informal inclusion sits at {_pct(value)} against the "
                f"FinScope 2024 national rate of 96%. Expand Umurenge SACCO outreach, "
                "tiered-KYC mobile onboarding and marketplace agent banking to close "
                "the remaining access gap."
            ),
            "data": [
                f"Financial inclusion: {_pct(value)} vs national mean {_pct(national)} "
                f"({_delta(value, national)}).",
                f"Flagged rule: inclusion < {t["inclusion_attention"]:.0f}%/"
                f"{t["inclusion_critical"]:.0f}% bands.",
            ],
        }
    if national is not None and value >= national:
        return {
            "id": "inclusion-strength",
            "severity": "strength",
            "pillar": "Vision 2050 · Prosperity",
            "title": "Benchmark district for financial inclusion",
            "description": (
                f"Inclusion of {_pct(value)} is at or above the national rate "
                f"({_pct(national)}) — the FinScope 2024 trajectory is intact here. "
                "Share the service-point model with lagging districts."
            ),
            "data": [
                f"Financial inclusion: {_pct(value)} vs national mean {_pct(national)} "
                f"({_delta(value, national)}).",
            ],
        }
    return None


def _rule_credit(m, nat, t) -> dict[str, Any] | None:
    value = m.get("formal_credit")
    if value is None or value >= t["credit_floor"]:
        return None
    national = nat.get("formal_credit", NATIONAL_BENCHMARKS["formal_credit"])
    severity = "critical" if value < t["credit_floor"] - 5.0 else "attention"
    return {
        "id": "credit-gap",
        "severity": severity,
        "pillar": "NST2 · Economic Transformation",
        "title": "Unlock affordable credit for productive households",
        "description": (
            f"Formal credit usage is {_pct(value)} (national: "
            f"{_pct(NATIONAL_BENCHMARKS['formal_credit'])}). Push the MSME credit-"
            "guarantee scheme into the district and link Umurenge SACCO lending "
            "lines with warehouse-receipt finance."
        ),
        "data": [
            f"Formal credit usage: {_pct(value)} vs national mean {_pct(national)} "
            f"({_delta(value, national)}).",
            f"Flagged rule: formal credit < {t["credit_floor"]:.0f}%.",
        ],
    }


def _rule_savings(m, nat, t) -> dict[str, Any] | None:
    value = m.get("formal_savings")
    if value is None or value >= t["savings_floor"]:
        return None
    national = nat.get("formal_savings", NATIONAL_BENCHMARKS["formal_savings"])
    severity = "critical" if value < t["savings_floor"] - 10.0 else "attention"
    return {
        "id": "savings-gap",
        "severity": severity,
        "pillar": "NST2 · Economic Transformation",
        "title": "Grow a formal savings culture",
        "description": (
            f"Formal savings uptake is {_pct(value)} (national: "
            f"{_pct(NATIONAL_BENCHMARKS['formal_savings'])}). Promote Ejo Heza long-"
            "term savings enrolment and school-based financial literacy bundled "
            "with cooperative group accounts."
        ),
        "data": [
            f"Formal savings uptake: {_pct(value)} vs national mean {_pct(national)} "
            f"({_delta(value, national)}).",
        ],
    }


def _rule_social_protection(m, nat, t) -> dict[str, Any] | None:
    value = m.get("social_protection")
    if value is None or value >= t["sp_floor"]:
        return None
    national = nat.get("social_protection", NATIONAL_BENCHMARKS["social_protection"])
    severity = "critical" if value < t["sp_floor"] - 8.0 else "attention"
    return {
        "id": "social-protection",
        "severity": severity,
        "pillar": "NST2 · Social Protection",
        "title": "Widen the social-protection umbrellas",
        "description": (
            f"Programme reach is {_pct(value)} (national composite: "
            f"{_pct(NATIONAL_BENCHMARKS['social_protection'])}). Consolidate "
            "beneficiary registries to close exclusion errors and add "
            "shock-responsive top-ups."
        ),
        "data": [
            f"Social protection coverage: {_pct(value)} vs national mean "
            f"{_pct(national)} ({_delta(value, national)}).",
        ],
    }


def _rule_climate(m, nat, t) -> dict[str, Any] | None:
    value = m.get("climate_shock")
    if value is None or value <= t["climate_attention"]:
        return None
    national = nat.get("climate_shock", NATIONAL_BENCHMARKS["climate_shock"])
    severity = "critical" if value > t["climate_critical"] else "attention"
    description = (
        f"{_pct(value)} of adults experienced climate shocks (national rate: "
        f"{_pct(NATIONAL_BENCHMARKS['climate_shock'])}). Prioritise climate-"
        "resilient finance: NAIS crop/livestock cover, weather-indexed "
        "insurance and nature-based erosion control bundled with SACCO credit."
    )
    if severity == "critical":
        title = "High climate-exposure emergency programming"
        description += (
            " Exposure exceeds the critical band (above 80%) — coordinate with "
            "MINEMA resonance and pre-position emergency liquidity."
        )
    else:
        title = "Deploy climate-resilient financial products"
    return {
        "id": "climate-resilience",
        "severity": severity,
        "pillar": "Vision 2050 · Resilience",
        "title": title,
        "description": description,
        "data": [
            f"Climate shock exposure: {_pct(value)} vs national mean {_pct(national)} "
            f"({_delta(value, national)}).",
            f"Flagged rule: exposure above national rate "
            f"{t["climate_attention"]:.0f}% / critical {t["climate_critical"]:.0f}%.",
        ],
    }


def _rule_healthy(m, nat, t) -> dict[str, Any] | None:
    value = m.get("financial_health")
    if value is None:
        return None
    national = nat.get("financial_health", NATIONAL_BENCHMARKS["financial_health"])
    if value < 9.0:
        return {
            "id": "financial-health",
            "severity": "attention",
            "pillar": "NST2 · Human Development",
            "title": "Lift households up the financial-health ladder",
            "description": (
                f"Only {_pct(value)} of adults are financially healthy (FinScope 2024 "
                f"national: {_pct(NATIONAL_BENCHMARKS['financial_health'])}). Bundle "
                "savings nudges, digital-wage payments and insurance bundles to "
                "convert coping households into healthy ones."
            ),
            "data": [
                f"Financially healthy: {_pct(value)} vs national mean {_pct(national)} "
                f"({_delta(value, national)}).",
            ],
        }
    return None


def _rule_extreme_poverty(m, nat, t) -> dict[str, Any] | None:
    value = m.get("extreme_poverty_rate")
    if value is None or value <= t["extreme_poverty_floor"]:
        return None
    national = nat.get("extreme_poverty_rate", NATIONAL_BENCHMARKS["extreme_poverty_rate"])
    return {
        "id": "extreme-poverty",
        "severity": "critical" if value > t["extreme_poverty_floor"] + 2.0 else "attention",
        "pillar": "NST2 · Social Protection",
        "title": "Intensify direct-support graduation programmes",
        "description": (
            f"Extreme poverty is {_pct(value)} (EICV7 national: "
            f"{_pct(NATIONAL_BENCHMARKS['extreme_poverty_rate'])}). Scale up Girinka "
            "livestock-transfers and Ubudehe re-categorisation so affected "
            "households graduate beyond food insecurity."
        ),
        "data": [
            f"Extreme poverty: {_pct(value)} vs national mean {_pct(national)} "
            f"({_delta(value, national)}).",
        ],
    }


RULES = (
    _rule_poverty,
    _rule_vulnerability,
    _rule_mobile_money,
    _rule_inclusion,
    _rule_credit,
    _rule_savings,
    _rule_social_protection,
    _rule_climate,
    _rule_healthy,
    _rule_extreme_poverty,
)

MAX_INSIGHTS = 8


def generate_insights(
    metrics: dict[str, float],
    national_means: dict[str, float] | None = None,
    targets: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Runs every rule and returns a render-ready payload.

    `targets` overrides the shipped official flag-lines (poverty guardrail,
    mobile-money floor, vulnerability bands, ...) for ministerial what-if
    scenarios; absent keys fall back to the official defaults above.
    """
    defaults = {
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
    t: dict[str, float] = {**defaults, **(targets or {})}
    available = {k: v for k, v in metrics.items() if v is not None}
    nat = national_means or {}
    insights: list[dict[str, Any]] = []
    for rule in RULES:
        try:
            insight = rule(available, nat, t)
        except Exception as exc:  # a broken rule must never take down the panel
            RULE_LOGGER.warning("rule %s failed: %s", rule.__name__, exc)
            continue
        if insight:
            insights.append(insight)
    insights.sort(key=lambda i: SEVERITY_RANK.get(i["severity"], 9))
    outside_baseline = {k: v for k, v in t.items() if v != defaults[k]}
    return {
        "insights": insights[:MAX_INSIGHTS],
        "using_baseline_targets": not outside_baseline,
        "active_target_overrides": outside_baseline or None,
        "thresholds": {
            "vulnerability_share_flag": t["vulnerability_share_flag"],
            "mobile_money_floor": t["mobile_money_floor"],
            "poverty_limit": t["poverty_limit"],
            "climate_attention": t["climate_attention"],
            "climate_critical": t["climate_critical"],
        },
        "benchmarks": NATIONAL_BENCHMARKS,
    }
