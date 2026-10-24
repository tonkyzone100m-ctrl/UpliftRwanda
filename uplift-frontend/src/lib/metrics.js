export function normKey(str) {
  return String(str ?? "").toLowerCase().replace(/[^a-z0-9]/g, "");
}

export function entryMatches(row, { aliases, rejects = [] }) {
  const code = normKey(row.indicator_code);
  const name = normKey(row.indicator_name);
  if (rejects.some((r) => code.includes(r) || name.includes(r))) return false;
  return aliases.some((a) => code.includes(a) || name.includes(a));
}

/**
 * Canonical indicator registry, calibrated to the official NISR statistics:
 *   FinScope 2024 - inclusion 96% (7.8m) - transactional accounts 77% (6.2m)
 *                  mobile wallets 77% - formal credit 24% - formal savings 59%
 *                  climate shocks 69% - health tiers 10/57/31/3
 *   EICV7 2023/24 - poverty 27.4% - extreme poverty 4.5% - social protection 61.3%
 * Thresholds below mirror the backend policy engine (policy.py).
 */
export const METRIC_DEFS = [
  {
    key: "financialInclusion",
    label: "Financial Inclusion",
    icon: "shield-check",
    aliases: ["financialinclusion", "accesstofinance", "financialaccess"],
    rejects: ["exclusion", "rategap"],
    direction: "higher",
    criticalLow: 90,
    target: ">= 96% (FinScope 2024)",
  },
  {
    key: "formalInclusion",
    label: "Formal Inclusion",
    icon: "landmark",
    aliases: ["formalinclusion", "formallyserved", "formalfinancialinclusion"],
    rejects: [],
    direction: "higher",
    criticalLow: 88,
    target: ">= 92% (FinScope 2024: 7.5m adults)",
  },
  {
    key: "transactionalAccount",
    label: "Transactional Account Ownership",
    icon: "landmark",
    aliases: ["transactionalaccount", "accountownership", "bankingaccess", "depositaccount"],
    rejects: [],
    direction: "higher",
    criticalLow: 77,
    target: ">= 77% (FinScope 2024) · 6.2m adults",
  },
  {
    key: "financialExclusion",
    label: "Financial Exclusion",
    icon: "ban",
    aliases: ["financialexclusion", "exclusion"],
    rejects: [],
    direction: "lower",
    criticalHigh: 10,
    target: "< 10% (FinScope 2024: 4%)",
  },
  {
    key: "mobileMoney",
    label: "Mobile Money Usage",
    icon: "smartphone",
    aliases: ["mobilemoney", "momo"],
    rejects: [],
    direction: "higher",
    criticalLow: 77,
    target: ">= 77% (FinScope 2024) · engine rule < 75%",
  },
  {
    key: "formalSavings",
    label: "Formal Savings",
    icon: "piggy-bank",
    aliases: ["formalsavings", "savings", "saving"],
    rejects: ["loan", "credit", "informalsavings"],
    direction: "higher",
    criticalLow: 59,
    target: ">= 59% (FinScope 2024) · engine rule < 55%",
  },
  {
    key: "formalCredit",
    label: "Formal Credit Usage",
    icon: "handshake",
    aliases: ["formalcredit", "creditaccess", "borrowing", "loanaccess", "credit"],
    rejects: [],
    direction: "higher",
    criticalLow: 24,
    target: ">= 24% (FinScope 2024) · engine rule < 21%",
  },
  {
    key: "socialProtection",
    label: "Social Protection",
    icon: "heart-handshake",
    aliases: ["socialprotection", "protectioncoverage", "umurenge", "girinka", "ubudehe", "visionprogram"],
    rejects: [],
    direction: "higher",
    criticalLow: 61,
    target: ">= 61.3% (EICV7) · engine rule < 58%",
  },
  {
    key: "vupPublicWorks",
    label: "VUP Public Works",
    icon: "hammer",
    aliases: ["vuppublicworks", "publicworks"],
    rejects: [],
    direction: "higher",
    criticalLow: 10,
    target: "TUNABLE 21% (EICV7 VUP)",
  },
  {
    key: "vupDirectSupport",
    label: "VUP Direct Support",
    icon: "hand-heart",
    aliases: ["vupdirectsupport", "directsupport"],
    rejects: [],
    direction: "higher",
    criticalLow: 4,
    target: "TUNABLE 9.5% (EICV7 VUP)",
  },
  {
    key: "povertyRate",
    label: "Poverty Headcount",
    icon: "trending-down",
    aliases: ["povertyheadcount", "povertyrate", "povertyincidence", "poverty"],
    rejects: ["extreme", "gap", "depth", "severity", "vulnerab"],
    direction: "lower",
    criticalHigh: 30,
    target: "< 30% (EICV7: 27.4%)",
  },
  {
    key: "extremePoverty",
    label: "Extreme Poverty",
    icon: "alert",
    aliases: ["extremepoverty"],
    rejects: [],
    direction: "lower",
    criticalHigh: 6,
    target: "< 6% (EICV7: 4.5%)",
  },
  {
    key: "climateShock",
    label: "Climate Shock Exposure",
    icon: "cloud-lightning",
    aliases: ["climateshock", "shockexposure", "shock"],
    rejects: [],
    direction: "lower",
    criticalHigh: 69,
    target: "< 69% (FinScope 2024)",
  },
  {
    key: "financialHealth",
    label: "Financially Healthy",
    icon: "heart-pulse",
    aliases: ["financialhealth", "financiallyhealthy", "healthy"],
    rejects: ["coping"],
    direction: "higher",
    criticalLow: 10,
    target: ">= 10% (FinScope 2024)",
  },
  {
    key: "financiallyCoping",
    label: "Financially Coping",
    icon: "activity",
    aliases: ["financiallycoping"],
    rejects: [],
    direction: "higher",
    criticalLow: 57,
    target: "57% (FinScope 2024)",
  },
  {
    key: "vulnerableShare",
    label: "Financially Vulnerable",
    icon: "shield-alert",
    aliases: ["financiallyvulnerable", "vulnerability"],
    rejects: ["extreme"],
    direction: "lower",
    criticalHigh: 31,
    target: "< 31% (FinScope 2024) · engine rule > 30%",
  },
  {
    key: "extremeVulnerable",
    label: "Extremely Vulnerable",
    icon: "shield-x",
    aliases: ["extremelyvulnerable"],
    rejects: [],
    direction: "lower",
    criticalHigh: 6,
    target: "< 6% (FinScope 2024: 3%)",
  },
  // Living conditions / infrastructure (EICV7)
  {
    key: "electricityAccess",
    label: "Electricity Access",
    icon: "zap",
    aliases: ["electricityaccess", "electricity"],
    rejects: [],
    direction: "higher",
    criticalLow: 55,
    target: ">= 72% (EICV7)",
  },
  {
    key: "improvedWater",
    label: "Improved Water Access",
    icon: "droplets",
    aliases: ["improvedwater", "wateraccess"],
    rejects: [],
    direction: "higher",
    criticalLow: 80,
    target: ">= 90% (EICV7)",
  },
  {
    key: "modernFlooring",
    label: "Modern Solid Flooring",
    icon: "layers",
    aliases: ["modernflooring", "floormaterial"],
    rejects: [],
    direction: "higher",
    criticalLow: 12,
    target: "TUNABLE 25% (EICV7)",
  },
  // CFSVA 2024 layer (WFP/NISR) — dedicated district_cfsva_metrics table
  {
    key: "fiesModerateSevere",
    label: "Food Insecurity (moderate+severe)",
    icon: "package-x",
    aliases: ["fiesmoderateseverepct", "moderatesevere", "moderatelyseverelyfoodinsecure"],
    rejects: [],
    direction: "lower",
    criticalHigh: 25,
    target: "< 25% (CFSVA 2024)",
  },
  {
    key: "fiesSevere",
    label: "Severe Food Insecurity",
    icon: "life-buoy",
    aliases: ["fiesseverepct", "severefoodinsecurity"],
    rejects: [],
    direction: "lower",
    criticalHigh: 4.5,
    target: "< 4.5% (CFSVA 2024: 1%)",
  },
  {
    key: "foodConsumptionScore",
    label: "Food Consumption Score",
    icon: "wheat",
    aliases: ["foodconsumptionscore"],
    rejects: ["poor"],
    direction: "higher",
    criticalLow: 42,
    target: ">= 42 pts (IPC threshold)",
  },
  {
    key: "fcsPoor",
    label: "Poor Food Consumption",
    icon: "utensils-crossed",
    aliases: ["fcspoorpct", "poorfoodconsumption"],
    rejects: [],
    direction: "lower",
    criticalHigh: 10,
    target: "< 10% (CFSVA 2024)",
  },
  {
    key: "hdds",
    label: "Dietary Diversity (HDDS)",
    icon: "utensils",
    aliases: ["hdds", "dietarydiversity"],
    rejects: [],
    direction: "higher",
    criticalLow: 4.5,
    target: ">= 6.2 pts (CFSVA 2024)",
  },
  {
    key: "stunting",
    label: "Child Stunting",
    icon: "sprout",
    aliases: ["stuntingpct", "stunting"],
    rejects: [],
    direction: "lower",
    criticalHigh: 29,
    target: "< 29% (CFSVA 2024)",
  },
  {
    key: "wasting",
    label: "Child Wasting",
    icon: "activity-2",
    aliases: ["wastingpct", "wasting"],
    rejects: [],
    direction: "lower",
    criticalHigh: 4,
    target: "< 4% (CFSVA 2024)",
  },
  {
    key: "rcsi",
    label: "Coping Strategies Index",
    icon: "life-buoy",
    aliases: ["rcsi", "copingstrategies"],
    rejects: ["financially", "share"],
    direction: "lower",
    criticalHigh: 19,
    target: "< 19 (CFSVA 2024)",
  },
  {
    key: "harvestLoss",
    label: "Harvest Loss Exposure",
    icon: "package",
    aliases: ["harvestlosspct", "harvestloss"],
    rejects: [],
    direction: "lower",
    criticalHigh: 30,
    target: "< 30% (CFSVA 2024)",
  },
];

