# UpliftRwanda

NISR 2026 Big Data Hackathon, Track 2 - financial inclusion and poverty reduction.

A public intelligence dashboard for all 30 Rwandan districts (870 calibrated
observations: 600 FinScope 2024 / EICV7 rows plus 270 CFSVA 2024 food-security
rows; ministers can also ingest newer vintages, e.g. the 2025 NISR Labour-Force
panel, which the engine resolves indicator-by-indicator instead of blending
years), a ten-rule policy engine with editable flag-lines, an NST2-lever
scenario simulator, and a JWT-secured Ministerial console for the write path.

The RDHS 2025 (Rwanda Demographic & Health Survey) microdata layer is the
third dataset: `RWHR91FL.dta` (household recode) and `RWBR91FL.dta` (birth
recode) are aggregated by a Python/Pandas pipeline into a household-weighted
district panel of living standards, financial inclusion, wealth distribution
and child mortality/nutrition — see "RDHS 2025 integration" below.

## Hackathon upgrade — four new modules

- **Module A — Labour Market Intelligence (NISR RLFS 2025)**: a 30-district
  calibrated labour panel (unemployment 12.4%, youth NEET 24.5%, LFPR 66.3%,
  14.3 pp LFPR gender gap) with gender/education/disability segment splits,
  urban-vs-rural structure and per-district profiles & ranks. The 2025 vintage
  also feeds the existing `/api/metrics` contract (600 → 750 rows).
  API: `GET /api/labour/indicators | /summary | /districts | /districts/{ref}`
  `| /disaggregation?dimension=gender|education|disability | /metrics`
  Seeder: `python3 seed_lfs.py --url $DATABASE_URL` · Tab: "Labour Market LFS 2025"
- **Module B — VUP Social-Protection Tracker (NST2)**: the five-pillar
  caseload architecture distributed across 30 districts to exact national
  totals (DS 131,500 · cPW 246,000 · ePW 158,500 · NSDS 47,200 · FS 88,600),
  poverty among beneficiaries ~41% (12.5 extreme / 28.5 moderate), 91%
  payment timeliness, SACCO 61% / MoMo 24% / cash 15% disbursement mix.
  API: `GET /api/vup/indicators | /summary | /districts | /districts/{ref} | /metrics`
  Seeder: `python3 seed_vup.py --url $DATABASE_URL` · Tab: "VUP Social Protection"
- **Module C — Inclusion & Opportunity Matchmaker (FinScope 2024 tiers)**:
  financial-health pyramid (10 healthy / 57 coping / 31 vulnerable / 3
  extreme), district credit-gap league, and an explainable rule-based
  matchmaker scoring a declared profile (age, gender, occupation, goal,
  phone, SACCO membership, district) against a 12-product stack (Ejo Heza,
  Umurenge SACCO, MoMo nano-loans, VUP DS/cPW/ePW/NSDS/FS, BDF, Duterimbere,
  Smart Nkunganire, AFA value chains, VSLA Ibimina) with cited evidence.
  API: `GET /api/matchmaker/catalog`, `POST /api/matchmaker/recommendations`,
  `GET /api/inclusion/summary | /districts` · Tab: "Inclusion & Matchmaker"
- **Module D — Executive Policy Brief Generator**: one-click boardroom PDF
  (reportlab) and tidy CSV for any district or the national view, assembling
  headline economics (FinScope/EICV7), labour, VUP, CFSVA and RDHS sections,
  automated verdicts from the live policy engine, and rule-based
  recommended interventions — each row names its survey source and reference.
  API: `GET /api/brief/national`, `GET /api/brief/{district}.pdf | .csv`

## Two surfaces, one principle

The analytics layer is open to everyone - no sign-in, no paywall between a
judge and the evidence. Write access (reseed, baseline-target changes, survey
uploads) sits behind bcrypt credentials and short-lived HS256 tokens issued
by the Ministerial Portal in the header.

- 870 observations: FinScope 2024 (transactional accounts 77%, mobile money 77%,
  formal inclusion 92%, formal credit 24%, formal savings 59%), EICV7 2023/24
  (poverty 27.4%, extreme poverty 4.5%, social-protection reach 61.3%),
  CFSVA 2024 (83/16/1 food-security split, 30% stunting, 2.1% wasting)
- RDHS 2025 district panel: bank accounts, mobile-money/fintech use, health
  insurance, electricity/improved-water/improved-sanitation, hv270 wealth
  quintiles (bottom-40% share = NST2/Vision-2050 prosperity lens), IMR/U5MR
  from the birth history, and child stunting/underweight/wasting markers
- LFS 2025 + VUP panels (Modules A/B): see the section above
- Leaflet district map, filterable indicator table, national and per-district
  verdicts with the reasoning and thresholds shown, not hidden
- RDHS 2025 tab: Recharts comparison bar (13 indicators x 30 districts),
  wealth-quintile stack, financial-inclusion vs prosperity-sharing scatter
  with a live correlation read, and a mortality/nutrition league table —
  filterable by Province and District, consistent with the map selection
- Scenario API quantifies what NST2 levers move which outcomes, with
  uncertainty bands derived from the data itself
- District panel is calibrated synthetic data anchored to the published
  national statistics above; the dashboard labels it as such. FinScope
  microdata is not redistributable, so this is the reproducible stand-in.

