# UpliftRwanda — Database Snapshot

`database_snapshot.sql` is a plain `pg_dump` (no owners / privileges) of the calibrated
dataset that powers the dashboard, so judges can restore the exact data locally without
re-running any seeding.

## What is inside

| table                    | rows | meaning                                                          |
| ------------------------ | ---- | ---------------------------------------------------------------- |
| `regions`                | 30   | all Rwandan districts (province, area type, population weight)    |
| `indicators`             | 25   | FinScope / EICV7 catalog + the five 2025 NISR Labour-Force codes  |
| `survey_metrics`         | 630  | 600 x 2024 FinScope/EICV7 + 30 x 2025 LFS urban vintages          |
| `district_cfsva_metrics` | 30   | CFSVA 2024 wide rows — 9 statistics per district (= 270 values)   |
| `district_rdhs_metrics`  | 30   | RDHS 2025 wide rows — living standards, financial inclusion, wealth quintiles, IMR/U5MR, stunting/wasting (NOT in the dump; auto-seeded at boot from `rdhs/rdhs_2025_district_panel.json`; run `python3 seed_rdhs.py` against any restored DB to fill it manually) |
| `national_targets`       | 0    | admin target overrides (defaults active when empty)               |

Total: **900 calibrated observations in the dump** (630 survey rows + 270 CFSVA district
values) plus the derived RDHS 2025 layer (30 wide rows = 510 `/api/rdhs/metrics`
values seeding automatically from the committed panel artifact). The
30 x 2025 rows are the NISR RLFS 2025 vintages (`employment_ratio`,
`unemployment_rate`, `lfpr`, `youth_unemployment`, `labor_underutilization`)
for the six urban districts (Gasabo, Kicukiro, Nyarugenge, Huye, Musanze,
Rubavu) — ingestible as one zero-rejection CSV (`nisr_rlfs_2025_microdata.csv`,
the exact file the Ministerial console demo uploads). Insights resolve them
latest-vintage-wins while the 2024 baseline stays authoritative elsewhere.
The dump contains survey data only — no credentials, tokens, or user records.

## Restore (PostgreSQL 14+)

```bash
createdb uplift_rwanda_db
psql -d uplift_rwanda_db -f db/database_snapshot.sql
```

Snapshot tables are restored without owners, so the restoring user owns them.
Then start the API from `uplift-backend/`:

```bash
uvicorn main:app --reload --port 8000
```

## Alternative: no snapshot needed

The backend now self-populates a **fresh, empty database at boot**: `main.py` detects
an empty `survey_metrics` table and runs the deterministic seeders
(`seed_data.py` → FinScope/EICV7 calibration, `seed_cfsva.py` → CFSVA 2024 layer).
Both seeders are reproducible — the same run always yields the same 2024 baseline
(600 observations + the Labour-Force catalog entries, 25 indicators). The
uploaded 2025 LFS vintages therefore come only from this snapshot; to reach
that state from a bare seed, upload `db/nisr_rlfs_2025_microdata.csv` through
the Ministerial console (30 rows, 0 rejected). Restored snapshot and bare-seed
agree value-for-value on every shared row.

Full-clone seeder route (equivalent result, manual):

```bash
cd uplift-backend
python3 seed_data.py
python3 seed_cfsva.py
```

Environment variables: see `uplift-backend/README.md` (`DB_*` / `DATABASE_URL`).

## Backup scripts

`scripts/db_backup.sh` dumps the live database to git-ignored
`db/database_backup.sql`; `scripts/db_restore.sh` restores `database_backup.sql`
when present, else this snapshot. Both read connection settings from
`uplift-backend/.env` (`DB_*`), falling back to peer-auth localhost defaults.
The submission artifact to share with judges is `db/database_snapshot.sql`.
