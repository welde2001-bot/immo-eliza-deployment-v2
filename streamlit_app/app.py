# streamlit_app/app.py
# Immo Eliza Price Predictor — Streamlit UI (FastAPI backend)
#
# Purpose
# -------
# This Streamlit app collects property features, sends them to a FastAPI backend (POST /predict),
# and displays a price estimate. The UI uses a form so inputs are only "committed" when the user
# presses Predict (submit semantics).

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import requests
import streamlit as st

# =============================================================================
# App configuration
# =============================================================================

APP_VERSION = "0.1.0"
BACKEND_URL = "https://immo-eliza-deployment-vnhp.onrender.com"  # backend base URL (not shown in UI)

CURRENT_YEAR = date.today().year  # dynamic, avoids hardcoding 2025+

APP_DIR = Path(__file__).resolve().parent
ASSETS_DIR = APP_DIR / "assets"
SIDEBAR_HEADER_IMAGE_PATH = ASSETS_DIR / "Immo-eliza.png"

# =============================================================================
# UI options (keep aligned with backend schemas)
# =============================================================================

PROPERTY_TYPE_OPTIONS = [
    "",
    "Apartment", "Residence", "Villa", "Ground", "Penthouse", "Duplex", "Mixed",
    "Studio", "Chalet", "Bungalow", "Cottage", "Master", "Loft", "Land", "Triplex",
    "Development", "Office", "Mansion", "Commercial", "Garage", "Student", "Business",
]
STATE_OPTIONS = [
    "",
    "New", "Normal", "Excellent", "To be renovated", "To renovate",
    "Fully renovated", "Under construction", "To restore", "To demolish",
]
PROVINCE_OPTIONS = [
    "",
    "ANTWERPEN", "OOST-VLAANDEREN", "WEST-VLAANDEREN", "LIMBURG",
    "VLAAMS-BRABANT", "WAALS-BRABANT", "HENEGOUWEN", "LUIK",
    "LUXEMBURG", "NAMEN", "BRUSSEL",
]
AMENITY_OPTIONS = ["", "yes", "no", "unknown"]

# =============================================================================
# Session defaults (input state + last output)
# =============================================================================
# DEFAULTS holds form values. META_DEFAULTS holds last result/error to render the right panel.

DEFAULTS: Dict[str, Any] = {
    "build_year": 2000,
    "living_area": 100,
    "number_rooms": 1,
    "facades": 2,
    "postal_code": "",
    "province": "",
    "property_type": "",
    "state": "",
    "garden": "",
    "terrace": "",
    "swimming_pool": "",
}
META_DEFAULTS: Dict[str, Any] = {
    "last_result": None,
    "last_error_user": None,
    "last_error_debug": None,
    "last_local_note": None,
}

# =============================================================================
# Helpers: normalization, formatting, error parsing
# =============================================================================

def _normalize_base_url(url: str) -> str:
    """Trim whitespace and trailing slashes to prevent malformed URLs."""
    return (url or "").strip().rstrip("/")


def _digits4_or_none(raw: Any) -> Optional[str]:
    """
    Extract a 4-digit postal code from user input.
    Returns:
      - 'dddd' if exactly 4 digits found
      - None otherwise
    """
    s = "" if raw is None else str(raw).strip()
    if not s:
        return None
    digits = "".join(ch for ch in s if ch.isdigit())
    return digits if len(digits) == 4 else None


def _extract_prediction(result: Dict[str, Any]) -> Optional[str]:
    """Read prediction field from backend response (supports multiple key names)."""
    pred = result.get("prediction_text") or result.get("prediction") or result.get("pred_text")
    return None if pred is None else str(pred)


def _format_price_eur(pred: Optional[str]) -> str:
    """Format to €123,456.78 when numeric; otherwise return a safe string."""
    if not pred:
        return "N/A"
    s = str(pred).strip()
    if not s:
        return "N/A"

    raw = s.replace("€", "").strip().replace(" ", "")
    try:
        val = float(raw.replace(",", ""))
        return f"€{val:,.2f}"
    except Exception:
        return s if s.startswith("€") else f"€{s}"


