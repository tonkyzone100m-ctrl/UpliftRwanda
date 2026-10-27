import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

// UI-level EN/RW strings for static chrome: tabs, headers, button labels, status text.
// Survey data and indicator names stay in their source language.

const STORAGE_KEY = "uplift.lang";

const DICTIONARY = {
  en: {
    "lang.toggleAria": "Switch language",

    // Navigation tabs
    "tab.dashboard": "National Intelligence Dashboard",
    "tab.lab": "Policy Scenario Lab",
    "tab.rdhs": "RDHS 2025 Living Standards",
    "tab.labour": "Labour Market LFS 2025",
    "tab.vup": "VUP Social Protection",
    "tab.inclusion": "Inclusion & Matchmaker",
    "tab.explorer": "District Explorer",

    // Header
    "header.dashboardViews": "Dashboard views",
    "header.live": "Live · Open Data",
    "header.liveTitle": "API responding · dataset loaded from the live database",
    "header.heroBadge": "Public Data · No sign-in required",
    "header.heroDescription":
      "District-level evidence on financial inclusion, food security, labour, VUP and living standards — one dashboard, zero sign-in.",
    "header.dataPoints": "Data points",
    "header.liveFromDb": "live from the database",
    "header.loading": "loading",
    "header.districts": "Districts",
    "header.allMapped": "all of Rwanda mapped",
    "header.surveyVintage": "Survey vintage",

    // Ministerial portal button
    "portal.button": "Ministerial Portal",
    "portal.session": "Ministerial session",
    "portal.sessionTitle": "Sign in to the ministerial console",

    // Filters
    "filters.aria": "Filters and search",
    "filters.searchLabel": "Search indicators · districts · provinces",
    "filters.searchPlaceholder": "e.g. mobile money, poverty, Kigali…",
    "filters.clearSearch": "Clear search",
    "filters.district": "District",
    "filters.allDistricts": "All districts",
    "filters.category": "Data category",
    "filters.allCategories": "All categories · {count} data points",
    "filters.of": "of",
    "filters.dataPoints": "data points",
    "filters.scopeDistrict": "in {district}",
    "filters.scopeAll": "across all districts",
    "filters.syncedAt": "synced {time}",
    "filters.removeFilter": "Remove filter: {label}",
    "filters.reset": "Reset",
    "filters.refresh": "Refresh",

    // Summary cards
    "cards.nationalMean": "National mean across districts",
    "cards.inclusionLabel": "Avg · Financial Inclusion",
    "cards.inclusionSub": "{mean} · NST2 benchmark ≥ 80%",
    "cards.povertyLabel": "Avg · Poverty Headcount",
    "cards.povertySub": "{mean} · guardrail < 30%",
    "cards.socialLabel": "Avg · Social Protection",
    "cards.socialSub": "{mean} · target ≥ 60%",
    "cards.topInclusion": "Top Inclusion District",
    "cards.noInclusion": "No inclusion data yet",
    "cards.highestPoverty": "Highest Poverty",
    "cards.noPoverty": "No poverty data yet",

    // Status / loading / errors
    "status.loading": "Loading national survey metrics…",
    "status.errorTitle": "We couldn't load the survey data",
    "status.unexpected": "An unexpected error occurred.",
    "status.checkFastapi": "Check that the FastAPI service is reachable at",
    "status.checkDb": "Confirm the PostgreSQL {db} connection",
    "status.tryAgain": "Try again",
    "status.refreshFailed": "Live refresh failed:",
    "status.showingSnapshot": "showing the last successful snapshot.",
    "status.unknownError": "unknown error",
    "status.dismiss": "Dismiss refresh error",
    "footer.about":
      "UpliftRwanda · NISR 2026 Big Data Hackathon — Track 2: Financial Inclusion & Poverty Reduction. Data inspired by EICV 7 / FinScope Rwanda.",
    "footer.records": "{count} records",

    // App-level states
    "app.noDataTitle": "No usable district data was returned",
    "app.noDataBody":
      "The API responded, but the dataset contained no district rows. Ministers can regenerate it from the",
    "app.noDataTail": ", then refresh.",
    "app.reloadDataset": "Reload dataset",
    "metrics.emptyHint":
      "No rows match your current filters — try a broader search term or reset the filters.",
  },

  rw: {
    "lang.toggleAria": "Hindura ururimi",

    // Navigation tabs
    "tab.dashboard": "Imbonerahamwe y'Amakuru y'Igihugu",
    "tab.lab": "Isuzuma ry'Ingamba",
    "tab.rdhs": "RDHS 2025 · Imibereho",
    "tab.labour": "Isoko ry'Akazi LFS 2025",
    "tab.vup": "VUP · Imibereho Myiza",
    "tab.inclusion": "Kwinjira mu Mafaranga n'Ihuzabikorwa",
    "tab.explorer": "Shakisha Uturere",

    // Header
    "header.dashboardViews": "Ibyiciro by'imbonerahamwe",
    "header.live": "Ku Kirwa · Amakuru Yugurwe",
    "header.liveTitle": "API ikora · amakuru yavuye mu bubiko bw'amakuru",
    "header.heroBadge": "Amakuru Rusange · Nta Kwiyandikisha Bisabwa",
    "header.heroDescription":
      "Amakuru ku rwego rw'uturere: kwinjira mu mafaranga, umutekane w'ibiribwa, akazi, VUP n'imibereho myiza — imbonerahamwe imwe, nta kwiyandikisha.",
    "header.dataPoints": "Ibipimo by'Amakuru",
    "header.liveFromDb": "biva mu bubiko bw'amakuru",
    "header.loading": "birimo kuzurwa",
    "header.districts": "Uturere",
    "header.allMapped": "Rwanda yose yagaragara ku ikarita",
    "header.surveyVintage": "Umwaka w'Ubushakashatsi",

    // Ministerial portal button
    "portal.button": "Urubuga rw'Abaminisitiri",
    "portal.session": "Kwinjira kw'Abaminisitiri",
    "portal.sessionTitle": "Injira mu rubuga rw'abaminisitiri",

    // Filters
    "filters.aria": "Guhitamo no Gushakisha",
    "filters.searchLabel": "Shakisha ibipimo, uturere, intara",
    "filters.searchPlaceholder": "urugero: mobile money, ubukene, Kigali…",
    "filters.clearSearch": "Siba ishakiro",
    "filters.district": "Akarere",
    "filters.allDistricts": "Uturere twose",
    "filters.category": "Icyiciro cy'amakuru",
    "filters.allCategories": "Ibyiciro byose · {count} by'amakuru",
    "filters.of": "mu",
    "filters.dataPoints": "by'amakuru",
    "filters.scopeDistrict": "mu {district}",
    "filters.scopeAll": "mu turere twose",
    "filters.syncedAt": "byavuguruwe {time}",
    "filters.removeFilter": "Kuraho ihitamo: {label}",
    "filters.reset": "Subiza Ahabanze",
    "filters.refresh": "Vugurura",

    // Summary cards
    "cards.nationalMean": "Impuzanyingano mu turere twose",
    "cards.inclusionLabel": "Impuzanyingano · Kwinjira mu Mafaranga",
    "cards.inclusionSub": "{mean} · NST2 ≥ 80%",
    "cards.povertyLabel": "Impuzanyingano · Ubukene",
    "cards.povertySub": "{mean} · Umupaka < 30%",
    "cards.socialLabel": "Impuzanyingano · Imibereho Myiza",
    "cards.socialSub": "{mean} · Intego ≥ 60%",
    "cards.topInclusion": "Akarere ka Mbere mu Kwinjira mu Mafaranga",
    "cards.noInclusion": "Nta makuru yabonetse",
    "cards.highestPoverty": "Ubukene Burenza",
    "cards.noPoverty": "Nta makuru yabonetse",

    // Status / loading / errors
    "status.loading": "Amakuru y'ibipimo arimo kuzurwa…",
    "status.errorTitle": "Ntibyashobotse kuzana amakuru",
    "status.unexpected": "Habaye ikibazo kitateganyijwe.",
    "status.checkFastapi": "Reba ko serivisi ya FastAPI ihari kuri",
    "status.checkDb": "Emeza ko umugohe wa PostgreSQL {db} ukora",
    "status.tryAgain": "Gerageza",
    "status.refreshFailed": "Kuvugurura byanze:",
    "status.showingSnapshot": "erekana amakuru ya nyuma yageze neza.",
    "status.unknownError": "ikibazo kitazwi",
    "status.dismiss": "Funga iburira",
    "footer.about":
      "UpliftRwanda · NISR 2026 Big Data Hackathon — Track 2: Kwinjira mu Mafaranga no Kugabanya Ubukene. Amakuru yavanwe kuri EICV 7 / FinScope Rwanda.",
    "footer.records": "ibyanditswe {count}",

    // App-level states
    "app.noDataTitle": "Nta makuru y'uturere yabonetse",
    "app.noDataBody":
      "API yagize igisubizo, ariko amakuru yatanze nta murongo w'uturere ubamo. Abaminisitiri bashobora kuyakora kuri",
    "app.noDataTail": ", hanyuma uvugurure.",
    "app.reloadDataset": "Kongera Gufata Amakuru",
    "metrics.emptyHint":
      "Nta makuru ahuye n'ibyo wahitamo — gerageza ijambo rindi cyangwa ukoreshe 'Subiza Ahabanze'.",
  },
};

const LanguageContext = createContext(null);

export function LanguageProvider({ children }) {
  const [lang, setLang] = useState(() => {
    try {
      return window.localStorage.getItem(STORAGE_KEY) === "rw" ? "rw" : "en";
    } catch {
      return "en";
    }
  });

  useEffect(() => {
    try {
      window.localStorage.setItem(STORAGE_KEY, lang);
    } catch {
      /* private mode */
    }
    document.documentElement.lang = lang === "rw" ? "rw" : "en";
  }, [lang]);

  const t = useCallback(
    (key, vars) => {
      let text = DICTIONARY[lang]?.[key] ?? DICTIONARY.en[key] ?? key;
      if (vars) {
        for (const [name, value] of Object.entries(vars)) {
          text = text.replaceAll(`{${name}}`, String(value));
        }
      }
      return text;
    },
    [lang],
  );

  const value = useMemo(() => ({ lang, setLang, t }), [lang, t]);
  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>;
}

// eslint-disable-next-line react-refresh/only-export-components
export function useLanguage() {
  const ctx = useContext(LanguageContext);
  if (!ctx) throw new Error("useLanguage must be used inside <LanguageProvider>");
  return ctx;
}
