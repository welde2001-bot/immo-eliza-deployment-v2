# streamlit_app/app.py
# UI that calls the FastAPI backend (/predict)
# Improvements:
# - Backend URL is editable again (for you + testers)
# - Default comes from st.secrets["BACKEND_URL"] or env BACKEND_URL, else localhost
# - Quick buttons to switch between deployed and localhost
# - "Test backend" button that checks connectivity
# - More robust prediction key handling to avoid N/A
# - Optional debug output (payload + raw response)

import os
from typing import Any, Dict, Optional

import requests
import streamlit as st


DEFAULT_LOCAL_API = "http://localhost:8000"


def get_default_backend_url() -> str:
    """Prefer Streamlit secrets, then env var, then localhost."""
    return str(
        st.secrets.get(
            "BACKEND_URL",
            os.getenv("BACKEND_URL", DEFAULT_LOCAL_API),
        )
    ).strip()


def normalize_base_url(url: str) -> str:
    url = (url or "").strip()
    return url.rstrip("/")


def call_api(api_url: str, payload: dict) -> Dict[str, Any]:
    base = normalize_base_url(api_url)
    url = base + "/predict"
    r = requests.post(url, json=payload, timeout=30)

    try:
        data = r.json()
    except Exception:
        raise RuntimeError(f"Non-JSON response (status {r.status_code}): {r.text[:300]}")

    if r.status_code >= 400:
        msg = data.get("error") or data.get("detail") or str(data)
        raise ValueError(f"API error ({r.status_code}): {msg}")

    if not isinstance(data, dict):
        raise RuntimeError(f"Unexpected JSON type: {type(data).__name__}")

    return data


def test_backend(api_url: str) -> Optional[str]:
    """
    Light connectivity test.
    Prefers GET / (as your sidebar indicates). If it fails, returns error string.
    """
    base = normalize_base_url(api_url)
    try:
        r = requests.get(base + "/", timeout=10)
        # even if not JSON, a 200 is good enough to show server is reachable
        if r.status_code >= 400:
            return f"Backend reachable but returned HTTP {r.status_code} on GET /"
        return None
    except Exception as e:
        return str(e)


def is_valid_postal_code(s: str) -> bool:
    s = (s or "").strip()
    return len(s) == 4 and s.isdigit()


def extract_pred_text(result: Dict[str, Any]) -> Optional[str]:
    """Accept multiple possible key names so UI doesn't show N/A due to mismatch."""
    pred = result.get("prediction_text") or result.get("prediction") or result.get("pred_text")
    return None if pred is None else str(pred)


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
st.set_page_config(page_title="Immo Eliza Price Predictor", page_icon="🏠", layout="centered")
st.title("Immo Eliza Price Predictor")
st.caption("Fill the required fields and get a predicted price. The model runs on a FastAPI backend.")

default_backend = get_default_backend_url()

# persist editable backend URL across reruns
if "api_url" not in st.session_state:
    st.session_state["api_url"] = default_backend

with st.sidebar:
    st.subheader("Backend settings")

    # Editable input (your complaint fixed)
    st.session_state["api_url"] = st.text_input(
        "API base URL",
        value=st.session_state["api_url"],
        help="Example: https://your-backend.onrender.com or http://localhost:8000",
    )
    api_url = st.session_state["api_url"]

    colA, colB = st.columns(2)
    with colA:
        if st.button("Use deployed default"):
            st.session_state["api_url"] = default_backend
            st.rerun()
    with colB:
        if st.button("Use localhost"):
            st.session_state["api_url"] = DEFAULT_LOCAL_API
            st.rerun()

    if st.button("Test backend"):
        err = test_backend(api_url)
        if err is None:
            st.success("Backend reachable (GET / OK).")
        else:
            st.error(f"Backend test failed: {err}")

    debug = st.toggle("Debug mode", value=False)

    st.divider()
    st.write("Tip: local testing uses http://localhost:8000")
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

# Convert UI values to payload (send None for empties)
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
        st.code(payload, language="json")

# ---------- Predict ----------
if predict_clicked:
    try:
        with st.spinner("Calling the model..."):
            result = call_api(api_url, payload)

        pred_text = extract_pred_text(result)
        warning = result.get("warning")

        if debug:
            st.subheader("Debug output")
            st.write("API base URL:", normalize_base_url(api_url))
            st.write("Raw response:")
            st.json(result)

        st.success("Prediction complete")
        st.metric("Predicted price", pred_text or "N/A")

        if warning:
            st.warning(str(warning))

        if pred_text is None:
            st.info(
                "Backend response did not include 'prediction_text'. "
                "Enable Debug mode to view the raw response and confirm the key name."
            )

    except Exception as e:
        if debug:
            st.exception(e)
        else:
            st.error(str(e))
