# UpliftRwanda API

Read-only analytical API for the NISR 2026 Big Data Hackathon (Track 2: financial
inclusion and poverty reduction), with a JWT-secured surface for the small set of
ministerial write operations. Python 3.14, FastAPI, SQLAlchemy 2 (PostgreSQL in
production, SQLite for offline testing).

## What it serves

- `GET /api/metrics` — 600 FinScope 2024 / EICV7 observations (20 indicators x 30 districts)
- `GET /api/cfsva/metrics` — 270 CFSVA 2024 rows (30 districts x 9 food-security indicators)
- `GET /api/districts/{name}/insights`, `GET /api/insights/national` — the ten-rule policy
  engine (poverty guardrail, vulnerability bands, mobile-money floors, inclusion and
  climate attention lines, savings/credit/social-protection floors)
- `GET /api/targets` — effective policy targets plus a per-key audit trail
- `POST /api/v1/simulate` — NST2-lever scenario projection (mobile money, formal credit,
  savings, social-protection coverage; climate shock treated as exogenous)

Analytical reads are public by design: a judge, an analyst, or a district officer can
click through everything without an account. Only the routes below accept writes:

- `POST /api/auth/login`, `GET /api/auth/me` (bcrypt, 5-failure window, short-lived HS256 token)
- `POST /api/admin/seed` — rebuild the calibrated dataset (destructive)
- `POST /api/admin/targets` — override or reset baseline flag-lines, `updated_by`/`updated_at` recorded
- `POST /api/admin/microdata` — upsert survey vintages on (district, indicator, year)

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
python3 test_api.py            # 51 end-to-end checks (sqlite): seeding, public reads,
                               # auth, rate limiting, targets, microdata, failure paths
```

Database backup/restore scripts live in `~/uplift-backend` (`db_backup.sh`,
`db_restore.sh`, round-tripped `database_backup.sql`).

## Data provenance

National anchors are published statistics (FinScope 2024: 92% formal inclusion,
77% transactional accounts and mobile money, 59% formal savings, 24% formal credit,
31% financially vulnerable; EICV7 2023/24: 27.4% poverty, 4.5% extreme poverty,
61.3% social-protection reach; CFSVA 2024: 83/16/1 food-security split, 30% stunting,
2.1% wasting). District dispersion around those anchors is modelled from urban/rural
and poverty-exposure gradients with deterministic jitter, then population-weighted
calibration snaps the national means back onto the anchors. It is a calibrated
synthetic panel, not FinScope microdata, and the UI says so where it counts.
