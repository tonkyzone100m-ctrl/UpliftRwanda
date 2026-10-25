"""Predictive scenario simulation API (POST /api/v1/simulate).

Body:
    {
      "driver_deltas": {"mobile_money": 5.0, "formal_credit": 3.0, ...},
      "horizon_years": 2,
      "district": "Karongi"          // optional; omit for national
    }

Response: model card (coefficients, RMSE, priors), scenario framing, national
baseline -> year-by-year projected path with ±1.96·RMSE/√30 bands, and the same
trajectory for a targeted district when requested.

Registered from main.py:
    from simulation_api import router as simulation_router
    app.include_router(simulation_router)
"""

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from main import get_db
from simulation import DRIVERS, HORIZON_DEFAULT, run_scenario

router = APIRouter(prefix="/api/v1", tags=["simulation"])


class ScenarioRequest(BaseModel):
    driver_deltas: dict[str, float] = Field(default_factory=dict)
    horizon_years: int = Field(default=HORIZON_DEFAULT, ge=1, le=5)
    district: str | None = None


@router.post("/simulate")
def simulate(request: ScenarioRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    deltas = {c: request.driver_deltas.get(c, 0.0) for c in DRIVERS}
    truncation = {
        c: request.driver_deltas[c]
        for c in request.driver_deltas
        if c not in DRIVERS and request.driver_deltas.get(c) != 0.0
    }
    horizon = request.horizon_years
    payload, error = run_scenario(db, deltas, horizon, request.district)
    if error == "unknown_district":
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=404,
            content={"status": "error", "code": "district_not_found",
                     "detail": f"No district matching '{request.district}'."},
        )
    payload["warnings"] = []
    if truncation:
        payload["warnings"].append(
            f"Unknown driver keys ignored (supported: {', '.join(DRIVERS)}): "
            + ", ".join(sorted(truncation))
        )
    payload["status"] = "success"
    return payload


@router.get("/simulate/coefficients")
def simulate_coefficients(db: Session = Depends(get_db)):
    """Plain coefficient walk-through endpoint for judges (transparency)."""
    from simulation import fit_elasticities

    model = fit_elasticities(db)
    return {"status": "success", "model": model, "documented": True}