def _compact_fastapi_422(detail: Any) -> str:
    """Convert FastAPI/Pydantic 422 detail payload into a short readable message."""
    if isinstance(detail, str):
        return detail
    if isinstance(detail, dict):
        return str(detail)
    if isinstance(detail, list):
        parts = []
        for item in detail[:6]:
            if isinstance(item, dict):
                loc = item.get("loc")
                msg = item.get("msg")
                if loc and msg:
                    loc_str = ".".join(str(x) for x in loc if x not in ("body",))
                    parts.append(f"{loc_str}: {msg}")
                else:
                    parts.append(str(item))
            else:
                parts.append(str(item))
        suffix = "" if len(detail) <= 6 else " …"
        return " | ".join(parts) + suffix
    return str(detail)


def _parse_backend_error_json(data: Any) -> str:
    """
    Extract an error message from JSON responses.
    Supported formats:
      - {"error": "..."}   (custom backend)
      - {"detail": [...]}  (FastAPI validation)
    """
    if isinstance(data, dict):
        err = data.get("error")
        if isinstance(err, str) and err.strip():
            return err.strip()
        if "detail" in data:
            return _compact_fastapi_422(data["detail"])
        return str(data)
    return str(data)

# =============================================================================
# API status badge 
# =============================================================================

@dataclass(frozen=True)
class ApiStatus:
    """Simple availability state for the UI badge."""
    state: str  # "online" | "warming" | "offline"


@st.cache_data(ttl=10, show_spinner=False)
def _api_status(api_base_url: str) -> ApiStatus:
    """
    Lightweight reachability probe.
    Tries a small set of endpoints to handle different deployments.
    """
    base = _normalize_base_url(api_base_url)
    for path in ["/health", "/live", "/openapi.json", "/docs", "/"]:
        try:
            r = requests.get(base + path, timeout=5, allow_redirects=True)
            if path == "/health" and r.status_code == 503:
                return ApiStatus("warming")
            if r.status_code < 400:
                return ApiStatus("online")
            if r.status_code == 503:
                return ApiStatus("warming")
        except Exception:
            continue
    return ApiStatus("offline")


def _render_bottom_left_api_indicator(status: ApiStatus) -> None:
    """Render a fixed-position API status badge (bottom-left)."""
    if status.state == "online":
        label, bg, border = "API : → alive", "#0E5A2A", "#0B4A22"
    elif status.state == "warming":
        label, bg, border = "API : → warming", "#8A6A14", "#6F5710"
    else:
        label, bg, border = "API : → offline", "#8A1F1F", "#6F1919"

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
            color: #FFFFFF;
            border: 1px solid {border};
            font-size: 12px;
            font-weight: 650;
            box-shadow: 0 6px 18px rgba(0,0,0,0.18);
          }}
        </style>
        <div class="api-badge">{label}</div>
        """,
        unsafe_allow_html=True,
    )

# =============================================================================
# Backend call (preserves backend error messages)
# =============================================================================

def _call_predict(api_base_url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Call POST /predict.

    Returns:
      - JSON dict on success

    Raises:
      - RuntimeError with:
          "User: ..."  (message safe to display)
          "Debug: ..." (technical details)
    """
    base = _normalize_base_url(api_base_url)
    url = base + "/predict"

    try:
        resp = requests.post(
            url,
            json=payload,
            timeout=30,
            headers={"Accept": "application/json", "Content-Type": "application/json"},
        )
    except requests.RequestException as e:
        raise RuntimeError(
            "User: The prediction service could not be reached. Please try again.\n"
            f"Debug: network error: {repr(e)}"
        )

    content_type = (resp.headers.get("content-type") or "").lower()

    # Handle HTTP errors and keep backend messages intact where possible.
    if resp.status_code >= 400:
        detail_for_user: Optional[str] = None
        debug_bits = [f"HTTP {resp.status_code}"]

        if "application/json" in content_type:
            try:
                detail_for_user = _parse_backend_error_json(resp.json())
            except Exception:
                detail_for_user = None
        else:
            snippet = (resp.text or "")[:300].replace("\n", " ").strip()
            detail_for_user = "Upstream returned a non-JSON error response."
            debug_bits.append(f"snippet={snippet[:140]}")

        if resp.status_code in (400, 422):
            user_msg = detail_for_user or "Invalid request."
        elif resp.status_code == 503:
            user_msg = detail_for_user or "The model is warming up. Please try again shortly."
        else:
            user_msg = detail_for_user or "The prediction service returned an error. Please try again."

        raise RuntimeError(f"User: {user_msg}\nDebug: {', '.join(debug_bits)}")

    # Defensive: success responses should be JSON.
    if "application/json" not in content_type:
        snippet = (resp.text or "")[:300].replace("\n", " ").strip()
        raise RuntimeError(
            "User: The prediction service returned an unexpected response format.\n"
            f"Debug: HTTP {resp.status_code}, content-type={content_type}, snippet={snippet}"
        )

    data = resp.json()
    if not isinstance(data, dict):
        raise RuntimeError(
            "User: The prediction service returned an unexpected JSON structure.\n"
            f"Debug: type={type(data).__name__}"
        )
    return data


