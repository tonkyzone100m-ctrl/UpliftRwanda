import { resolveRegionMetric } from "./stats";

/**
 * Offline mirror of the backend policy engine (policy.py).
 * Fires ONLY when the FastAPI engine is unreachable; ids/severities match the
 * backend so the UI renders the same insight cards either way.
 *
 * Backend thresholds (FinScope 2024 / EICV7 calibrated):
 *   vulnerability share > 30% (critical > 37%)   mobile money < 75% (critical < 65%)
 *   poverty > 30%                                 climate exposure > 69% (critical > 80%)
 *   inclusion < 95 (critical < 90)                savings < 55 (critical < 45)
 *   credit < 21 (critical < 16)                   social protection < 58 (critical < 50)
 *   healthy < 9                                   extreme poverty > 6 (critical > 8)
 */

const SEVERITY_ORDER = { critical: 0, attention: 1, strength: 2 };
const MAX_INSIGHTS = 8;

export function buildPolicyInsights(region, stats) {
  if (!region) return [];
  const get = (defKey) => resolveRegionMetric(region, defKey, stats);
  const value = (defKey) => get(defKey)?.entry?.value ?? null;
  const insights = [];

  const pov = value("povertyRate");
  const xpo = value("extremePoverty");
  const vul = value("vulnerableShare");
  const xvl = value("extremeVulnerable");
  const mm = value("mobileMoney");
  const inc = value("financialInclusion");
  const sav = value("formalSavings");
  const cre = value("formalCredit");
  const soc = value("socialProtection");
  const cli = value("climateShock");
  const hea = value("financialHealth");
  const national = stats?.perMetric ?? {};
  const natMean = (defKey) => national[defKey]?.mean ?? null;
  const fmt = (v) => (v == null ? "—" : `${Number(v).toFixed(1)}%`);
  const compare = (v, n) =>
    v == null || n == null ? "" : ` (${n > v ? "above" : "below"} the national mean of ${fmt(n)})`;

  const add = (insight) => insights.push(insight);

  // poverty
  if (pov != null && pov > 30) {
    add({
      id: "poverty-critical",
      severity: "critical",
      pillar: "NST2 · Social Protection",
      title: "Declare targeted poverty-reduction response",
      description:
        `Poverty headcount is ${fmt(pov)}, above the 30% NSSP response guardrail, versus the ` +
        "EICV7 national headline of 27.4%. Anchor a district poverty-reduction compact " +
        "prioritizing VUP Classic Plus, direct-support graduations and productive-inclusion packages.",
      data: [`Flagged rule: poverty headcount > 30%.`, `Poverty headcount: ${fmt(pov)} vs national 27.4%.`],
    });
  } else if (pov != null && natMean("povertyRate") != null && pov > natMean("povertyRate")) {
    add({
      id: "poverty-relative",
      severity: "attention",
      pillar: "NST2 · Social Protection",
      title: "Close the poverty gap against the national mean",
      description:
        `Poverty stands at ${fmt(pov)} — above the dataset national mean of ` +
        `${fmt(natMean("povertyRate"))} though within the 30% guardrail. Deploy labour-intensive ` +
        "public works and asset transfers ahead of rain seasons.",
      data: [`Poverty headcount: ${fmt(pov)}${compare(pov, natMean("povertyRate"))}`],
    });
  } else if (pov != null && natMean("povertyRate") != null && pov <= natMean("povertyRate") - 2) {
    add({
      id: "poverty-strength",
      severity: "strength",
      pillar: "Vision 2050 · Prosperity",
      title: "On-trajectory poverty performance",
      description:
        `Poverty at ${fmt(pov)} is at least 2 pp below the national mean ` +
        `(${fmt(natMean("povertyRate"))}). Sustain registry upkeep to keep graduation gains irreversible.`,
      data: [`Poverty headcount: ${fmt(pov)} vs national mean ${fmt(natMean("povertyRate"))}.`],
    });
  }

  // financial-health vulnerability share (FinScope composite)
  if (vul != null || xvl != null) {
    const share = (vul ?? 0) + (xvl ?? 0);
    const natShare = (() => {
      const nv = natMean("vulnerableShare");
      const nx = natMean("extremeVulnerable");
      return nv == null ? null : nv + (nx ?? 0);
    })();
    if (share > 30) {
      add({
        id: "vulnerability-share",
        severity: share > 37 ? "critical" : "attention",
        pillar: "NST2 · Social Protection",
        title: "Scale up consumption-smoothing support",
        description:
          `${fmt(share)} of adults are financially vulnerable or extreme (national flag line: ` +
          "30%). Reinforce shock-responsive cash transfers, hedge informal-group savings with " +
          "graduation support and prioritise the district in the next VUP cycle.",
        data: [
          `Vulnerability share (vulnerable + extremely): ${fmt(share)} vs national ${fmt(natShare ?? 34)}${compare(share, natShare)}.`,
          "Flagged rule: vulnerability share > 30%.",
        ],
      });
    } else if (natShare != null && share <= natShare - 3) {
      add({
        id: "vulnerability-strength",
        severity: "strength",
        pillar: "Vision 2050 · Prosperity",
        title: "Model households for financial resilience",
        description:
          `Financial vulnerability share is ${fmt(share)} — comfortably under the 30% national ` +
          "flag line. Document this district's consumption-smoothing practices for cross-district learning.",
        data: [
          `Vulnerability share (vulnerable + extremely): ${fmt(share)} vs national ${fmt(natShare)}${compare(share, natShare)}.`,
        ],
      });
    }
  }

  // mobile money
  if (mm != null && mm < 75) {
    add({
      id: "mobile-money",
      severity: mm < 65 ? "critical" : "attention",
      pillar: "NST2 · Economic Transformation",
      title: "Deepen mobile-money adoption corridors",
      description:
        `Mobile-money usage is ${fmt(mm)}, below the 75% flag floor (FinScope 2024 national: 77%). ` +
        "Partner with MTN MoMo / Airtel Money on fee-free government pay-ins, agent coverage at " +
        "markets, and GSM registration drives.",
      data: [`Mobile money usage: ${fmt(mm)} — flagged rule: mobile money < 75%.`],
    });
  } else if (mm != null && natMean("mobileMoney") != null && mm >= natMean("mobileMoney") + 3) {
    add({
      id: "mobile-money-strength",
      severity: "strength",
      pillar: "Vision 2050 · Modern Rwandan",
      title: "Digital-finance leader in the dataset",
      description:
        `Mobile-money usage of ${fmt(mm)} is well above the national mean ` +
        `(${fmt(natMean("mobileMoney"))}). Fixture for interoperable e-commerce and fuel-supplier payments roll-out.`,
      data: [`Mobile money usage: ${fmt(mm)} vs national mean ${fmt(natMean("mobileMoney"))}${compare(mm, natMean("mobileMoney"))}.`],
    });
  }

  // inclusion
  if (inc != null && inc < 90) {
    add({
      id: "inclusion-gap",
      severity: "critical",
      pillar: "NST2 · Economic Transformation",
      title: "Accelerate formal financial inclusion",
      description:
        `Formal inclusion is ${fmt(inc)}, below the 90% critical band (FinScope 2024 national: 96%). ` +
        "Expand Umurenge SACCO outreach, tiered-KYC mobile onboarding and agent banking.",
      data: [`Financial inclusion: ${fmt(inc)} — critical band < 90% / attention < 95%.`],
    });
  } else if (inc != null && inc < 95) {
    add({
      id: "inclusion-gap",
      severity: "attention",
      pillar: "NST2 · Economic Transformation",
      title: "Push inclusion toward the 96% frontier",
      description:
        `Inclusion is ${fmt(inc)} — within 1.5 pp of the FinScope 2024 national rate of 96% ` +
        "but not on it. Target the residual informal-only adults with SACCO linkage campaigns.",
      data: [`Financial inclusion: ${fmt(inc)} — attention band < 95%.`],
    });
  } else if (inc != null && inc >= 96) {
    add({
      id: "inclusion-strength",
      severity: "strength",
      pillar: "Vision 2050 · Prosperity",
      title: "Benchmark district for financial inclusion",
      description:
        `Inclusion at ${fmt(inc)} meets or beats the 96% FinScope 2024 national achievement. ` +
        "Document the service-point model and share playbooks with lagging districts.",
      data: [`Financial inclusion: ${fmt(inc)} (benchmark 96%).`],
    });
  }

  // credit / savings
  if (cre != null && cre < 21) {
    add({
      id: "credit-gap",
      severity: cre < 16 ? "critical" : "attention",
      pillar: "NST2 · Economic Transformation",
      title: "Unlock affordable credit for productive households",
      description:
        `Formal credit sits at ${fmt(cre)} — below the 21% engine floor (FinScope 2024 national: 24%). ` +
        "Push the MSME credit-guarantee scheme and SACCO lending lines with warehouse-receipt finance.",
      data: [`Formal credit: ${fmt(cre)} — flagged rule: formal credit < 21%.`],
    });
  }
  if (sav != null && sav < 55) {
    add({
      id: "savings-gap",
      severity: sav < 45 ? "critical" : "attention",
      pillar: "NST2 · Economic Transformation",
      title: "Grow a formal savings culture",
      description:
        `Formal savings at ${fmt(sav)} — below the 55% engine floor (FinScope 2024 national: 59%). ` +
        "Promote Ejo Heza long-term enrolment and financial-literacy bundles with cooperative accounts.",
      data: [`Formal savings: ${fmt(sav)} — flagged rule: formal savings < 55%.`],
    });
  }

  // social protection
  if (soc != null && soc < 58) {
    add({
      id: "social-protection",
      severity: soc < 50 ? "critical" : "attention",
      pillar: "NST2 · Human Development",
      title: "Widen the social protection umbilicals",
      description:
        `Coverage of social protection programmes trails the 58% engine floor (EICV7 national: 61.3%). ` +
        "Consolidate beneficiary registries to prevent exclusion errors and enable shock-responsive top-ups.",
      data: [`Social protection coverage: ${fmt(soc)} — flagged rule: < 58%.`],
    });
  }

  // climate resilience (FinScope 2024: 69% national)
  if (cli != null && cli > 69) {
    add({
      id: "climate-resilience",
      severity: cli > 80 ? "critical" : "attention",
      pillar: "NST2 · Human Development",
      title: "Scale climate-smart risk protection",
      description:
        `Climate-shock exposure is ${fmt(cli)} — above the 69% FinScope 2024 national exposure ` +
        "(critical band > 80%). Bundle NAIS crop/livestock cover and shock-responsive transfers " +
        "with drought-deferred savings windows.",
      data: [`Climate shock exposure: ${fmt(cli)} — attention > 69% / critical > 80%.`],
    });
  }

  // financial health ladder (FinScope 2024: 10% healthy)
  if (hea != null && hea < 9) {
    add({
      id: "financial-health",
      severity: "attention",
      pillar: "NST2 · Human Development",
      title: "Lift households up the financial-health ladder",
      description:
        `Only ${fmt(hea)} of adults are financially healthy (FinScope 2024 national: 10%). ` +
        "Bundle savings nudges, digital-wage payments and insurance to convert coping households into healthy ones.",
      data: [`Financially healthy: ${fmt(hea)} — flagged rule: healthy share < 9%.`],
    });
  }

  // extreme poverty (EICV7: 4.5%)
  if (xpo != null && xpo > 6) {
    add({
      id: "extreme-poverty",
      severity: xpo > 8 ? "critical" : "attention",
      pillar: "NST2 · Social Protection",
      title: "Intensify direct-support graduation programmes",
      description:
        `Extreme poverty is ${fmt(xpo)} (EICV7 national: 4.5%). Scale up Girinka livestock ` +
        "transfers and Ubudehe re-categorisation so affected households graduate beyond food insecurity.",
      data: [`Extreme poverty: ${fmt(xpo)} — flagged rule: > 6% / critical > 8%.`],
    });
  }

  return insights
    .sort((a, b) => SEVERITY_ORDER[a.severity] - SEVERITY_ORDER[b.severity])
    .slice(0, MAX_INSIGHTS);
}
