# streamlit_app/app.py
# Streamlit UI for the Immo Eliza Price Predictor (FastAPI backend)
#
# UI improvements requested:
# - Use fixed backend URL (hidden from the page)
# - Add a small welcome note
# - Show a subtle bottom-left indicator: "API: -> alive" when backend is reachable
# - Place the TE KOOP / À VENDRE banner image above the form
# - Keep prediction robust + always show € in the displayed output
# - Keep the page clean and “demo-ready”

from __future__ import annotations

import requests
import streamlit as st
from typing import Any, Dict, Optional

# Fixed backend URL (hidden; not displayed, not editable)
BACKEND_URL = "https://immo-eliza-deployment-vnhp.onrender.com"

# Image file for the banner (put it in your repo, e.g. streamlit_app/assets/tekoop_avendre.png)
# Update this path to match where you store the image.
BANNER_IMAGE_PATH = "streamlit_app/assets/tekoop_avendre.png"


# ---------------- Helpers ----------------
def normalize_base_url(url: str) -> str:
    return (url or "").strip().rstrip("/")


def check_api_alive(api_base_url: str) -> bool:
    """
    Lightweight health check.
    Your backend supports GET / -> alive (per your earlier UI notes).
    If your backend uses a different health path, change "/" accordingly.
    """
    base = normalize_base_url(api_base_url)
    try:
        r = requests.get(base + "/", timeout=6)
        return r.status_code < 400
    except Exception:
        return False


def call_predict(api_base_url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
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
    pred = result.get("prediction_text") or result.get("prediction") or result.get("pred_text")
    return None if pred is None else str(pred)


def format_price_eur(pred: Optional[str]) -> str:
    if pred is None:
        return "N/A"
    s = str(pred).strip()
    if not s:
        return "N/A"
    return s if s.startswith("€") else f"€{s}"


def render_api_badge(is_alive: bool) -> None:
    """
    Bottom-left API connection indicator.
    Uses fixed-position HTML anchored to the bottom-left of the page.
    """
    if is_alive:
        label = "API : → alive"
        bg = "#0E5A2A"   # dark green
        fg = "#FFFFFF"
        border = "#0B4A22"
    else:
        label = "API : → offline"
        bg = "#8A1F1F"   # dark red
        fg = "#FFFFFF"
        border = "#6F1919"

    st.markdown(
        f"""
        <style>
          .api-badge {{
            position: fixed;
            left: 18px;
            bottom: 18px;
            z-index: 1000;
            padding: 10px 12px;
            border-radius: 999px;
            background: {bg};
            color: {fg};
            border: 1px solid {border};
            font-size: 12px;
            font-weight: 600;
            letter-spacing: 0.2px;
            box-shadow: 0 6px 18px rgba(0,0,0,0.18);
          }}
        </style>
        <div class="api-badge">{label}</div>
        """,
        unsafe_allow_html=True,
    )


# ---------------- Static choices (keep in sync with backend) ----------------
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


# ---------------- Page layout ----------------
st.set_page_config(page_title="Immo Eliza Price Predictor", page_icon="🏠", layout="wide")

# Subtle page styling (keeps Streamlit clean but more “product-like”)
st.markdown(
    """
    <style>
      /* Make the content area a little tighter and nicer */
      .block-container { padding-top: 1.2rem; padding-bottom: 2.5rem; max-width: 1100px; }
      h1, h2, h3 { letter-spacing: -0.2px; }
      /* Reduce space under captions */
      [data-testid="stCaptionContainer"] { margin-top: -0.25rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

# Header + welcome note
st.title("Immo Eliza Price Predictor")
st.caption("Welcome to Immo-Eliza — a Belgian real estate price predictor for quick, demo-friendly estimates.")

# Banner image
# (If the image file is missing, we keep the app functional and show a placeholder note.)
try:
    st.image(BANNER_IMAGE_PATH, use_container_width=True)
except Exception:
    st.info(
        "Banner image not found. Add your TE KOOP / À VENDRE image at "
        f"`{BANNER_IMAGE_PATH}` (or update `BANNER_IMAGE_PATH`)."
    )

# API indicator (computed once per run; lightweight)
api_alive = check_api_alive(BACKEND_URL)
render_api_badge(api_alive)

# Main content layout
left, right = st.columns([1.15, 0.85], vertical_alignment="top")

with left:
    st.subheader("Property details")

    with st.container(border=True):
        st.markdown("**Required inputs**")
        build_year = st.number_input("Build year", min_value=1800, max_value=2025, value=1996, step=1)
        living_area = st.number_input("Living area (m²)", min_value=0, value=120, step=5)
        number_rooms = st.number_input("Number of rooms", min_value=0, value=3, step=1)
        facades = st.number_input("Facades", min_value=1, value=2, step=1)

    st.markdown("")

    with st.container(border=True):
        st.markdown("**Location (required: Postal code or Province)**")
        postal_code = st.text_input("Postal code (4 digits)", value="")
        province = st.selectbox("Province", options=PROVINCE_OPTIONS, index=0)

    st.markdown("")

    with st.container(border=True):
        st.markdown("**Optional characteristics**")
        property_type = st.selectbox("Property type", options=PROPERTY_TYPE_OPTIONS, index=0)
        state = st.selectbox("State", options=STATE_OPTIONS, index=0)

        c1, c2, c3 = st.columns(3)
        with c1:
            garden = st.selectbox("Garden", AMENITY_OPTIONS)
        with c2:
            terrace = st.selectbox("Terrace", AMENITY_OPTIONS)
        with c3:
            swimming_pool = st.selectbox("Swimming pool", AMENITY_OPTIONS)

with right:
    st.subheader("Prediction")

    # Validation
    postal_str = (postal_code or "").strip()
    postal_provided = bool(postal_str)
    postal_ok = is_valid_postal_code(postal_str)
    postal_invalid = postal_provided and (not postal_ok)

    province_ok = bool(province)
    location_ok = postal_ok or province_ok

    disable_predict = (not location_ok) or postal_invalid

    if not location_ok:
        st.warning("Enter a valid 4-digit postal code or select a province.")
    elif postal_invalid:
        st.warning("Postal code must be exactly 4 digits (e.g., 9000).")

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

    with st.container(border=True):
        st.markdown("Click the button to request a price estimate from the model.")

        predict_clicked = st.button("Predict price", type="primary", disabled=disable_predict, use_container_width=True)

        st.divider()

        if predict_clicked:
            try:
                with st.spinner("Calling the model..."):
                    result = call_predict(BACKEND_URL, payload)

                pred_raw = extract_prediction(result)
                price_display = format_price_eur(pred_raw)
                warning = result.get("warning")

                st.success("Prediction complete")
                st.metric("Predicted price", price_display)

                if warning:
                    st.info(str(warning))

            except Exception as e:
                st.error(str(e))