def _split_user_debug(err: Exception) -> Tuple[str, str]:
    """Split raised errors into user-facing vs technical details."""
    s = str(err)
    user_msg = "The prediction service is currently unavailable. Please try again."
    debug_msg = s
    if "User:" in s:
        parts = s.split("Debug:", 1)
        user_part = parts[0].replace("User:", "").strip()
        user_msg = user_part or user_msg
        debug_msg = ("Debug:" + parts[1]).strip() if len(parts) > 1 else s
    return user_msg, debug_msg

# =============================================================================
# Payload construction
# =============================================================================

def _build_payload_after_submit() -> Tuple[Dict[str, Any], Optional[str], Optional[str]]:
    """
    Build the API payload from session_state values committed by form submission.

    Rules:
      - Require at least: valid 4-digit postal code OR province.
      - If postal code is present but invalid and province is set -> ignore postal code and proceed.
    """
    pc_raw = st.session_state.get("postal_code", "")
    prov_raw = (st.session_state.get("province") or "").strip()

    pc4 = _digits4_or_none(pc_raw)
    has_province = bool(prov_raw)

    user_error: Optional[str] = None
    local_note: Optional[str] = None

    if pc4 is None and not has_province:
        user_error = "Please provide a postal code (4 digits) or select a province."

    if pc_raw and pc4 is None and has_province:
        local_note = "Postal code ignored (invalid); using province."

    payload: Dict[str, Any] = {
        "build_year": int(st.session_state["build_year"]),
        "living_area": float(st.session_state["living_area"]),
        "number_rooms": int(st.session_state["number_rooms"]),
        "facades": int(st.session_state["facades"]),
        "postal_code": pc4,
        "province": prov_raw or None,
        "property_type": (st.session_state.get("property_type") or "").strip() or None,
        "state": (st.session_state.get("state") or "").strip() or None,
        "garden": (st.session_state.get("garden") or "").strip() or None,
        "terrace": (st.session_state.get("terrace") or "").strip() or None,
        "swimming_pool": (st.session_state.get("swimming_pool") or "").strip() or None,
    }
    return payload, user_error, local_note

# =============================================================================
# Session state lifecycle
# =============================================================================

def _init_state() -> None:
    """Initialize session_state keys once per browser session."""
    for k, v in DEFAULTS.items():
        st.session_state.setdefault(k, v)
    for k, v in META_DEFAULTS.items():
        st.session_state.setdefault(k, v)


def _reset_state() -> None:
    """Reset form inputs and clear previous prediction outputs."""
    for k, v in DEFAULTS.items():
        st.session_state[k] = v
    for k, v in META_DEFAULTS.items():
        st.session_state[k] = v

