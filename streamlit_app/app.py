# streamlit_app/app.py
# UI that calls the FastAPI backend (/predict)

import os
import requests
import streamlit as st

DEFAULT_API_URL = st.secrets.get("BACKEND_URL", os.getenv("BACKEND_URL", "http://localhost:8000"))


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


def call_api(api_url: str, payload: dict) -> dict:
    url = api_url.rstrip("/") + "/predict"
    r = requests.post(url, json=payload, timeout=30)

    try:
        data = r.json()
    except Exception:
        raise RuntimeError(f"Non-JSON response (status {r.status_code}): {r.text[:300]}")

    if r.status_code >= 400:
        msg = data.get("error", str(data))
        raise ValueError(f"API error ({r.status_code}): {msg}")

    return data


def is_valid_postal_code(s: str) -> bool:
    s = (s or "").strip()
    return len(s) == 4 and s.isdigit()


st.set_page_config(page_title="Immo Eliza Price Predictor", page_icon="🏠", layout="centered")
st.title("Immo Eliza Price Predictor")
st.caption("Fill the required fields and get a predicted price. The model runs on a FastAPI backend.")

with st.sidebar:
    st.subheader("Backend settings")
    api_url = st.text_input("API base URL", value=DEFAULT_API_URL)
    st.write("Tip: for local testing use http://localhost:8000")
    st.divider()
    st.write("Routes:")
    st.code("GET  /  -> alive\nPOST /predict -> prediction", language="text")

st.subheader("Required inputs")

# Required
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
state = st.selectbox("State ", options=STATE_OPTIONS, index=0)

garden = st.selectbox("Garden ", ["", "yes", "no", "unknown"])
terrace = st.selectbox("Terrace ", ["", "yes", "no", "unknown"])
swimming_pool = st.selectbox("Swimming pool", ["", "yes", "no", "unknown"])

# Validation rules:
# - living_area, facades, number_rooms are required by construction (min_value prevents empty/0 for some)
# - Must provide either postal_code (valid 4 digits) OR province
postal_ok = is_valid_postal_code(postal_code)
province_ok = bool(province)

location_ok = postal_ok or province_ok

postal_str = (postal_code or "").strip()
postal_provided = bool(postal_str)
postal_invalid = postal_provided and (not postal_ok)

disable_predict = (not location_ok) or postal_invalid

if not location_ok:
    st.error("Location is required: enter a valid 4-digit postal code OR select a province.")
elif postal_provided and postal_invalid:
    st.error("Postal code must be exactly 4 digits (e.g., 9000).")

# Convert UI values to payload (send None for empties)
payload = {
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
    st.code(payload, language="json")

if predict_clicked:
    try:
        with st.spinner("Calling the model..."):
            result = call_api(api_url, payload)

        st.success("Prediction complete")
        st.metric("Predicted price", result.get("prediction_text", "N/A"))

        warning = result.get("warning")
        if warning:
            st.warning(warning)

    except Exception as e:
        st.error(str(e))
