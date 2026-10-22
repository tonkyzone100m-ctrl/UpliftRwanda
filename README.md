# UpliftRwanda

NISR 2026 Big Data Hackathon, Track 2 - financial inclusion and poverty reduction.

A public intelligence dashboard for all 30 Rwandan districts (870 observations:
600 FinScope 2024 / EICV7 rows plus 270 CFSVA 2024 food-security rows), a
ten-rule policy engine with editable flag-lines, an NST2-lever scenario
simulator, and a JWT-secured Ministerial console for the write path.

## Two surfaces, one principle

The analytics layer is open to everyone - no sign-in, no paywall between a
judge and the evidence. Write access (reseed, baseline-target changes, survey
uploads) sits behind bcrypt credentials and short-lived HS256 tokens issued
by the Ministerial Portal in the header.

- 870 observations: FinScope 2024 (transactional accounts 77%, mobile money 77%,
  formal inclusion 92%, formal credit 24%, formal savings 59%), EICV7 2023/24
  (poverty 27.4%, extreme poverty 4.5%, social-protection reach 61.3%),
  CFSVA 2024 (83/16/1 food-security split, 30% stunting, 2.1% wasting)
- Leaflet district map, filterable indicator table, national and per-district
  verdicts with the reasoning and thresholds shown, not hidden
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
    cd uplift-backend && python3 test_api.py        # 51 checks
    cd uplift-frontend && npm run lint && npm run build

Ministerial demo credentials are in `uplift-backend/README.md` alongside the
environment variables that replace them in production.

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