# =============================================================================
# Render app
# =============================================================================

st.set_page_config(page_title="Immo Eliza Price Predictor", page_icon="🏠", layout="wide")
_init_state()

# Fixed API badge (cached probe).
_render_bottom_left_api_indicator(_api_status(BACKEND_URL))

# Global styling (CSS injection for layout control).
st.markdown(
    """
    <style>
      .block-container { padding-top: 0.9rem; padding-bottom: 2.0rem; max-width: 1120px; }
      [data-testid="stAppViewContainer"] {
        background: radial-gradient(1200px 600px at 18% 0%, rgba(59,130,246,0.10), transparent 60%),
                    radial-gradient(900px 500px at 100% 10%, rgba(16,185,129,0.07), transparent 55%);
      }
      section[data-testid="stSidebar"] { position: fixed; top: 0; left: 0; height: 100vh; overflow: hidden; z-index: 999; }
      section[data-testid="stSidebar"] > div { height: 100vh; overflow: hidden; }
      [data-testid="stSidebarContent"] { height: 100vh; overflow: hidden; padding-bottom: 2.0rem; }

      div[data-testid="stVerticalBlockBorderWrapper"] > div {
        border-radius: 18px;
        border-color: rgba(0,0,0,0.08);
        box-shadow: 0 10px 28px rgba(0,0,0,0.06);
      }

      .stButton > button { border-radius: 14px; padding: 0.75rem 1rem; font-weight: 700; }
      .action-hint { font-size: 12px; opacity: 0.78; margin-top: -6px; margin-bottom: 6px; }

      .center-title { text-align: center; margin-top: 0.2rem; }
      .center-sub { text-align: center; opacity: 0.85; margin-top: -0.2rem; }

      .version-pill {
        display: inline-block;
        margin-top: 6px;
        padding: 3px 10px;
        border-radius: 999px;
        border: 1px solid rgba(0,0,0,0.10);
        background: rgba(255,255,255,0.85);
        font-size: 11px;
        font-weight: 750;
        opacity: 0.85;
      }
    </style>
    """,
    unsafe_allow_html=True,
)

# Sidebar: branding + explanation + reset.
with st.sidebar:
    if SIDEBAR_HEADER_IMAGE_PATH.exists():
        st.image(str(SIDEBAR_HEADER_IMAGE_PATH), use_container_width=True)

    st.markdown("### About this app")
    st.write(
        "This app provides a fast real estate price estimate based on key property details such as build year, location, "
        "property profile, and amenities. Complete the required fields, add optional details if you have them, then press "
        "Predict to view the estimated price."
    )

    st.markdown(f'<span class="version-pill">App v{APP_VERSION}</span>', unsafe_allow_html=True)

    if st.button("Reset form", use_container_width=True):
        _reset_state()
        st.rerun()

# Header.
st.markdown('<h2 class="center-title">🏠 Immo Eliza Price Predictor</h2>', unsafe_allow_html=True)
st.markdown(
    '<div class="center-sub">Enter the property details, then click Predict to generate a price estimate.</div>',
    unsafe_allow_html=True,
)

# =============================================================================
# Form-based interaction model
# - Editing widgets does not trigger predictions.
# - A prediction is made only when the user presses Predict (form submit).
# =============================================================================

