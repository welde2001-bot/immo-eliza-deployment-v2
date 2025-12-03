# api/schemas.py
# Request/response schemas.
# Hard validation: build_year + numeric sanity limits.
# Normalization/warnings happen in api/predict.py.

from typing import Optional, Union
from pydantic import BaseModel, Field, field_validator

ALLOWED_PROPERTY_TYPES = {
    "Apartment", "Residence", "Villa", "Ground", "Penthouse", "Duplex", "Mixed",
    "Studio", "Chalet", "Bungalow", "Cottage", "Master", "Loft", "Land", "Triplex",
    "Development", "Office", "Mansion", "Commercial", "Garage", "Student", "Business",
}

ALLOWED_STATES = {
    "New", "Normal", "Excellent", "To be renovated", "To renovate",
    "Fully renovated", "Under construction", "To restore", "To demolish",
}

# Canonical labels used by your dataset (NL uppercase)
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

# Soft normalization helpers
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
    "needs renovation": "To be renovated",
    "renovated": "Fully renovated",
    "construction": "Under construction",
}

# FR + NL province aliases -> canonical NL uppercase
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


class PredictRequest(BaseModel):
    # Required + hard validation
    build_year: int = Field(..., ge=1800, le=2025, examples=[1996])

    # Numeric sanity checks (hard errors)
    living_area: Optional[float] = Field(None, gt=0, le=500, examples=[120])
    number_rooms: Optional[int] = Field(None, ge=0, le=12, examples=[3])
    facades: Optional[int] = Field(None, ge=1, le=6, examples=[2])

    # Optional categoricals (handled softly in predict.py)
    garden: Optional[str] = Field(None, examples=["yes"])
    terrace: Optional[str] = Field(None, examples=["no"])
    swimming_pool: Optional[str] = Field(None, examples=["unknown"])

    postal_code: Optional[Union[str, int]] = Field(None, examples=["9000"])
    province: Optional[str] = Field(None, examples=["OOST-VLAANDEREN"])
    property_type: Optional[str] = Field(None, examples=["Residence"])
    state: Optional[str] = Field(None, examples=["Excellent"])

    model_config = {"extra": "forbid"}

    @field_validator(
        "garden", "terrace", "swimming_pool", "postal_code",
        "province", "property_type", "state",
        mode="before",
    )
    @classmethod
    def empty_to_none(cls, v):
        # Convert empty strings to None so predict.py can warn + treat as missing
        if v is None:
            return None
        s = str(v).strip()
        return None if s == "" else s


class PredictResponse(BaseModel):
    # One price field for UI, one warning line for UI
    prediction_text: str                      # e.g. "€410,802.38"
    warning: Optional[str] = None             # one line or null


class ErrorResponse(BaseModel):
    error: str
