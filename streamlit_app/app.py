# streamlit_app/app.py
# Public demo UI for Immo Eliza Price Predictor
# - Uses BACKEND_URL from Streamlit Secrets (preferred) or environment variables
# - Avoids editable backend URL (prevents users from accidentally using localhost)
# - Adds robust prediction field handling (prediction_text / prediction / pred_text)
# - Shows backend response details only when "Debug mode" is enabled

import os
from typing import Any, Dict, Optional

import requests
import streamlit as st

# ---------- Config ----------
APP_TITLE = "Immo Eliza Price Predictor"
DEFAULT_LOCAL_API = "http://localhost:8000"


def get_backend_url() -> str:
    """
    Resolve backend base URL in this order:
    1) Streamlit secrets: BACKEND_URL
    2) Environment variable: BACKEND_URL
    3) Fallback to localhost for local development
    """
    # st.secrets exists in all contexts; it behaves like a dict.
    # If no secrets are configured, get() simply returns the default value.
    return str(
        st.secrets.get(
            "BACKEND_URL",
            os.getenv("BACKEND_URL", DEFAULT_LOCAL_API),
        )
    ).strip()


def is_valid_postal_code(s: str) -> bool:
    s = (s or "").strip()
    return len(s) == 4 and s.isdigit()


def post_json(url: str, payload: Dict[str, Any], timeout: int = 30) -> Dict[str, Any]:
    r = requests.post(url, json=payload, timeout=timeout)

    # Try to parse JSON even for errors so we can display meaningful messages.
    try:
        data = r.json()
    except Exception:
        snippet = (r.text or "")[:300]
        raise RuntimeError(f"Non-JSON response (status {r.status_code}): {snippet}")

    if r.status_code >= 400:
        # Backend might return {"error": "..."} or a structured FastAPI error.
        msg = data.get("error") or data.get("detail") or str(data)
        raise ValueError(f"API error ({r.status_code}): {msg}")

    if not isinstance(data, dict):
        raise RuntimeError(f"Unexpected JSON shape: expected object, got {type(data).__name__}")

    return data


def call_predict(api_base_url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    api_base_url = api_base_url.rstrip("/")
    url = f"{api_base_url}/predict"
    return post_json(url, payload, timeout=30)


def extract_prediction_text(result: Dict[str, Any]) -> Optional[str]:
    """
    Support multiple backend response keys so UI doesn't show N/A due to naming mismatch.
    """
    pred = result.get("prediction_text") or result.get("prediction") or result.get("pred_text")
    if pred is None:
        return None
    # Normalize to string for UI safety.
    return str(pred)


# Keep these lists in sync with backend/app/schemas.py (allowed values).
PROPERTY_TYPE_OPTIONS = [
    "",  # allow "missing"
    "Apartment", "Residence", "Villa", "Ground", "Penthouse", "Duplex", "Mixed",
    "Studio", "Chalet", "Bungalow", "Cottage", "Master", "Loft", "Land", "Triplex",
    "Development", "Office", "Mansion", "Commercial", "Garage", "Student", "Business",
]

STATE_OPTIONS = [
    "",  # allow "missing"
    "New", "Normal", "Excellent", "To be renovated", "To renovate",
    "Fully renovated", "Under construction", "To restore", "To demolish",
]

PROVINCE_OPTIONS = [
    "",  # allow "missing"
    "ANTWERPEN",
    "OOST-VLAANDEREN",
    "WEST-VLAANDEREN",
    "LIMBURG",
    "VLAAMS-BRABANT",
    "WAALS-BRABANT",
    "HENEGOUWEN",
    "LUIK",
    "LUXEMBURG",
    "NAMEN",
    "BRUSSEL",
]

AMENITY_OPTIONS = ["", "yes", "no", "unknown"]


# ---------- UI ----------
st.set_page_config(page_title=APP_TITLE, page_icon="🏠", layout="centered")
st.title(APP_TITLE)
st.caption("Fill the required fields and get a predicted price. The model runs on a FastAPI backend.")

backend_url = get_backend_url()

with st.sidebar:
    st.subheader("Backend status")
    st.write("API base URL (configured):")
    st.code(backend_url, language="text")
    debug = st.toggle("Debug mode", value=False, help="Show payload and raw backend response")
    st.divider()
    st.write("Expected routes:")
    st.code("GET  /  -> alive\nPOST /predict -> prediction", language="text")
    st.write("Note: For public demos, the backend URL is not editable to avoid localhost issues.")

st.subheader("Required inputs")

# Required (by UI design)
build_year = st.number_input("Build year (required)", min_value=1800, max_value=2030, value=1996, step=1)
living_area = st.number_input("Living area (m²) (required)", min_value=0, value=120, step=5)
number_rooms = st.number_input("Number of rooms (required)", min_value=0, value=3, step=1)
facades = st.number_input("Facades (required)", min_value=1, value=2, step=1)

st.divider()
st.subheader("Location (required: Postal code/Province)")

postal_code = st.text_input("Postal code (4 digits) (required OR choose province)", value="")
province = st.selectbox("Province (required OR enter postal code)", options=PROVINCE_OPTIONS, index=0)

st.divider()
st.subheader("Optional inputs")

property_type = st.selectbox("Property type", options=PROPERTY_TYPE_OPTIONS, index=0)
state = st.selectbox("State", options=STATE_OPTIONS, index=0)

garden = st.selectbox("Garden", AMENITY_OPTIONS)
terrace = st.selectbox("Terrace", AMENITY_OPTIONS)
swimming_pool = st.selectbox("Swimming pool", AMENITY_OPTIONS)

# ---------- Validation ----------
postal_str = (postal_code or "").strip()
postal_provided = bool(postal_str)
postal_ok = is_valid_postal_code(postal_str)
postal_invalid = postal_provided and (not postal_ok)

province_ok = bool(province)
location_ok = postal_ok or province_ok

disable_predict = (not location_ok) or postal_invalid

if not location_ok:
    st.error("Location is required: enter a valid 4-digit postal code OR select a province.")
elif postal_invalid:
    st.error("Postal code must be exactly 4 digits (e.g., 9000).")

# ---------- Payload ----------
payload: Dict[str, Any] = {
    "build_year": int(build_year),
    "living_area": float(living_area),
    "number_rooms": int(number_rooms),
    "facades": int(facades),
    "postal_code": postal_str or None,
    "province": province or None,
    "property_type": property_type or None,
    "state": state or None,
    "garden": garden or None,
    "terrace": terrace or None,
    "swimming_pool": swimming_pool or None,
}

if debug:
    st.subheader("Debug")
    st.write("Payload:")
    st.json(payload)

st.divider()

col1, col2 = st.columns([1, 2])
with col1:
    predict_clicked = st.button("Predict price", type="primary", disabled=disable_predict)
with col2:
    if debug:
        st.write("Backend URL:")
        st.code(backend_url, language="text")

# ---------- Prediction ----------
if predict_clicked:
    try:
        with st.spinner("Calling the model..."):
            result = call_predict(backend_url, payload)

        pred_text = extract_prediction_text(result)
        warning = result.get("warning")

        if debug:
            st.write("Raw backend response:")
            st.json(result)

        st.success("Prediction complete")
        st.metric("Predicted price", pred_text or "N/A")

        if warning:
            st.warning(str(warning))

        if pred_text is None:
            st.info(
                "The backend response did not include a recognized prediction field "
                "(expected one of: prediction_text, prediction, pred_text). "
                "Enable Debug mode to inspect the raw response."
            )

    except Exception as e:
        if debug:
            st.exception(e)
        else:
            st.error(str(e))
