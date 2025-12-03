# backend/app/predict.py

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime
import re
import unicodedata

import numpy as np
import pandas as pd
import joblib
from sklearn.compose import TransformedTargetRegressor

from .schemas import (
    PredictRequest,
    ALLOWED_PROPERTY_TYPES,
    ALLOWED_STATES,
    ALLOWED_PROVINCES,
    PROPERTY_TYPE_MAP,
    STATE_MAP,
    PROVINCE_ALIASES,
)

BACKEND_DIR = Path(__file__).resolve().parents[1]
ARTIFACTS_DIR = BACKEND_DIR / "artifacts"
DATA_DIR = BACKEND_DIR / "data"

MODEL_PATH_PRIMARY = ARTIFACTS_DIR / "pipeline.joblib"
MODEL_PATH_FALLBACK = ARTIFACTS_DIR / "xgboost_log_model.pkl"
POSTAL_REF_PATH = DATA_DIR / "postal_code_ref.csv"

AMENITY_ALLOWED = {"yes", "no", "unknown"}

CAT_COLS = [
    "garden", "terrace", "swimming_pool",
    "postal_code", "property_type", "state", "province", "region",
]

REGION_MAP = {
    "ANTWERPEN": "Flanders",
    "OOST-VLAANDEREN": "Flanders",
    "WEST-VLAANDEREN": "Flanders",
    "LIMBURG": "Flanders",
    "VLAAMS-BRABANT": "Flanders",
    "WAALS-BRABANT": "Wallonia",
    "HENEGOUWEN": "Wallonia",
    "LUIK": "Wallonia",
    "LUXEMBURG": "Wallonia",
    "NAMEN": "Wallonia",
    "BRUSSEL": "Brussels",
}

NUMERIC_COLS = [
    "build_year", "facades", "living_area", "number_rooms",
    "house_age", "is_new_build", "is_recent", "is_old", "build_decade",
]

_pipeline: Optional[Any] = None
_expected_cols: List[str] = []
_postal_to_province: Dict[str, str] = {}


def _infer_expected_columns(p) -> List[str]:
    pre = p.named_steps["preprocess"]
    cols: List[str] = []
    for _, _, columns in pre.transformers_:
        if isinstance(columns, (list, tuple)):
            cols.extend(list(columns))

    seen = set()
    out: List[str] = []
    for c in cols:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out


def _pick_col(cols: List[str], keys: List[str]) -> Optional[str]:
    for c in cols:
        cl = c.lower()
        if any(k in cl for k in keys):
            return c
    return None


def _load_postal_lookup(path: Path) -> Dict[str, str]:
    if not path.exists():
        return {}

    for enc in ["utf-8-sig", "utf-8", "latin1", "cp1252"]:
        try:
            ref = pd.read_csv(path, dtype=str, sep=None, engine="python", encoding=enc)
            cols = [c.strip() for c in ref.columns]
            ref.columns = cols

            pc_col = _pick_col(cols, ["postcode", "zip", "zipcode", "postal"])
            pr_col = _pick_col(cols, ["provincie", "province", "prov"])
            if pc_col is None or pr_col is None:
                continue

            tmp = (
                ref[[pc_col, pr_col]]
                .dropna()
                .assign(
                    postcode=lambda d: d[pc_col].astype(str).str.extract(r"(\d{4})", expand=False),
                    province=lambda d: d[pr_col].astype(str).str.strip().str.upper(),
                )
                .dropna(subset=["postcode"])
                .assign(postcode=lambda d: d["postcode"].astype(str).str.zfill(4))
                .drop_duplicates(subset=["postcode"])
            )
            return dict(zip(tmp["postcode"].tolist(), tmp["province"].tolist()))
        except Exception:
            continue

    return {}


def load_artifacts() -> None:
    global _pipeline, _expected_cols, _postal_to_province

    if _pipeline is not None:
        return

    model_path = MODEL_PATH_PRIMARY if MODEL_PATH_PRIMARY.exists() else MODEL_PATH_FALLBACK
    if not model_path.exists():
        raise FileNotFoundError(f"Missing model. Expected {MODEL_PATH_PRIMARY} or {MODEL_PATH_FALLBACK}")

    _pipeline = joblib.load(model_path)
    _expected_cols = _infer_expected_columns(_pipeline)

    # Load postal lookup if available (only strictly needed when postal_code is provided)
    _postal_to_province = _load_postal_lookup(POSTAL_REF_PATH)


def _norm_key(s: str) -> str:
    s = s.strip().upper()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = re.sub(r"[\s\-_\.']", "", s)
    return s


def _normalize_province(raw: Optional[str]) -> Optional[str]:
    if raw is None:
        return None

    key = _norm_key(str(raw))
    canon = PROVINCE_ALIASES.get(key)

    if canon is None:
        for p in ALLOWED_PROVINCES:
            if _norm_key(p) == key:
                canon = p
                break

    return canon if canon in ALLOWED_PROVINCES else None


def _normalize_property_type(raw: Optional[str]) -> Optional[str]:
    if raw is None:
        return None
    s = str(raw).strip()
    if s == "":
        return None
    k = s.lower()

    canon = PROPERTY_TYPE_MAP.get(k)
    if canon is None:
        for pt in ALLOWED_PROPERTY_TYPES:
            if k == pt.lower():
                canon = pt
                break

    return canon if canon in ALLOWED_PROPERTY_TYPES else None


