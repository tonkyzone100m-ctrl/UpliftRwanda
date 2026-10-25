import logging
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import URL, create_engine, text
from sqlalchemy.exc import DBAPIError, SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from models import Base, NationalTarget, as_int, as_float

logger = logging.getLogger("uplift_api")

DB_NAME = os.getenv("DB_NAME", "uplift_rwanda_db")
DB_USER = os.getenv("DB_USER", "it-eng")
DB_PASSWORD = os.getenv("DB_PASSWORD", "uplift")  # local default; deployments override via env
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")


def build_database_url():
    explicit = os.getenv("DATABASE_URL")
    if explicit:
        return explicit
    return URL.create(
        "postgresql+psycopg2",
        username=DB_USER,
        password=DB_PASSWORD or None,
        host=DB_HOST,
        port=int(DB_PORT),
        database=DB_NAME,
    )


DATABASE_URL = build_database_url()

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,      # self-heals when Postgres drops/restarts connections
    pool_recycle=1800,       # retire connections older than 30 min
    # Postgres-only options (SQLite offline tests need connect_args={})
    connect_args={}
    if str(DATABASE_URL).startswith("sqlite")
    else {
        "connect_timeout": 5,          # fail fast if Postgres is not listening
        "application_name": "uplift_api",
    },
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """Request-scoped session; connections are always returned to the pool."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _ensure_seed_data(engine) -> None:
    """Populate an EMPTY database at boot so a fresh clone serves real data immediately.

    The deterministic seeders (FinScope/EICV7 profiling + CFSVA 2024 calibration)
    produce the same 870 observations every run. No-op once survey rows exist, and
    never invoked for sqlite (the test suites drive their own data).
    """
    if str(DATABASE_URL).startswith("sqlite"):
        return
    try:
        with engine.connect() as conn:
            existing = conn.execute(text("SELECT count(*) FROM survey_metrics")).scalar_one()
    except SQLAlchemyError:
        existing = 0  # survey_metrics not created yet on a brand-new database
    if existing:
        return
    logger.info("boot: empty database detected - seeding FinScope/EICV7 + CFSVA 2024 (deterministic)")
    import seed_cfsva
    import seed_data
    region_count, indicator_count, metric_count, _series = seed_data.seed(engine, drop_existing=False)
    logger.info(
        "boot: seed complete - %s regions / %s indicators / %s survey rows",
        region_count, indicator_count, metric_count,
    )
    try:
        seed_cfsva.seed_cfsva(engine)
        logger.info("boot: CFSVA 2024 layer seeded (30 districts x 9 statistics)")
    except Exception as exc:  # CFSVA layer failure must not fail FinScope seeding
        logger.warning("boot: CFSVA 2024 layer failed to seed: %s", exc)
    try:
        import seed_rdhs
        seed_rdhs.seed_rdhs(engine)
        logger.info("boot: RDHS 2025 layer seeded (30 districts, household + birth recodes)")
    except Exception as exc:  # RDHS layer failure must not fail core seeding
        logger.warning("boot: RDHS 2025 layer failed to seed: %s", exc)
    try:
        import seed_lfs
        seed_lfs.seed_lfs(engine)
        logger.info("boot: LFS 2025 labour layer seeded (30 districts + demographic segments)")
    except Exception as exc:  # LFS layer failure must not fail core seeding
        logger.warning("boot: LFS 2025 layer failed to seed: %s", exc)
    try:
        import seed_vup
        seed_vup.seed_vup(engine)
        logger.info("boot: VUP 2025 layer seeded (30 districts x 5 components)")
    except Exception as exc:  # VUP layer failure must not fail core seeding
        logger.warning("boot: VUP 2025 layer failed to seed: %s", exc)


try:
    Base.metadata.create_all(engine, tables=[NationalTarget.__table__])
    try:
        _ensure_seed_data(engine)
    except Exception as exc:  # seed failure must not block API startup
        logger.warning(
            "auto-seed skipped (%s); run any of the seed_*.py scripts manually.", exc
        )
    try:
        from seed_data import ensure_indicator_catalog
        lfs_added = ensure_indicator_catalog(engine)
        if lfs_added:
            logger.info("boot: registered %s Labour-Force-Survey catalog entries", lfs_added)
    except Exception as exc:
        logger.warning("boot: indicator catalog ensure skipped (%s)", exc)
    # Release the boot-time connection: SQLite test flows delete and recreate the
    # file at this path, and a pooled handle would keep serving the orphan inode
    # (reads succeed, writes raise readonly).
    engine.dispose()
except SQLAlchemyError:
    logger.warning("national_targets bootstrap skipped (database unreachable at boot).")

app = FastAPI(title="UpliftRwanda API", version="1.4")

_cors_origins = [
    origin.strip()
    for origin in os.getenv(
        "UPLIFT_CORS_ORIGINS",
        "https://uplift-frontend.vercel.app,"     # production frontend (Vercel)
        "https://uplift-frontend-rose.vercel.app," # deployed frontend (Vercel)
        "http://localhost:5173,http://127.0.0.1:5173,"
        "http://localhost:4173,http://127.0.0.1:4173,"
        "http://localhost:3000,http://127.0.0.1:3000",
    ).split(",")
    if origin.strip()
]
# Origins are an explicit allow-list (never "*"), so allow_credentials=True
# stays CORS-spec-compliant. The origin regex covers Vercel preview aliases
# (uplift-frontend-<hash>.vercel.app); extend via UPLIFT_CORS_ORIGINS if needed.
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from auth import auth_router  # noqa: E402
app.include_router(auth_router)

from admin_api import router as admin_router  # noqa: E402
app.include_router(admin_router)

from insights_api import router as insights_router  # noqa: E402
app.include_router(insights_router)

from simulation_api import router as simulation_router  # noqa: E402
app.include_router(simulation_router)

from cfsva_api import router as cfsva_router  # noqa: E402
app.include_router(cfsva_router)

from rdhs_api import router as rdhs_router  # noqa: E402
app.include_router(rdhs_router)

from labour_api import router as labour_router  # noqa: E402
app.include_router(labour_router)

from vup_api import router as vup_router  # noqa: E402
app.include_router(vup_router)

from matchmaker_api import router as matchmaker_router  # noqa: E402
app.include_router(matchmaker_router)

from brief_api import router as brief_router  # noqa: E402
app.include_router(brief_router)

def _db_hint(exc: DBAPIError) -> str:
    message = str(getattr(exc, "orig", exc)).lower()
    if "no password supplied" in message or "password authentication failed" in message:
        return "PostgreSQL rejected the credentials. Export DB_PASSWORD or fix DATABASE_URL."
    if "could not connect" in message or "connection refused" in message:
        return "PostgreSQL is not reachable. Start the database service first."
    if "does not exist" in message:
        return "Check that DB_NAME is correct and the database is seeded."
    return "Check DATABASE_URL / DB_* environment variables."


@app.exception_handler(DBAPIError)
async def database_error_handler(request: Request, exc: DBAPIError):
    orig = getattr(exc, "orig", exc)
    logger.error("Database error on %s %s: %s", request.method, request.url.path, orig, exc_info=True)
    return JSONResponse(
        status_code=503,
        content={
            "status": "error",
            "code": "database_unavailable",
            "detail": "The analytics database is unreachable or misconfigured.",
            "hint": _db_hint(exc),
            "path": request.url.path,
        },
    )


@app.exception_handler(SQLAlchemyError)
async def database_generic_handler(request: Request, exc: SQLAlchemyError):
    logger.error("SQLAlchemy error on %s %s: %s", request.method, request.url.path, exc)
    return JSONResponse(
        status_code=500,
        content={
            "status": "error",
            "code": "database_query_failed",
            "detail": "A database query failed while processing the request.",
            "path": request.url.path,
        },
    )

@app.get("/")
def read_root():
    return {"message": "Welcome to the UpliftRwanda NISR Analytics API"}


@app.get("/api/health")
def health():
    """Liveness probe: reports whether the database is reachable."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected", "engine": engine.url.drivername}
    except DBAPIError as exc:
        logger.warning("Health check failed: %s", getattr(exc, "orig", exc))
        return JSONResponse(
            status_code=503,
            content={
                "status": "degraded",
                "database": "unreachable",
                "hint": _db_hint(exc),
            },
        )


@app.get("/api/metrics")
def get_survey_metrics(db: Session = Depends(get_db)):
    query = text("""
        SELECT r.province, r.district, r.area_type,
               i.indicator_code, i.indicator_name, i.category, i.unit,
               sm.survey_year, sm.value
        FROM survey_metrics sm
        JOIN regions r ON sm.region_id = r.id
        JOIN indicators i ON sm.indicator_id = i.id
        ORDER BY r.province, r.district, i.indicator_code, sm.survey_year DESC;
    """)
    rows = db.execute(query).fetchall()

    metrics = [{
        "province": row[0],
        "district": row[1],
        "area_type": row[2],
        "indicator_code": row[3],
        "indicator_name": row[4],
        "category": row[5],
        "unit": row[6],
        "survey_year": as_int(row[7]),
        "value": as_float(row[8]),
    } for row in rows]
    years = sorted({row["survey_year"] for row in metrics})
    count_by_year: dict[str, int] = {}
    for row in metrics:
        key = str(row["survey_year"])
        count_by_year[key] = count_by_year.get(key, 0) + 1

    return {
        "status": "success",
        "count": len(metrics),
        "years": years,
        "count_by_year": count_by_year,
        "data": metrics,
    }