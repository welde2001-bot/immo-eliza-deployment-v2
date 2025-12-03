# backend/app/schemas.py

from typing import Optional, Union
from pydantic import BaseModel, Field, field_validator, model_validator

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

    # Mandatory numerics
    living_area: float = Field(..., gt=0, le=500, examples=[120])
    number_rooms: int = Field(..., ge=0, le=12, examples=[3])
    facades: int = Field(..., ge=1, le=4, examples=[2])

    # Optional categoricals (handled softly in predict.py)
    garden: Optional[str] = Field(None, examples=["yes"])
    terrace: Optional[str] = Field(None, examples=["no"])
    swimming_pool: Optional[str] = Field(None, examples=["unknown"])

    # Location: at least one required
    postal_code: Optional[Union[str, int]] = Field(None, examples=["9000"])
    province: Optional[str] = Field(None, examples=["OOST-VLAANDEREN"])

    # Optional categoricals
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
        if v is None:
            return None
        s = str(v).strip()
        return None if s == "" else s

    @model_validator(mode="after")
    def require_location(self):
        # Must provide at least one: postal_code OR province
        if self.postal_code is None and self.province is None:
            raise ValueError("Either postal_code or province must be provided.")

        # If postal_code provided, basic format check (4 digits). Deeper validation happens in predict.py.
        if self.postal_code is not None:
            digits = "".join(ch for ch in str(self.postal_code).strip() if ch.isdigit())
            if len(digits) != 4:
                raise ValueError("postal_code must be exactly 4 digits (e.g., 9000).")

        return self


class PredictResponse(BaseModel):
    prediction_text: str
    warning: Optional[str] = None


class ErrorResponse(BaseModel):
    error: str
