# backend/app/schemas.py

"""
Pydantic schemas and shared constants for the prediction API.

Design goals:
- Enforce strict request shape (no unexpected fields).
- Apply lightweight, "hard" validation for core numeric ranges and minimal location rules.
- Leave deeper domain validation (e.g., postal_code existence, province matching) to predict.py,
  where reference data is available and better error messages can be produced.

Update:
- build_year is now validated against the *current year* at request time (not hard-coded to 2025).
"""

from datetime import date
from typing import Optional, Union

from pydantic import BaseModel, Field, field_validator, model_validator

# -------------------------
# Allowed canonical values (used for normalization and optional validation)
# -------------------------
ALLOWED_PROPERTY_TYPES = {
    "Apartment", "Residence", "Villa", "Ground", "Penthouse", "Duplex", "Mixed",
    "Studio", "Chalet", "Bungalow", "Cottage", "Master", "Loft", "Land", "Triplex",
    "Development", "Office", "Mansion", "Commercial", "Garage", "Student", "Business",
}

ALLOWED_STATES = {
    "New", "Normal", "Excellent", "To be renovated", "To renovate",
    "Fully renovated", "Under construction", "To restore", "To demolish",
}

ALLOWED_PROVINCES = {
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
}

# -------------------------
# Normalization maps (user-friendly input -> canonical backend value)
# -------------------------
PROPERTY_TYPE_MAP = {
    "apt": "Apartment",
    "apartment": "Apartment",
    "res": "Residence",
    "resid": "Residence",
    "residence": "Residence",
    "house": "Residence",
}

STATE_MAP = {
    "new": "New",
    "normal": "Normal",
    "excellent": "Excellent",
    "to be renovated": "To be renovated",
    "to renovate": "To renovate",
    "fully renovated": "Fully renovated",
    "under construction": "Under construction",
    "to restore": "To restore",
    "to demolish": "To demolish",
    # Common synonyms
    "needs renovation": "To be renovated",
    "renovated": "Fully renovated",
    "construction": "Under construction",
}

# Province aliases across NL/FR spellings and common variants.
# Keys are normalized upstream (see predict.py _norm_key).
PROVINCE_ALIASES = {
    # NL
    "ANTWERPEN": "ANTWERPEN",
    "OOSTVLAANDEREN": "OOST-VLAANDEREN",
    "WESTVLAANDEREN": "WEST-VLAANDEREN",
    "LIMBURG": "LIMBURG",
    "VLAAMSBRABANT": "VLAAMS-BRABANT",
    "WAALSBRABANT": "WAALS-BRABANT",
    "HENEGOUWEN": "HENEGOUWEN",
    "LUIK": "LUIK",
    "LUXEMBURG": "LUXEMBURG",
    "NAMEN": "NAMEN",
    "BRUSSEL": "BRUSSEL",
    # FR
    "ANVERS": "ANTWERPEN",
    "FLANDREORIENTALE": "OOST-VLAANDEREN",
    "FLANDREOCCIDENTALE": "WEST-VLAANDEREN",
    "BRABANTFLAMAND": "VLAAMS-BRABANT",
    "BRABANTWALLON": "WAALS-BRABANT",
    "HAINAUT": "HENEGOUWEN",
    "LIEGE": "LUIK",
    "LUXEMBOURG": "LUXEMBURG",
    "NAMUR": "NAMEN",
    "BRUXELLES": "BRUSSEL",
    # Brussels variants
    "BRUXELLESCAPITALE": "BRUSSEL",
    "REGIONDEBRUXELLESCAPITALE": "BRUSSEL",
    "REGIONBRUXELLESCAPITALE": "BRUSSEL",
}

# -------------------------
# Request/response models
# -------------------------
class PredictRequest(BaseModel):
    """
    Request payload for /predict.

    Notes:
    - Core numeric fields are validated here with strict ranges.
    - Categorical fields are optional and are normalized/validated more deeply in predict.py.
    - Location: at least one of postal_code or province must be provided.
      A basic 4-digit postal_code format check is handled here; existence checks happen in predict.py.
    - build_year: must not be in the future (validated against current year at request time).
    """

    # Required year: lower-bounded here; "not in future" enforced via validator below.
    build_year: int = Field(..., ge=1800, examples=[1996])

    # Mandatory numerics used by the model
    living_area: float = Field(..., gt=0, le=500, examples=[120])
    number_rooms: int = Field(..., ge=0, le=12, examples=[3])
    facades: int = Field(..., ge=1, le=4, examples=[2])

    # Optional features (soft-handled by predict.py)
    garden: Optional[str] = Field(None, examples=["yes"])
    terrace: Optional[str] = Field(None, examples=["no"])
    swimming_pool: Optional[str] = Field(None, examples=["unknown"])

    # Location: at least one required
    postal_code: Optional[Union[str, int]] = Field(None, examples=["9000"])
    province: Optional[str] = Field(None, examples=["OOST-VLAANDEREN"])

    # Optional categoricals
    property_type: Optional[str] = Field(None, examples=["Residence"])
    state: Optional[str] = Field(None, examples=["Excellent"])

    # Reject unknown fields to keep the API strict and predictable.
    model_config = {"extra": "forbid"}

    @field_validator(
        "garden", "terrace", "swimming_pool", "postal_code",
        "province", "property_type", "state",
        mode="before",
    )
    @classmethod
    def empty_to_none(cls, v):
        """
        Treat empty strings as missing values.
        This enables UIs to send "" for unselected fields without causing validation noise.
        """
        if v is None:
            return None
        s = str(v).strip()
        return None if s == "" else s

    @field_validator("build_year")
    @classmethod
    def build_year_not_in_future(cls, v: int) -> int:
        """
        Enforce build_year <= current year at validation time.
        This avoids hardcoding a fixed upper bound (e.g., 2025) that would become stale.
        """
        current_year = date.today().year
        if v > current_year:
            raise ValueError(f"build_year cannot be in the future (max {current_year}).")
        return v

    @model_validator(mode="after")
    def require_location(self):
        """
        Enforce minimal location policy:
        - at least one of postal_code or province must be provided
        - if postal_code is provided, it must contain exactly 4 digits
        Deeper domain checks (e.g., reference lookup and province matching) occur in predict.py.
        """
        if self.postal_code is None and self.province is None:
            raise ValueError("Either postal_code or province must be provided.")

        if self.postal_code is not None:
            digits = "".join(ch for ch in str(self.postal_code).strip() if ch.isdigit())
            if len(digits) != 4:
                raise ValueError("postal_code must be exactly 4 digits (e.g., 9000).")

        return self


class PredictResponse(BaseModel):
    """
    Successful prediction response.

    prediction_text:
      - UI-ready formatted string in EUR (e.g., "€123,456.78")
    warning:
      - optional one-line note when inputs were normalized or partially ignored
    """
    prediction_text: str
    warning: Optional[str] = None


class ErrorResponse(BaseModel):
    """
    Standard error envelope for business/domain errors (HTTP 400/500).
    The UI displays the 'error' string verbatim to keep backend messages intact.
    """
    error: str