## Layout

    uplift-backend/    FastAPI app, policy engine, seeders, tests (README inside)
    uplift-frontend/   React 19 + Vite + Tailwind v4 + Leaflet dashboard

## Run

    # backend
    cd uplift-backend
    uvicorn main:app --reload --host 127.0.0.1 --port 8000

    # frontend
    cd uplift-frontend
    npm install
    npm run dev              # http://localhost:5173

    # verification
    cd uplift-backend && venv/bin/python test_api.py
    cd uplift-backend && for t in test_api test_cfsva test_rdhs test_labour test_vup test_matchmaker test_brief test_sim; do venv/bin/python $t.py || break; done
    cd uplift-frontend && npm run lint && npm run build

    # production
    cd uplift-backend && ./start_prod.sh               # systemd unit: uplift-api.service
    cd uplift-frontend && npm run build && npx vite preview --port 4173

Ministerial demo credentials are in `uplift-backend/README.md` alongside the
environment variables that replace them in production.

## RDHS 2025 integration (Track 2 evidence chain)

How the raw NISR microdata became a lightweight, auditable dashboard layer —
every step is reproducible and every aggregate names its source column:

    RWHR91FL.dta (household recode)  ─┐
                                      ├─ preprocess_rdhs.py (Pandas)
    RWBR91FL.dta (birth recode)     ─┘
        │  estimates with DHS hv005/v005 survey weights (÷1,000,000 scaling)
        ▼
    db/rdhs/rdhs_2025_district_panel.json/.csv   ← 30 districts x 24 columns,
      committed to git (~23 KB) so judges don't redistribute the 41 MB .dta files
        │
        ▼  seed_rdhs.py
    district_rdhs_metrics (PostgreSQL)  ← appended to models.py, additive
        │
        ▼  rdhs_api.py (mounted in main.py)
    GET /api/rdhs/indicators · /districts · /districts/{ref} · /metrics
        │
        ▼  src/components/RDHSPanel.jsx (Recharts)
    "RDHS 2025 Living Standards" tab (filters: Province / District)

Indicator definitions (all weighted household shares unless noted):

| panel column              | RDHS source                                            |
| ------------------------- | ------------------------------------------------------ |
| `bank_account_pct`        | hv247 = 1 (has a bank account)                         |
| `mobile_fintech_pct`      | hv263 = 1 (phone used for financial transactions)      |
| `mobile_phone_pct`        | hv243a = 1                                             |
| `insurance_pct`           | any member across the SH21* health-insurance battery   |
| `electricity_pct`         | hv206 = 1                                              |
| `improved_water/sanitation`| hv201 / hv205 mapped to WHO/JMP improved groupings    |
| `wealth_q1..q5`           | hv270 quintile shares (p20/p40/p60+ derived cuts)      |
| `imr_per_1000`, `u5mr_per_1000` | direct complete-exposure birth-history cohort (conservative vs the official synthetic tables — documented) |
| `stunting/underweight/wasting_pct` | BR hw70/71/72 z-scores < -2 SD, children <60 months |

Why this matters for the track: `bank_account_pct` + `mobile_fintech_pct`
measure financial inclusion directly in official microdata, while
`wealth_p40_pct` (bottom-40% wealth share) is the prosperity-sharing lens of
NST2/Vision 2050 — the same two axes the policy engine already tracks from
FinScope/EICV7, now cross-validated in a third independent NISR survey
(national household-weighted RDHS 2025 means: bank 52.6%, fintech 74.1%,
insurance 89.7%, electricity 54.5%, IMR 39.0/1,000, stunting 27.5%).

Rebuild from raw microdata (after registering for RWHR91FL/RWBR91FL access):

    cd uplift-backend
    venv/bin/python preprocess_rdhs.py            # writes db/rdhs/rdhs_2025_district_panel.{json,csv}
    venv/bin/python seed_rdhs.py --url $DATABASE_URL

`main.py` auto-seeds every layer (FinScope/EICV7 calibration, CFSVA 2024,
RDHS 2025, LFS 2025, VUP 2025) at boot whenever the database is empty, so a
fresh clone serves the full dashboard immediately.

## Deploying to Vercel

- Frontend: `uplift-frontend` is a standard Vite app — import the repo in
  Vercel, set **Root Directory** to `uplift-frontend`, build `npm run build`,
  output `dist`, and set `VITE_API_URL` to the public API base URL. SPA
  deep-links use hash routing (`#rdhs`), so no rewrite rules are needed.
- API: FastAPI + PostgreSQL. Host it on any service that keeps a persistent
  Postgres connection (Railway/Fly/Render — `./start_prod.sh`), or point
  `DATABASE_URL` at a managed Postgres (Neon/Supabase). The frontend is
  read-only against a public API, so CORS is the only coupling.
- The RDHS layer needs no extra deploy step: the committed panel JSON seeds
  automatically at boot (or `python3 seed_rdhs.py --url $DATABASE_URL`).

## Policy targets: facts vs decisions

Measured statistics are facts and stay fixed. What ministers may adjust are
the derived flag-lines around them - the poverty guardrail, the vulnerability
flag/critical bands, the mobile-money floor, the inclusion and climate
attention lines, and the savings/credit/social-protection/extreme-poverty
floors. Overrides live in `national_targets` with author and timestamp, feed
every insights response live, and a one-call reset returns to the official
NISR-derived baseline. This separation is what makes the engine auditable
in front of NISR economists: every flag on screen names its threshold and
whether it is official or overridden.
