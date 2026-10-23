"""RDHS 2025 pre-processing pipeline (additive — touches nothing existing).

Reads the NISR Rwanda Demographic & Health Survey 2025 recodes

    RWHR91FL.dta  household recode  (14,427 households · 560 clusters)
    RWBR91FL.dta  birth-recode      (child mortality + child anthropometry)

and produces a lightweight, weighted DISTRICT panel consumed by:

    seed_rdhs.py  ->  district_rdhs_metrics table (PostgreSQL)
    rdhs_api.py   ->  GET /api/rdhs/* public analytics endpoints
    RDHSPanel.jsx ->  Recharts dashboard section

All aggregations use hv005 / v005 survey weights (DHS /1000000 scaling).
District assignment: `shdistrict` inside the household recode (verified:
zero clusters map to more than one district, so BR can join districts
through hv001/v001 clusters).

Output
    db/rdhs/rdhs_2025_district_panel.json   canonical machine artifact
    db/rdhs/rdhs_2025_district_panel.csv    human checkpoint

Method notes (shown in API payloads and README):
    * wealth quintiles            hv270 (1=poorest..5=richest), weighted shares
    * electricity                 hv206 == 1
    * improved water (JM)         hv201 in {11,12,14,21,31,41,51,61,62,71}
    * improved sanitation (JM)    hv205 in {11,12,13,21,22,41}
    * bank account                hv247 == 1            (has bank account)
    * mobile financial services   hv263 == 1            (mobile phone used financial transactions)
    * mobile phone ownership      hv243a == 1
    * health insurance            any member slot sh21_* == 1
    * IMR/U5MR                    direct complete-exposure cohort method from
                                  birth history: deaths <12m among births born
                                  >=12 months before interview; deaths <60m
                                  among births born >=60 months before
                                  interview (conservative vs the official
                                  synthetic-cohort tables —documented).
    * stunting/wasting/underweight  BR children <60 months with valid WHO
                                  z-scores: hw70/hw71/hw72 < -2
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
DEFAULT_SOURCE_DIR = HERE.parent / "db" / "rdhs"
FALLBACK_SOURCE_DIR = Path("/home/it-eng/Downloads/Microdata/Microdata")
DEFAULT_OUT_DIR = HERE.parent / "db" / "rdhs"

SURVEY_YEAR = 2025
SURVEY_NAME = "RDHS 2025"

PROVINCE_OF_CODE = {
    1: "City of Kigali",
    2: "Southern Province",
    3: "Western Province",
    4: "Northern Province",
    5: "Eastern Province",
}

# District code (SHDISTRI label table verified against the file) -> title case
SHDISTRICT_LABELS_RAW = {
    11: "nyarugenge", 12: "gasabo", 13: "kicukiro",
    21: "nyanza", 22: "gisagara", 23: "nyaruguru", 24: "huye",
    25: "nyamagabe", 26: "ruhango", 27: "muhanga", 28: "kamonyi",
    31: "karongi", 32: "rutsiro", 33: "rubavu", 34: "nyabihu",
    35: "ngororero", 36: "rusizi", 37: "nyamasheke",
    41: "rulindo", 42: "gakenke", 43: "musanze", 44: "burera", 45: "gicumbi",
    51: "rwamagana", 52: "nyagatare", 53: "gatsibo", 54: "kayonza",
    55: "kirehe", 56: "ngoma", 57: "bugesera",
}
DISTRICTS = {code: name.title() for code, name in SHDISTRICT_LABELS_RAW.items()}

IMPROVED_WATER = {11, 12, 14, 21, 31, 41, 51, 61, 62, 71}
IMPROVED_SANITATION = {11, 12, 13, 21, 22, 41}


def _wmean(values: pd.Series, weights: pd.Series) -> float:
    """Weighted mean over finite values; NaN when no valid weights."""
    mask = np.isfinite(values) & np.isfinite(weights) & (weights > 0)
    v = values[mask]
    w = weights[mask]
    total = float(w.sum())
    if len(v) == 0 or total <= 0:
        return float("nan")
    return 100.0 * float(np.dot(v, w) / total)


def _weighted_quintiles(hv270: pd.Series, hv005: pd.Series) -> dict[str, float]:
    mask = np.isfinite(hv270) & hv270.isin([1, 2, 3, 4, 5]) & np.isfinite(hv005)
    w = hv005[mask]
    total = float(w.sum())
    if total <= 0:
        return {f"wealth_q{q}": float("nan") for q in range(1, 6)}
    shares: dict[str, float] = {}
    for q in range(1, 6):
        shares[f"wealth_q{q}"] = 100.0 * float(w[hv270[mask] == q].sum()) / total
    return shares


def _load_labels(path: Path) -> dict:
    from pandas.io.stata import StataReader
    with StataReader(path, convert_categoricals=False) as rdr:
        return rdr.value_labels()


def _find_district_labels(label_tables: dict) -> dict[int, str]:
    """Recover the 30 SHDISTRI code->name table from the file (self-verifying)."""
    for name, table in label_tables.items():
        if not isinstance(table, dict) or len(table) != 30:
            continue
        values = {str(v).strip().lower() for v in table.values()}
        if {"nyarugenge", "gasabo", "nyamagabe", "kirehe", "bugesera"}.issubset(values):
            return {int(k): str(v).strip().title() for k, v in table.items()}
    raise RuntimeError("shdistrict label table not found in RWHR91FL.dta")


def load_households(source: Path) -> pd.DataFrame:
    cols = [
        "hv001", "hv005", "hv024", "hv025", "shdistrict",
        "hv201", "hv205", "hv206", "hv243a", "hv247", "hv263", "hv270",
        # health-insurance member battery (17 slots)
        *[f"sh21_{i:02d}" for i in range(1, 18)],
    ]
    df = pd.read_stata(source, columns=cols, convert_categoricals=False)
    return df


def load_births(source: Path) -> pd.DataFrame:
    cols = ["v001", "v005", "v008", "b3", "b5", "b7", "hw1", "hw70", "hw71", "hw72"]
    df = pd.read_stata(source, columns=cols, convert_categoricals=False)
    return df


def build_panel(source_dir: Path, out_dir: Path | None = None) -> dict:
    hr_path = source_dir / "RWHR91FL.dta"
    br_path = source_dir / "RWBR91FL.dta"
    if not hr_path.exists() or not br_path.exists():
        alt = FALLBACK_SOURCE_DIR
        if (alt / "RWHR91FL.dta").exists() and (alt / "RWBR91FL.dta").exists():
            print(f"[preprocess] local copy missing in {source_dir}; using {alt}")
            source_dir = alt
        else:
            raise FileNotFoundError(
                "RDHS 2025 recodes not found (looked in "
                f"{source_dir} and {FALLBACK_SOURCE_DIR})"
            )

    hr_labels = _load_labels(hr_path)
    district_map = _find_district_labels(hr_labels)
    weird = set(district_map.values()) ^ set(DISTRICTS.values())
    if weird:
        raise RuntimeError(f"district label mismatch with verified map: {weird}")

    print("[preprocess] loading household recode (RWHR91FL)...")
    hh = load_households(hr_path)
    print(f"[preprocess] {len(hh):,} households")

    # sanity: shdistrict must exist & be one of the 30 codes
    hh = hh[hh["shdistrict"].isin(district_map)].copy()
    hh = hh.assign(
        district=hh["shdistrict"].map(district_map),
        province=hh["hv024"].map(PROVINCE_OF_CODE),
        w=hh["hv005"] / 1_000_000.0,
    )

    # insurance: any member slot coded yes
    insurance_cols = [c for c in hh.columns if c.startswith("sh21_")]
    hh["insured_any"] = hh[insurance_cols].eq(1).any(axis=1).astype(float)

    hh["improved_water"] = hh["hv201"].isin(IMPROVED_WATER).astype(float)
    hh["improved_sanitation"] = hh["hv205"].isin(IMPROVED_SANITATION).astype(float)
    hh["electric"] = hh["hv206"].eq(1).astype(float)
    hh["mobile_phone"] = hh["hv243a"].eq(1).astype(float)
    hh["bank_account"] = hh["hv247"].eq(1).astype(float)
    # hv263: households with a valid answer only (exclude blanks/missing)
    hv263_valid = hh["hv263"].isin([0, 1])
    hh["mobile_fintech"] = np.where(hv263_valid, hh["hv263"], np.nan)

    print("[preprocess] loading birth recode (RWBR91FL)...")
    br = load_births(br_path)
    print(f"[preprocess] {len(br):,} births")

    # cluster -> district (verified unambiguous)
    hub = hh.groupby("hv001")["district"].agg(["nunique", "first"])
    cluster_district = hub[hub["nunique"] == 1]["first"].to_dict()
    br["district"] = br["v001"].map(cluster_district)
    br = br[br["district"].notna()].copy()
    br["mw"] = br["v005"] / 1_000_000.0
    br["alive_and_recent_date"] = br["v008"] - br["b3"]

    rows: list[dict] = []
    for district, g in hh.groupby("district", sort=True):
        w = g["w"]
        panel: dict[str, float] = {
            "households": int(len(g)),
        }
        panel.update({
            "electricity_pct": _wmean(g["electric"], w),
            "improved_water_pct": _wmean(g["improved_water"], w),
            "improved_sanitation_pct": _wmean(g["improved_sanitation"], w),
            "bank_account_pct": _wmean(g["bank_account"], w),
            "mobile_fintech_pct": _wmean(g["mobile_fintech"], w),
            "mobile_phone_pct": _wmean(g["mobile_phone"], w),
            "insurance_pct": _wmean(g["insured_any"], w),
            "urban_pct": _wmean(np.where(g["hv025"] == 1, 1.0, 0.0), w),
        })
        panel.update(_weighted_quintiles(g["hv270"], w))
        rows.append({"district": district, "province": g["province"].iloc[0], **panel})

    hh_meta = {r["district"]: r for r in rows}

    # ---- birth-history indicators per district -------------------------------
    mortality_rows: dict[str, dict[str, float]] = {}
    anthro_rows: dict[str, dict[str, float]] = {}
    for district in DISTRICTS.values():
        gb = br[br["district"] == district]
        if len(gb) == 0:
            mortality_rows[district] = {"imr_per_1000": float("nan")}
            anthro_rows[district] = {}
            continue
        age_at_survey = gb["alive_and_recent_date"]
        # IMR: complete-exposure cohort — births >=12 months before interview
        cohort_imr = gb[age_at_survey >= 12]
        deaths_imr = cohort_imr[(cohort_imr["b5"] == 0) & (cohort_imr["b7"] < 12)]
        imr = (
            1000.0
            * float(deaths_imr["mw"].sum())
            / float(cohort_imr["mw"].sum())
            if float(cohort_imr["mw"].sum()) > 0
            else float("nan")
        )
        # U5MR: complete-exposure cohort — births >=60 months before interview
        cohort_u5 = gb[age_at_survey >= 60]
        deaths_u5 = cohort_u5[(cohort_u5["b5"] == 0) & (cohort_u5["b7"] < 60)]
        u5 = (
            1000.0
            * float(deaths_u5["mw"].sum())
            / float(cohort_u5["mw"].sum())
            if float(cohort_u5["mw"].sum()) > 0
            else float("nan")
        )
        mortality_rows[district] = {
            "imr_per_1000": imr,
            "u5mr_per_1000": u5,
            "births": int(len(gb)),
            "imr_births": int(len(cohort_imr)),
            "u5mr_births": int(len(cohort_u5)),
        }
        # anthropometry: children <60 months with valid WHO z-scores
        kids = gb[(gb["hw1"] >= 0) & (gb["hw1"] < 60)]
        has70 = kids[np.isfinite(kids["hw70"]) & (kids["hw70"] >= -6) & (kids["hw70"] <= 6)]
        has71 = kids[np.isfinite(kids["hw71"]) & (kids["hw71"] >= -6) & (kids["hw71"] <= 6)]
        has72 = kids[np.isfinite(kids["hw72"]) & (kids["hw72"] >= -6) & (kids["hw72"] <= 6)]
        anthro_rows[district] = {
            "stunting_pct": _wmean((has70["hw70"] < -2).astype(float), has70["mw"])
            if len(has70) else float("nan"),
            "underweight_pct": _wmean((has71["hw71"] < -2).astype(float), has71["mw"])
            if len(has71) else float("nan"),
            "wasting_pct": _wmean((has72["hw72"] < -2).astype(float), has72["mw"])
            if len(has72) else float("nan"),
            "children_measured": int(len(has70)),
        }

    for r in rows:
        d = r["district"]
        r.update(mortality_rows.get(d, {}))
        r.update(anthro_rows.get(d, {}))
        for key, val in list(r.items()):
            if isinstance(val, float) and not math.isfinite(val):
                r[key] = None
        for k in ("wealth_q1", "wealth_q2", "wealth_q3", "wealth_q4", "wealth_q5"):
            if r.get(k) is not None:
                r["wealth_p20_pct"] = r["wealth_q1"]
                r["wealth_p40_pct"] = round(r["wealth_q1"] + r["wealth_q2"], 1)
                r["wealth_p60p_pct"] = round(r["wealth_q3"] + r["wealth_q4"] + r["wealth_q5"], 1)
                break
        else:
            r["wealth_p20_pct"] = r["wealth_p40_pct"] = r["wealth_p60p_pct"] = None

    # ---- deterministic ordering + rounding -----------------------------------
    order = {name: idx for idx, name in enumerate(DISTRICTS.values())}
    rows.sort(key=lambda r: order[r["district"]])
    for r in rows:
        for key in sorted(r.keys()):
            if isinstance(r[key], float):
                r[key] = round(r[key], 1)

    # ---- population-weighted national summary (regions weights joined later) --
    payload = {
        "survey": SURVEY_NAME,
        "survey_year": SURVEY_YEAR,
        "sources": [hr_path.name, br_path.name],
        "method": {
            "weights": "hv005/v005 (DHS household & birth survey weights)",
            "district_assignment": "shdistrict in household recode; BR joined via hv001 clusters",
            "wealth": "hv270 shares (poorest..richest derived composite p20/p40/p60+)",
            "water_sanitation": "WHO/JMP improved-source groupings from hv201/hv205",
            "imr_u5mr": "direct complete-exposure cohort from birth history (documented, conservative vs synthetic-cohort official tables)",
            "anthropometry": "BR children <60m, WHO z-scores hw70/71/72 < -2",
        },
        "counts": {
            "districts": len(rows),
            "households": int(sum(r["households"] for r in rows)),
            "births": int(sum((r.get("births") or 0) for r in rows)),
        },
        "districts": rows,
    }
    if out_dir is None:
        out_dir = source_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "rdhs_2025_district_panel.json"
    json_path.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    csv_path = out_dir / "rdhs_2025_district_panel.csv"
    pd.DataFrame(rows).to_csv(csv_path, index=False)

    print(f"[preprocess] wrote {json_path}")
    print(f"[preprocess] wrote {csv_path}")
    house_counts = np.array([r["households"] or 1 for r in rows], dtype=float)
    p40 = np.array([r["wealth_p40_pct"] if r["wealth_p40_pct"] is not None else np.nan for r in rows], dtype=float)
    valid = np.isfinite(p40)
    national_p40 = float(np.dot(p40[valid], house_counts[valid]) / house_counts[valid].sum()) if valid.any() else float("nan")
    print(f"[preprocess] national bottom-40% wealth share ≈ {national_p40:.1f}% "
          f"(household-weighted sanity figure)")
    return payload


def main() -> int:
    ap = argparse.ArgumentParser(description="RDHS 2025 -> weighted district panel")
    ap.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE_DIR)
    ap.add_argument("--out-dir", type=Path, default=None)
    args = ap.parse_args()
    payload = build_panel(args.source_dir, args.out_dir or args.source_dir)
    counts = payload["counts"]
    print(f"[preprocess] districts={counts['districts']} households={counts['households']:,} births={counts['births']:,}")
    if counts["districts"] != 30:
        print("[preprocess] FATAL: expected 30 districts", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
