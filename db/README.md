# UpliftRwanda — Database Snapshot

`database_snapshot.sql` is a plain `pg_dump` (no owners / privileges) of the calibrated
dataset that powers the dashboard, so judges can restore the exact data locally without
re-running any seeding.

## What is inside

| table                    | rows | meaning                                                        |
| ------------------------ | ---- | -------------------------------------------------------------- |
| `regions`                | 30   | all Rwandan districts (province, area type, population weight)  |
| `indicators`             | 20   | FinScope / EICV7 indicator catalog                              |
| `survey_metrics`         | 600  | FinScope 2024 + EICV7 VUP panel (20 indicators x 30 districts)  |
| `district_cfsva_metrics` | 30   | CFSVA 2024 wide rows — 9 statistics per district (= 270 values) |
| `national_targets`       | 0    | admin target overrides (defaults active when empty)             |

Total: **870 calibrated observations** (600 survey rows + 270 CFSVA district values).
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
Both seeders are reproducible — the same run always yields the same 870 observations —
so a restored snapshot and a fresh seed agree value-for-value.

Full-clone seeder route (equivalent result, manual):

```bash
cd uplift-backend
python3 seed_data.py
python3 seed_cfsva.py
```

Environment variables: see `uplift-backend/README.md` (`DB_*` / `DATABASE_URL`).