with st.form("predict_form", clear_on_submit=False):

    st.markdown("### 🧾 Property details")
    left, right = st.columns([0.62, 0.38], vertical_alignment="top")

    # --- Left column: required + location ---
    with left:
        with st.container(border=True):
            st.markdown("**📐 Required details**")
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                st.number_input("Build year", min_value=1800, max_value=CURRENT_YEAR, step=1, key="build_year")
            with c2:
                st.number_input("Living area (m²)", min_value=0, step=5, key="living_area")
            with c3:
                st.number_input("Rooms", min_value=0, step=1, key="number_rooms")
            with c4:
                st.number_input("Facades", min_value=1, step=1, key="facades")

        with st.container(border=True):
            st.markdown("**📍 Location**")
            lc1, lc2 = st.columns([0.9, 1.1])
            with lc1:
                st.text_input(
                    "Postal code",
                    placeholder="e.g., 9000",
                    key="postal_code",
                    max_chars=4,
                    help="Enter a 4-digit Belgian postal code (digits only).",
                )
            with lc2:
                st.selectbox("Province", options=PROVINCE_OPTIONS, key="province")

            st.caption("Provide either a 4-digit postal code or a province.")

    # --- Right column: optional profile + amenities ---
    with right:
        with st.container(border=True):
            st.markdown("**🏡 Property profile**")
            st.selectbox("Property type", options=PROPERTY_TYPE_OPTIONS, key="property_type")
            st.selectbox("State", options=STATE_OPTIONS, key="state")

        with st.container(border=True):
            st.markdown("**✨ Amenities**")
            a1, a2, a3 = st.columns(3)
            with a1:
                st.selectbox("🌿 Garden", options=AMENITY_OPTIONS, key="garden")
            with a2:
                st.selectbox("🪟 Terrace", options=AMENITY_OPTIONS, key="terrace")
            with a3:
                st.selectbox("🏊 Pool", options=AMENITY_OPTIONS, key="swimming_pool")

    # --- Prediction: action + result in one panel ---
    with st.container(border=True):
        st.markdown("### 🔮 Prediction")
        st.markdown(
            '<div class="action-hint">Press Predict to compute the estimate. The result appears here.</div>',
            unsafe_allow_html=True,
        )

        action_col, result_col = st.columns([0.28, 0.72], vertical_alignment="top")

        with action_col:
            submitted = st.form_submit_button("Predict price", type="primary", use_container_width=True)

            if submitted:
                # Clear previous output so the right panel reflects the latest attempt.
                st.session_state["last_result"] = None
                st.session_state["last_error_user"] = None
                st.session_state["last_error_debug"] = None
                st.session_state["last_local_note"] = None

                payload, user_err, local_note = _build_payload_after_submit()
                if user_err:
                    st.session_state["last_error_user"] = user_err
                else:
                    st.session_state["last_local_note"] = local_note
                    try:
                        with st.spinner("Calling the model endpoint..."):
                            st.session_state["last_result"] = _call_predict(BACKEND_URL, payload)
                    except Exception as e:
                        u, d = _split_user_debug(e)
                        st.session_state["last_error_user"] = u
                        st.session_state["last_error_debug"] = d

        with result_col:
            # Local note (e.g., invalid postal ignored when province is set).
            if st.session_state.get("last_local_note"):
                st.caption(st.session_state["last_local_note"])

            # Error state (user-friendly + optional technical details).
            if st.session_state.get("last_error_user"):
                st.error(st.session_state["last_error_user"])
                if st.session_state.get("last_error_debug"):
                    with st.expander("Technical details", expanded=False):
                        st.code(st.session_state["last_error_debug"], language="text")

            # Success state (prediction + optional warning).
            elif st.session_state.get("last_result"):
                result: Dict[str, Any] = st.session_state["last_result"]
                price = _format_price_eur(_extract_prediction(result))

                st.success("Prediction complete")
                st.metric("Predicted price", price)

                warning = result.get("warning")
                if warning:
                    st.warning(str(warning))

            # Empty state.
            else:
                st.caption("No prediction yet. Click Predict to generate an estimate.")

        # Disclaimer near the decision point.
        with st.expander("Disclaimer (read before use)", expanded=False):
            st.write(
                "This estimate is indicative and depends on listing quality, data coverage, and market conditions. "
                "It is not a certified valuation and provides no certification for this price. "
                "The model was trained on Belgian “for sale” listings collected up to 14 Nov 2025 "
                "(about 15,000+ properties), so accuracy may drift as the market changes or for unusual properties."
            )
