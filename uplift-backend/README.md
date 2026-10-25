# UpliftRwanda API

Read-only analytical API for the NISR 2026 Big Data Hackathon (Track 2: financial
inclusion and poverty reduction), with a JWT-secured surface for the small set of
ministerial write operations. Python 3.14, FastAPI, SQLAlchemy 2 (PostgreSQL in
production, SQLite for offline testing).

## What it serves

- `GET /api/metrics` — FinScope 2024 / EICV7 observations (20 indicators x 30 districts) plus any
  uploaded newer vintages (e.g. the 2025 NISR Labour Force Survey panel); the payload reports
  `years` and per-year counts so multi-vintage ingestion stays auditable
- `GET /api/cfsva/metrics` — 270 CFSVA 2024 rows (30 districts x 9 food-security indicators)
- `GET /api/rdhs/indicators` — RDHS 2025 catalog (17 indicators) with population-weighted
  national means and the full estimation method block
- `GET /api/rdhs/districts` — RDHS 2025 wide district rows (living standards, financial
  inclusion, wealth quintiles, IMR/U5MR, child anthropometry); `/districts/{ref}` and
  `/metrics` follow the same contracts as the other layers
- `GET /api/districts/{name}/insights`, `GET /api/insights/national` — the ten-rule policy
  engine (poverty guardrail, vulnerability bands, mobile-money floors, inclusion and
  climate attention lines, savings/credit/social-protection floors)
- `GET /api/targets` — effective policy targets plus a per-key audit trail
- `POST /api/v1/simulate` — NST2-lever scenario projection (mobile money, formal credit,
  savings, social-protection coverage; climate shock treated as exogenous)
- `GET /api/labour/*` — NISR RLFS 2025 labour-market module: catalog + official
  national hierarchy, population-weighted summary/leagues, 30 wide district rows
  (gender / education / disability splits), per-district profiles with ranks,
  segment disaggregation, and `/metrics` rows in the standard contract (also adds a
  2025 vintage of 5 canonical codes to `/api/metrics`: 600 → 750 rows)
- `GET /api/vup/*` — VUP & social-protection module: five-pillar caseloads per
  district (exact national DS/cPW/ePW/NSDS/FS totals), poverty among beneficiaries
  (~41% anchor), payment timeliness, disbursement channels, per-district profiles
- `GET /api/matchmaker/*`, `GET /api/inclusion/*` — explainable rule-based
  matchmaker (`POST /api/matchmaker/recommendations`) scoring a declared profile
  against 12 real products with cited evidence; FinScope health-tier summary
- `GET /api/brief/national`, `GET /api/brief/{district}.pdf|.csv` — executive
  policy brief (reportlab PDF + tidy CSV) joining all five survey layers with
  live policy-engine verdicts and recommended interventions

Analytical reads are public by design: a judge, an analyst, or a district officer can
click through everything without an account. Only the routes below accept writes:

- `POST /api/auth/login`, `GET /api/auth/me` (bcrypt, 5-failure window, short-lived HS256 token)
- `POST /api/admin/seed` — rebuild the calibrated dataset (destructive)
- `POST /api/admin/targets` — override or reset baseline flag-lines, `updated_by`/`updated_at` recorded
- `POST /api/admin/microdata` — upsert survey vintages on (district, indicator, year);
  the bundled demo pack `../db/nisr_rlfs_2025_microdata.csv` ingests with 0 rejections

Admin errors return structured JSON (`code` + `detail`, 4xx with per-row reasons for
uploads); 5xx never exposes SQL or stack traces.

## Configuration

| Variable | Default | Notes |
|---|---|---|
| `DATABASE_URL` | from `DB_*` vars | PostgreSQL in prod; sqlite for tests |
| `DB_NAME` / `DB_USER` / `DB_PASSWORD` / `DB_HOST` / `DB_PORT` | `uplift_rwanda_db` / `it-eng` / `uplift` / `localhost` / `5432` | |
| `UPLIFT_ADMIN_USERNAME` | `nisr_admin` | |
| `UPLIFT_ADMIN_PASSWORD` | dev fallback `nisr-admin-2026` | logged as a warning when the fallback is live |
| `UPLIFT_ADMIN_PASSWORD_HASH` | - | bcrypt hash; wins over the plaintext variable |
| `UPLIFT_JWT_SECRET` | ephemeral random per boot | set a strong fixed value to keep sessions across restarts |
| `UPLIFT_TOKEN_TTL_MINUTES` | `120` | |
| `UPLIFT_CORS_ORIGINS` | localhost dev ports | comma-separated |

## Run, test, verify

