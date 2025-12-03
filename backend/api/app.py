# api/app.py
# Minimal FastAPI app:
# - GET  /        -> "alive"
# - HEAD /        -> 200 for health checks
# - POST /predict -> prediction_text + warning (single line)

from contextlib import asynccontextmanager
from fastapi import FastAPI, Response
from fastapi.responses import JSONResponse

from api.schemas import PredictRequest, PredictResponse, ErrorResponse
from api.predict import load_artifacts, predict_text


@asynccontextmanager
async def lifespan(app: FastAPI):
    load_artifacts()
    yield


app = FastAPI(title="Immo Eliza Deployment API", lifespan=lifespan)


@app.get("/")
def root() -> str:
    return "alive"


@app.head("/")
def root_head() -> Response:
    return Response(status_code=200)


@app.post(
    "/predict",
    response_model=PredictResponse,
    responses={400: {"model": ErrorResponse}, 422: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
def predict_endpoint(req: PredictRequest):
    try:
        pred_text, warning_line = predict_text(req)
        return PredictResponse(prediction_text=pred_text, warning=warning_line)

    except ValueError as e:
        # Hard rule violations (postal reference mismatch, etc.)
        return JSONResponse(status_code=400, content=ErrorResponse(error=str(e)).model_dump())

    except Exception as e:
        return JSONResponse(status_code=500, content=ErrorResponse(error=f"Prediction failed: {e}").model_dump())