export const METRIC_COUNT = METRIC_DEFS.length;

export function resolveMetricDef(row) {
  return METRIC_DEFS.find((def) => entryMatches(row, def)) ?? null;
}

export function formatMetricValue(entry, { compact = false } = {}) {
  const v = entry.value;
  const rawUnit = String(entry.unit ?? "");
  const unit = normKey(rawUnit);
  if (rawUnit.includes("%") || unit.includes("percent") || unit.includes("pct")) {
    return `${v.toFixed(1)}%`;
  }
  if (unit.includes("index") || unit.includes("ratio")) {
    const scaled = v > 0 && v <= 1 ? `${(v * 100).toFixed(1)}%` : v.toFixed(2);
    return compact ? scaled : `${scaled} (index)`;
  }
  return v.toFixed(1);
}

export function metricStatus(def, entry, national) {
  if (!def || entry.value == null) return "neutral";
  if (def.direction === "higher") {
    if (def.criticalLow != null && entry.value < def.criticalLow) return "critical";
    if (national?.metrics?.[def.key] != null && entry.value < national.metrics[def.key].value) return "below";
    return "good";
  }
  if (def.criticalHigh != null && entry.value > def.criticalHigh) return "critical";
  if (national?.metrics?.[def.key] != null && entry.value > national.metrics[def.key].value) return "worse";
  return "good";
}
