# streamlit_app/app.py
# Streamlit UI for the Immo Eliza Price Predictor (FastAPI backend)
#
# - Default backend URL is the deployed Render service
# - Backend URL is editable (for manual overrides), but no local/production toggling
# - Handles multiple possible prediction field names from the backend
# - Ensures the displayed prediction includes a euro symbol

import requests
import streamlit as st
from typing import Any, Dict, Optional

# Fixed default backend URL (your deployed FastAPI on Render)
BACKEND_URL = "https://immo-eliza-deployment-vnhp.onrender.com"

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


# --------- Helpers ---------
def normalize_base_url(url: str) -> str:
    """Trim whitespace and trailing slashes for consistent URL building."""
    return (url or "").strip().rstrip("/")


def call_predict(api_base_url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Call the FastAPI /predict endpoint and return the parsed JSON."""
    base = normalize_base_url(api_base_url)
    url = base + "/predict"

    resp = requests.post(url, json=payload, timeout=30)

    try:
        data = resp.json()
    except Exception:
        snippet = (resp.text or "")[:300]
        raise RuntimeError(f"Non-JSON response (HTTP {resp.status_code}): {snippet}")

    if resp.status_code >= 400:
        msg = data.get("error") or data.get("detail") or str(data)
        raise ValueError(f"API error (HTTP {resp.status_code}): {msg}")

    if not isinstance(data, dict):
        raise RuntimeError(f"Unexpected JSON shape: expected object, got {type(data).__name__}")

    return data


def is_valid_postal_code(s: str) -> bool:
    s = (s or "").strip()
    return len(s) == 4 and s.isdigit()


def extract_prediction(result: Dict[str, Any]) -> Optional[str]:
    """
    Try common field names so the UI is robust to small backend differences.
    Preferred is 'prediction_text'.
    """
    pred = (
        result.get("prediction_text")
        or result.get("prediction")
        or result.get("pred_text")
    )
    return None if pred is None else str(pred)


def format_price_eur(pred: Optional[str]) -> str:
    """
    Ensure the displayed prediction has a euro symbol.
    If pred already starts with €, keep it. Otherwise prepend €.
    """
    if pred is None:
        return "N/A"
    s = str(pred).strip()
    if not s:
        return "N/A"
    return s if s.startswith("€") else f"€{s}"


# --------- Page layout ---------
st.set_page_config(page_title="Immo Eliza Price Predictor", page_icon="🏠", layout="centered")
st.title("Immo Eliza Price Predictor")
st.caption("Fill the required fields and get a predicted price. The model runs on a FastAPI backend.")

# Persist backend URL across reruns but keep your fixed default
if "api_url" not in st.session_state:
    st.session_state["api_url"] = BACKEND_URL

with st.sidebar:
    st.subheader("Backend")
    st.session_state["api_url"] = st.text_input(
        "API base URL",
        value=st.session_state["api_url"],
        help="Default is the deployed backend URL. You can override it if needed.",
    )
    api_url = st.session_state["api_url"]

    debug = st.toggle("Debug mode", value=False)

    st.divider()
    st.write("Expected routes on the backend:")
    st.code("GET  /        -> alive\nPOST /predict -> prediction", language="text")

st.subheader("Required inputs")

# Required numeric fields
build_year = st.number_input("Build year (required)", min_value=1800, max_value=2025, value=1996, step=1)
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

# --------- Validation ---------
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

# --------- Payload construction ---------
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

st.divider()

col1, col2 = st.columns([1, 2])
with col1:
    predict_clicked = st.button("Predict price", type="primary", disabled=disable_predict)
with col2:
    if debug:
        st.write("Payload sent to backend:")
        st.code(payload, language="json")

# --------- Prediction ---------
if predict_clicked:
    try:
        with st.spinner("Calling the model..."):
            result = call_predict(api_url, payload)

        pred_raw = extract_prediction(result)
        price_display = format_price_eur(pred_raw)
        warning = result.get("warning")

        st.success("Prediction complete")
        st.metric("Predicted price", price_display)

        if warning:
            st.warning(str(warning))

        if debug:
            st.subheader("Raw backend response")
            st.json(result)

    except Exception as e:
        if debug:
            st.exception(e)
        else:
            st.error(str(e))
