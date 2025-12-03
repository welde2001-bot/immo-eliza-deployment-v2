# streamlit/app.py
# Simple UI that calls the FastAPI backend (/predict)

import requests
import streamlit as st

DEFAULT_API_URL = "https://immo-eliza-deployment-vnhp.onrender.com"  # your Render URL


def call_api(api_url: str, payload: dict) -> dict:
    url = api_url.rstrip("/") + "/predict"
    r = requests.post(url, json=payload, timeout=30)
    # If backend returns a FastAPI error, show it nicely
    try:
        data = r.json()
    except Exception:
        raise RuntimeError(f"Non-JSON response (status {r.status_code}): {r.text[:300]}")

    if r.status_code >= 400:
        # backend uses {"error": "..."}
        msg = data.get("error", str(data))
        raise ValueError(f"API error ({r.status_code}): {msg}")

    return data


st.set_page_config(page_title="Immo Eliza Price Predictor", page_icon="🏠", layout="centered")
st.title("Immo Eliza Price Predictor")
st.caption("Fill a few fields and get a predicted price. The model runs on a FastAPI backend.")

with st.sidebar:
    st.subheader("Backend settings")
    api_url = st.text_input("API base URL", value=DEFAULT_API_URL)
    st.write("Tip: keep this as your Render URL.")
    st.divider()
    st.write("Routes:")
    st.code("GET  /  -> alive\nPOST /predict -> prediction", language="text")

st.subheader("Property inputs")

# Required
build_year = st.number_input("Build year (required)", min_value=1800, max_value=2025, value=1996, step=1)

# Optional numerics
living_area = st.number_input("Living area (m²) (optional)", min_value=0, value=120, step=5)
number_rooms = st.number_input("Number of rooms (optional)", min_value=0, value=3, step=1)
facades = st.number_input("Facades (optional)", min_value=0, value=2, step=1)

st.divider()

# Optional categoricals
postal_code = st.text_input("Postal code (optional, 4 digits)", value="")
province = st.text_input("Province (optional, FR/NL accepted)", value="")
property_type = st.text_input("Property type (optional)", value="")
state = st.text_input("State (optional)", value="")

garden = st.selectbox("Garden (optional)", ["", "yes", "no", "unknown"])
terrace = st.selectbox("Terrace (optional)", ["", "yes", "no", "unknown"])
swimming_pool = st.selectbox("Swimming pool (optional)", ["", "yes", "no", "unknown"])

# Convert UI values to payload (send None for empties)
payload = {
    "build_year": int(build_year),
    "living_area": None if living_area == 0 else float(living_area),
    "number_rooms": None if number_rooms == 0 else int(number_rooms),
    "facades": None if facades == 0 else int(facades),
    "postal_code": postal_code.strip() or None,
    "province": province.strip() or None,
    "property_type": property_type.strip() or None,
    "state": state.strip() or None,
    "garden": garden or None,
    "terrace": terrace or None,
    "swimming_pool": swimming_pool or None,
}

st.divider()

col1, col2 = st.columns([1, 2])
with col1:
    predict_clicked = st.button("Predict price", type="primary")
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
