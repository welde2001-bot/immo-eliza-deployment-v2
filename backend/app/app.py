# backend/app/app.py

"""
FastAPI application entrypoint for the Immo Eliza deployment API.

Key behaviors:
- Loads model artifacts at startup (lifespan hook) and exposes readiness state.
- Provides lightweight health endpoints:
    * /live   -> liveness (process is up)
    * /health -> readiness (artifacts loaded and model can serve predictions)
- Exposes /predict to generate a price estimate with consistent error handling.

Error handling policy:
- Validation / domain errors return HTTP 400 with a structured ErrorResponse.
- If artifacts fail to load at startup, /predict returns HTTP 503 (not ready) instead of 500.
- Unexpected runtime errors return HTTP 500 with ErrorResponse and are logged.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any, Dict

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from .schemas import PredictRequest, PredictResponse, ErrorResponse
from .predict import load_artifacts, predict_text

# Use Uvicorn's logger so messages appear in the standard server logs.
logger = logging.getLogger("uvicorn.error")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup/shutdown lifecycle hook.

    On startup:
    - Attempt to load all required artifacts (model pipeline, reference data).
    - Record readiness state on app.state so endpoints can respond appropriately.

    On shutdown:
    - Nothing to clean up explicitly (artifacts are in-memory).
    """
    app.state.ready = False
    app.state.startup_error = None

    try:
        load_artifacts()
        app.state.ready = True
        logger.info("Artifacts loaded successfully. API is ready.")
    except Exception as e:
        # Keep the process alive for debugging/monitoring, but mark it "not ready".
        app.state.ready = False
        app.state.startup_error = str(e)
        logger.exception("Artifact loading failed. API will stay alive but not ready.")

    yield


# Create the FastAPI app with the lifespan hook.
app = FastAPI(title="Immo Eliza Deployment API", lifespan=lifespan)

# -------------------------
# Health endpoints
# -------------------------
@app.get("/live")
def live() -> Dict[str, Any]:
    """
    Liveness probe: confirms the server process is running.
    This does not guarantee the model is ready.
    """
    return {"status": "alive"}


@app.get("/health")
def health() -> JSONResponse:
    """
    Readiness probe: indicates whether artifacts loaded successfully and
    the API is ready to serve predictions.

    Returns:
    - 200 if ready
    - 503 if still starting or startup failed (includes last startup error when available)
    """
    if getattr(app.state, "ready", False):
        return JSONResponse(status_code=200, content={"status": "ok", "ready": True})

    return JSONResponse(
        status_code=503,
        content={
            "status": "starting",
            "ready": False,
            "error": getattr(app.state, "startup_error", None),
        },
    )


@app.get("/")
def root() -> Dict[str, str]:
    """
    Backwards-compatible root endpoint.
    Kept for older clients; returns JSON so UIs can parse it consistently.
    """
    return {"status": "alive"}


# -------------------------
# Prediction endpoint
# -------------------------
@app.post(
    "/predict",
    response_model=PredictResponse,
    responses={
        400: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
)
def predict_endpoint(req: PredictRequest):
    """
    Run a prediction using the trained pipeline.

    Readiness behavior:
    - If artifacts are not loaded, return 503 (not ready) with a clear message.

    Error behavior:
    - ValueError is treated as a client/domain error (400) and returned verbatim in ErrorResponse.
    - Any unexpected exception returns 500 and is logged server-side.
    """
    if not getattr(app.state, "ready", False):
        return JSONResponse(
          status_code=503,
          content=ErrorResponse(error="Model is not ready (artifacts failed to load).").model_dump(),
        )

    try:
        pred_text, warning_line = predict_text(req)
        return PredictResponse(prediction_text=pred_text, warning=warning_line)

    except ValueError as e:
        return JSONResponse(status_code=400, content=ErrorResponse(error=str(e)).model_dump())

    except Exception as e:
        logger.exception("Prediction failed.")
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(error=f"Prediction failed: {e}").model_dump(),
        )
