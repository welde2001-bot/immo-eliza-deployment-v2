# Real Estate Price Prediction (Belgium) — Immo Eliza 

Fast, reproducible ML inference service to estimate Belgian property prices using a trained model and reference data (postal code/province). This repository contains:

- **FastAPI backend** exposing a clean `/predict` endpoint for inference
- **Streamlit UI** for interactive predictions (dropdowns + input validation)
- **Docker + Docker Compose** to run both services consistently

---
---

## Table of contents
- [Description](#description)
- [Repository structure](#repository-structure)
- [Installation](#installation)
- [Usage](#usage)
- [API contract](#api-contract)
- [How it works](#how-it-works)
- [Troubleshooting](#troubleshooting)
- [Authors](#authors)

---

## Description

This service predicts a property price based on structured inputs such as build year, living area, number of rooms, facades, construction state, property type, and amenities. Location is enforced via **either** a postal code (validated against the reference file) **or** a province.

The backend loads pre-trained artifacts from `backend/artifacts/` and uses `backend/data/postal_code_ref.csv` to validate and derive location features.

---

## Repository Structure

```text
immo-eliza-deployment-v2/
├─ backend/
│  ├─ app/
│  │  ├─ __init__.py
│  │  ├─ app.py          # FastAPI entrypoint
│  │  ├─ predict.py     # artifacts load + preprocessing 
│  │  └─ schemas.py   # request/resp schemas + constants
│  ├─ artifacts/
│  │  ├─ pipeline.joblib
│  │  └─ xgboost_log_model.pkl
│  ├─ data/
│  │  └─ postal_code_ref.csv
│  └─ requirements.txt
│
├─ streamlit_app/
│  ├─ app.py      # Streamlit UI (calls backend /predict)
│  └─ requirements.txt
│
├─ docker/
│  ├─ backend.Dockerfile
│  └─ streamlit.Dockerfile
│
├─ docker-compose.yml
├─ .dockerignore
├─ .gitignore
└─ README.md
``` 

## Installation

### Option A — Local development (recommended)

**Backend**
```powershell
cd C:\Users\welde\Desktop\immo-eliza-deployment-v2\backend
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
pip install -r requirements.txt
``` 

**Streamlit**
``` 
cd C:\Users\welde\Desktop\immo-eliza-deployment-v2\streamlit_app
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
pip install -r requirements.txt
``` 

### Option B — Docker (production-like)

Requires Docker Desktop.
No local venv required.

**Usage**
1) Run backend (FastAPI)
``` 
cd C:\Users\welde\Desktop\immo-eliza-deployment-v2\backend
.\.venv\Scripts\Activate.ps1
uvicorn app.app:app --reload --port 8000
``` 
Health check:
``` 
http://localhost:8000/ → alive

``` 
2) Run Streamlit UI

```
cd C:\Users\welde\Desktop\immo-eliza-deployment-v2\streamlit_app
.\.venv\Scripts\Activate.ps1
streamlit run app.py --server.port 8501

```
Open:

http://localhost:8501

In the sidebar set:

API base URL: http://localhost:8000 (do not append /predict)

3) Run both with Docker Compose

```
cd C:\Users\welde\Desktop\immo-eliza-deployment-v2
docker compose up --build
```
**Open**:

Streamlit: http://localhost:8501

Backend: http://localhost:8000

**Stop**:
```
docker compose down
```
## API contract

### Endpoints
- `GET /` → `"alive"`
- `POST /predict` → prediction response

### Request schema (JSON)

Required fields:
- `build_year` (int)
- `living_area` (float > 0)
- `number_rooms` (int)
- `facades` (int)
- location: provide **either** `postal_code` (4 digits) **or** `province`

Optional fields:
- `property_type` (string; supported values in `backend/app/schemas.py`)
- `state` (string; supported values in `backend/app/schemas.py`)
- `garden`, `terrace`, `swimming_pool` (`"yes" | "no" | "unknown"`)

Example request:
```
{
  "build_year": 1996,
  "living_area": 120,
  "number_rooms": 3,
  "facades": 2,
  "postal_code": "9000",
  "province": "OOST-VLAANDEREN",
  "property_type": "Residence",
  "state": "Excellent",
  "garden": "yes",
  "terrace": "no",
  "swimming_pool": "unknown"
}
```
Response
Success:
```
{
  "prediction_text": "€410,802.38",
  "warning": null
}
```
Error (HTTP 400/422/500):

```

{
  "error": "Human-readable error message"
}
```

Example call (PowerShell)
```
$body = @{
  build_year   = 1996
  living_area  = 120
  number_rooms = 3
  facades      = 2
  postal_code  = "9000"
} | ConvertTo-Json

Invoke-RestMethod -Method Post `
  -Uri http://localhost:8000/predict `
  -ContentType "application/json" `
  -Body $body
  ```
  ## How it works

### 1) Loading artifacts
On startup, the backend loads the trained model artifacts from:
- `backend/artifacts/pipeline.joblib` (primary), or
- `backend/artifacts/xgboost_log_model.pkl` (fallback)

### 2) Input validation (hard rules)
Validation is enforced in `backend/app/schemas.py` and `backend/app/predict.py`:
- `living_area`, `facades`, `number_rooms` are mandatory
- location is mandatory: **postal_code OR province**
- if `postal_code` is provided, it must exist in `backend/data/postal_code_ref.csv`
- if both `postal_code` and `province` are provided, they must match

### 3) Feature engineering + normalization
`backend/app/predict.py`:
- normalizes text categoricals (property type, state, province)
- derives features from `build_year` (house age, decade, etc.)
- aligns columns to the model’s expected input schema

### 4) Inference
The pipeline produces a numeric prediction which is formatted into `prediction_text` (EUR string). Non-blocking issues (e.g., missing optional fields) are returned as a single-line `warning` when applicable.

## Troubleshooting

### Python versions used (important)
This repo uses **separate virtual environments** per component:

- **Backend (FastAPI / ML inference):** Python **3.14**   
  Venv path: `backend\.venv\`
- **Streamlit UI:** Python **3.13**  
  Venv path: `streamlit_app\.venv\`

If installs fail on Python 3.14 (common with some ML wheels), switch the backend to Python 3.13 for maximum compatibility.

#### Verify the active Python (must match the folder)
Backend terminal:
```powershell
cd C:\Users\welde\Desktop\immo-eliza-deployment-v2\backend
.\.venv\Scripts\Activate.ps1
python --version
python -c "import sys; print(sys.executable)"

```
## Authors

- Welederufeal Tadege