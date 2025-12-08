<p align="left">
  <a href="https://www.python.org/" target="_blank" rel="noopener noreferrer">
    <img src="streamlit_app/assets/python.png" width="32%" alt="Python" />
  </a>
  <a href="https://fastapi.tiangolo.com/" target="_blank" rel="noopener noreferrer">
    <img src="streamlit_app/assets/fastapi.png" width="32%" alt="FastAPI" />
  </a>
  <a href="https://streamlit.io/" target="_blank" rel="noopener noreferrer">
    <img src="streamlit_app/assets/streamlit.png" width="32%" alt="Streamlit" />
  </a>
</p>

# Real Estate Price Prediction (Belgium) — Immo Eliza

A reproducible ML inference service to estimate Belgian property prices using a trained model and reference data (postal code ↔ province). This repository contains:

- **FastAPI backend** exposing a `/predict` endpoint for inference + health/readiness endpoints
- **Streamlit UI** for interactive predictions (dropdowns + validation)

---

## 📑 Table of contents
- [Description](#description)
- [Repository structure](#repository-structure)
- [Requirements](#requirements)
- [Installation](#installation)
- [Run locally](#run-locally)
- [Streamlit UI](#streamlit-ui)
- [API usage](#api-usage)
- [How it works](#how-it-works)
- [Deployment](#deployment)
- [Contributors](#contributors)

---

<a id="description"></a>

## 🔎 Description

This service predicts a property price based on structured inputs such as build year, living area, rooms, facades, state, property type, and amenities. Location is required via **either** a postal code (validated against a reference file) **or** a province.

The backend loads pre-trained artifacts from `backend/artifacts/` and uses `backend/data/postal_code_ref.csv` to validate postal codes and infer/verify the canonical province used in feature engineering.

---

<a id="repository-structure"></a>

## 🗂️ Repository structure

```text
immo-eliza-deployment-v2/
├─ backend/
│  ├─ app/
│  │  ├─ __init__.py
│  │  ├─ app.py          # FastAPI entrypoint + health
│  │  ├─ predict.py   # artifact load + preprocess
│  │  └─ schemas.py   # request schema + constants
│  ├─ artifacts/
│  │  ├─ pipeline.joblib
│  │  └─ xgboost_log_model.pkl
│  ├─ data/
│  │  └─ postal_code_ref.csv
│  └─ requirements.txt
│
├─ streamlit_app/
│  ├─ app.py      # Streamlit UI (calls backend /predict)
│  ├─ requirements.txt
│  └─ assets/
│     ├─ immo-eliza.png  # sidebar image shown in the UI
│     ├─ ui.png          # screenshot of Streamlit UI
│     ├─ fastapi.png
│     ├─ streamlit.png
│     └─ python.png
├─ .gitignore
└─ README.md
```
<a id="requirements"></a>

## ✅ Requirements

### Python versions (important)

This repository uses **separate virtual environments** per component.

Practical recommendation: use a Python version with strong ML wheel support for your OS. If you see installation errors for `numpy`, `scikit-learn`, or `xgboost`, switch to a more widely supported Python version for the backend (this is common for ML stacks).

Example layout (Windows):
- Backend venv: `backend\.venv\`
- Streamlit venv: `streamlit_app\.venv\`

---

<a id="installation"></a>

## 🛠️ Installation

Install dependencies from each component’s `requirements.txt`.


### Backend (Python 3.14)

```powershell
cd backend
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
pip install -r requirements.txt
```

### Streamlit (Python 3.13)

```powershell
cd ..\streamlit_app
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
pip install -r requirements.txt
```

<a id="run-local"></a>

## 🧪 Run (local)


### 1) Run the backend (FastAPI)

Open a terminal:

Open a terminal:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
uvicorn app.app:app --reload --host 0.0.0.0 --port 8000

```

### 2) Run the Streamlit UI

Open a second terminal:

```powershell
cd streamlit_app
.\.venv\Scripts\Activate.ps1
streamlit run app.py --server.port 8501
```

<a id="streamlit-ui"></a>

## 🖥️ Streamlit UI


Run the Streamlit Application Locally
The Streamlit application (app.py) provides an interactive interface for predictions.

You can then access the application in your web browser, typically at http://localhost:8501

![Immo Eliza UI](streamlit_app/assets/ui.png)

Required fields:

- `build_year` (int)
- `living_area` (float > 0)
- `number_rooms` (int)
- `facades` (int)
- location: provide **either** `postal_code` (4 digits) **or** `province`

Optional fields:

- `property_type`, `state`,  `garden`,  `terrace`,  `swimming_pool`

After filling the form press predict price and the predicted price will be displayed according to the property details entered. Press reset button on the left side to reset the form and refill again to predict another property.

<a id="api-usage"></a>

## 🔌 API usage
### Request

POST /predict accepts JSON:
```powershell
{
  "build_year": 2000,
  "living_area": 100,
  "number_rooms": 2,
  "facades": 2,
  "postal_code": "9000",
  "province": null,
  "property_type": "Residence",
  "state": "Excellent",
  "garden": "yes",
  "terrace": "no",
  "swimming_pool": "unknown"
}
```
### Response (success)

```json
{
  "prediction_text": "€323,456.78",
  "warning": "postal_code not provided; using province only."
} 

```
### Quick test (curl)

```bash
curl -X POST "http://localhost:8000/predict" \
  -H "Content-Type: application/json" \
  -d '{"build_year":1996,"living_area":120,"number_rooms":3,"facades":2,"postal_code":"9000"}'
```
<a id="how-it-works"></a>

## ⚙️ How it works


### 1) Loading artifacts

On startup, the backend loads the trained model artifacts

### 2) Input validation (hard rules)

Validation is enforced in `backend/app/schemas.py` and `backend/app/predict.py`:

- `living_area`, `facades`, `number_rooms` are mandatory
- location is mandatory: **postal_code OR province**
- If `postal_code` is provided, it must exist in `backend/data/postal_code_ref.csv`
- If both `postal_code` and `province` are provided, they must match

### 3) Inference

The pipeline produces a numeric prediction which is formatted into prediction_text (EUR string). Non-blocking issues (e.g., unknown optional fields) return a single-line warning when applicable.

<a id="deployment"></a>

## ☁️ Deployment

This application is deployed using Streamlit Sharing and is accessible at: [immo-eliza-deployment](https://immo-eliza-deployment-v2-mm5chdvgf6maztxrhttbxu.streamlit.app/)

### If you want to contribute to the project, follow these steps:

1. Fork the repository and clone it to your local machine.
2. Create a new branch for your feature or bug fix.
3. Implement your changes.
4. Run tests to make sure everything works as expected.
5. Commit and push your changes.
6. Submit a pull request.


<a id="contributors"></a>

## 👥 Contributors

This project is part of AI & Data Science Bootcamp training at **</becode** and it was done by: 

- Welederufeal Tadege [LinkedIn](https://www.linkedin.com/in/) | [Github](https://github.com/welde2001-bot) 

Supervision: AI & Data Science coach Vanessa Rivera Quinones ***Vanessa Rivera Quinones***