```bash
uvicorn main:app --reload --host 127.0.0.1 --port 8000
python3 test_api.py            # 59 end-to-end checks (sqlite): seeding, public reads,
                               # auth, rate limiting, targets, microdata, vintage sync,
                               # failure paths
venv/bin/python test_api.py    # same suite on the packaged venv (canonical environment)
venv/bin/python test_cfsva.py  # CFSVA 2024 layer: co-existence + official provincial split
venv/bin/python test_rdhs.py   # RDHS 2025 layer: panel round-trip + no-break checks
venv/bin/python test_labour.py # LFS 2025 layer: calibration anchors + segment endpoints
venv/bin/python test_vup.py    # VUP layer: exact national totals + welfare anchors
venv/bin/python test_matchmaker.py  # catalog/POST validation + district context
venv/bin/python test_brief.py  # PDF/CSV endpoints + report assembly (needs reportlab)
```

## New-module seeders (LFS 2025, VUP 2025)

```bash
venv/bin/python seed_lfs.py --url $DATABASE_URL   # district_lfs_metrics + 780 segment rows
                                                  # + 150 survey_metrics rows (2025 vintage)
venv/bin/python seed_vup.py --url $DATABASE_URL   # district_vup_metrics (30 rows)
```

- `seed_lfs.py` — builds the LFS 2025 panel from published RLFS anchors
  (unemployment 12.4%, NEET 24.5%, LFPR gap 14.3pp) with archetype deviations +
  deterministic jitter + population-weighted calibration; `--dry-run` prints the
  national block without writing. Upserts the 2025 vintage of
  unemployment_rate/employment_ratio/lfpr/youth_unemployment/labor_underutilization
  into `survey_metrics` (all 30 districts).
- `seed_vup.py` — distributes exact NST2 component totals to districts via
  population x poverty-intensity weights with largest-remainder rounding;
  poverty among beneficiaries snaps to ~41% (12.5 extreme).

## RDHS 2025 pipeline (additive layer)

```bash
venv/bin/python preprocess_rdhs.py                # RWHR91FL + RWBR91FL -> ../db/rdhs/rdhs_2025_district_panel.{json,csv}
venv/bin/python seed_rdhs.py --url $DATABASE_URL  # panel -> district_rdhs_metrics (30 rows)
```

- `preprocess_rdhs.py` — Pandas pipeline over the raw `.dta` recodes; DHS
  `hv005`/`v005` weights, `shdistrict` for district assignment (zero clusters are
  ambiguous), deterministic ordering/rounding. Exits non-zero unless exactly 30
  districts carry data.
- `seed_rdhs.py` — creates `district_rdhs_metrics` (models.py addition, same
  `regions.id` keys as CFSVA), upserts idempotently, restores NULL-for-NULL microdata
  sparsity, and skips nothing existing. Works from the committed panel JSON, so the
  41 MB raw `.dta` files never need to ship with the repo (`db/rdhs/*.dta` is
  git-ignored; raw access via NISR/DHS registration).
- `rdhs_api.py` — the four public `GET /api/rdhs/*` routes; mounted in `main.py`
  after the CFSVA router; nothing pre-existing is modified.

Database backup/restore scripts live in `../db/scripts/` (`db_backup.sh`,
`db_restore.sh`); the round-tripped `database_backup.sql` is a git-ignored
working artifact — the submission artifact is `../db/database_snapshot.sql`.

## Production launch

```bash
./start_prod.sh                 # gates on UPLIFT_ADMIN_PASSWORD, serves HOST/PORT/WORKERS
sudo systemctl enable --now uplift-api.service   # after installing the unit template
```

The bundled `Procfile` (`web: ./start_prod.sh`) covers Procfile-based hosts such
as Render. `start_prod.sh` refuses to boot without an admin password, so the dev
fallback credential can never leak into a live serving. An empty `survey_metrics`
table self-seeds at boot; a restored `database_snapshot.sql` and a fresh seed
agree value-for-value (deterministic seeders).

## Data provenance

National anchors are published statistics (FinScope 2024: 92% formal inclusion,
77% transactional accounts and mobile money, 59% formal savings, 24% formal credit,
31% financially vulnerable; EICV7 2023/24: 27.4% poverty, 4.5% extreme poverty,
61.3% social-protection reach; CFSVA 2024: 83/16/1 food-security split, 30% stunting,
2.1% wasting). District dispersion around those anchors is modelled from urban/rural
and poverty-exposure gradients with deterministic jitter, then population-weighted
calibration snaps the national means back onto the anchors. It is a calibrated
synthetic panel, not FinScope microdata, and the UI says so where it counts.