def _normalize_state(raw: Optional[str]) -> Optional[str]:
    if raw is None:
        return None
    s = str(raw).strip()
    if s == "":
        return None
    k = s.lower()

    canon = STATE_MAP.get(k)
    if canon is None:
        for st in ALLOWED_STATES:
            if k == st.lower():
                canon = st
                break

    return canon if canon in ALLOWED_STATES else None


def _normalize_amenity(raw: Optional[str]) -> Optional[str]:
    if raw is None:
        return None
    s = str(raw).strip().lower()
    if s == "":
        return None
    if s in {"1", "true", "y"}:
        s = "yes"
    if s in {"0", "false", "n"}:
        s = "no"
    return s if s in AMENITY_ALLOWED else None


def _parse_postal_code(raw: Any) -> Optional[str]:
    if raw is None:
        return None
    s = str(raw).strip()
    if s == "":
        return None

    digits = re.sub(r"\D+", "", s)
    if len(digits) != 4:
        return None

    num = int(digits)
    if num < 1000 or num > 9999:
        return None

    return digits


def _model_outputs_real_price(pipeline_obj: Any) -> bool:
    try:
        model_step = getattr(pipeline_obj, "named_steps", {}).get("model")
        return isinstance(model_step, TransformedTargetRegressor)
    except Exception:
        return False


def _one_line_warning(lines: List[str]) -> Optional[str]:
    clean = [x.strip() for x in lines if x and x.strip()]
    return None if not clean else " | ".join(clean)


def preprocess(req: PredictRequest) -> Tuple[pd.DataFrame, Optional[str]]:
    load_artifacts()
    assert _pipeline is not None

    data: Dict[str, Any] = req.model_dump()
    warnings: List[str] = []

    # Amenities: invalid -> warning + missing
    for col in ["garden", "terrace", "swimming_pool"]:
        raw = data.get(col)
        norm = _normalize_amenity(raw)
        if raw is not None and norm is None:
            warnings.append(f"{col} invalid; treated as missing.")
        data[col] = norm

    # property_type/state: invalid -> warning + missing (optional)
    raw_pt = data.get("property_type")
    pt = _normalize_property_type(raw_pt)
    if raw_pt is not None and pt is None:
        warnings.append("property_type not known; treated as missing.")
    data["property_type"] = pt

    raw_state = data.get("state")
    st = _normalize_state(raw_state)
    if raw_state is not None and st is None:
        warnings.append("state not known; treated as missing.")
    data["state"] = st

    # Province normalization
    raw_prov = data.get("province")
    prov_norm = _normalize_province(raw_prov)

    # Postal logic: either postal_code OR province must be provided (schemas already enforces at least one)
    pc_raw = data.get("postal_code")
    pc = _parse_postal_code(pc_raw)

    if pc_raw is None:
        # No postal_code: province must be usable (hard error if not recognized)
        if prov_norm is None:
            raise ValueError("You must provide either a valid postal_code or a recognizable province.")
        data["postal_code"] = None
        # Optional informational warning (not an error)
        warnings.append("postal_code not provided; using province only.")

    else:
        # Postal code provided: must be valid and exist in reference
        if pc is None:
            raise ValueError("postal_code must be exactly 4 digits (e.g., 9000).")

        if not _postal_to_province:
            raise RuntimeError("Postal reference not loaded; cannot validate postal_code.")

        if pc not in _postal_to_province:
            raise ValueError(f"postal_code {pc} not found in reference file.")

        prov_ref = _postal_to_province[pc]

        # If user also provided province, it must match reference (hard rule)
        if prov_norm is not None and prov_norm != prov_ref:
            raise ValueError(f"postal_code {pc} belongs to province {prov_ref}, but you sent {prov_norm}.")

        prov_norm = prov_ref
        data["postal_code"] = pc

    # Finalize province + region
    data["province"] = prov_norm
    data["region"] = REGION_MAP.get(prov_norm) if prov_norm else None

    # Derived features from build_year
    by = float(data["build_year"])
    current_year = datetime.now().year
    house_age = current_year - by
    if house_age < 0:
        house_age = np.nan

    data["house_age"] = house_age
    data["is_new_build"] = 1 if np.isfinite(house_age) and house_age <= 5 else np.nan
    data["is_recent"] = 1 if np.isfinite(house_age) and house_age <= 20 else np.nan
    data["is_old"] = 1 if np.isfinite(house_age) and house_age >= 50 else np.nan
    data["build_decade"] = int((by // 10) * 10)

    # Force categoricals to strings; missing -> "unknown"
    for c in CAT_COLS:
        if data.get(c) is None:
            data[c] = "unknown"

    # Build aligned input
    X = pd.DataFrame([data]).astype(object)
    X = X.reindex(columns=_expected_cols)
    X = X.mask(pd.isna(X), np.nan)

    # Enforce numeric conversions
    for c in NUMERIC_COLS:
        if c in X.columns:
            X[c] = pd.to_numeric(X[c], errors="coerce")

    return X, _one_line_warning(warnings)


def predict_text(req: PredictRequest) -> Tuple[str, Optional[str]]:
    load_artifacts()
    assert _pipeline is not None

    X, warning_line = preprocess(req)
    raw_pred = float(_pipeline.predict(X)[0])

    pred_price = raw_pred if _model_outputs_real_price(_pipeline) else float(np.expm1(raw_pred))
    pred_value = round(float(pred_price), 2)
    pred_text = f"€{pred_value:,.2f}"

    return pred_text, warning_line
