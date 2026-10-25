from pydantic import BaseModel, Field, HttpUrl, ConfigDict
from typing import Literal
from datetime import datetime

class CaseCreate(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    mode: Literal["pre_purchase", "post_purchase", "both"] = "pre_purchase"
    store_url: str | None = Field(default=None, max_length=2048)
    seller_handle: str | None = Field(default=None, max_length=240)
    product_name: str | None = Field(default=None, max_length=240)
    amount_minor_units: int | None = Field(default=None, ge=0)
    currency: str = Field(default="INR", min_length=3, max_length=3)
    notes: str | None = None

class CasePatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=240)
    mode: Literal["pre_purchase", "post_purchase", "both"] | None = None
    store_url: str | None = Field(default=None, max_length=2048)
    seller_handle: str | None = Field(default=None, max_length=240)
    product_name: str | None = Field(default=None, max_length=240)
    amount_minor_units: int | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    notes: str | None = None

class CaseOut(BaseModel):
    id: str; title: str; mode: str; status: str; store_url: str | None
    seller_handle: str | None; product_name: str | None; amount_minor_units: int | None
    currency: str; notes: str | None; created_at: datetime; updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

class FindingCreate(BaseModel):
    category: str = Field(min_length=1, max_length=80)
    claim: str = Field(min_length=1, max_length=4000)
    status: Literal["observed", "corroborated", "unverified", "contradicted", "inconclusive"] = "unverified"
    confidence: float = Field(default=0, ge=0, le=1)
    risk_weight: int = Field(default=0, ge=0, le=100)
    evidence_id: str | None = None
    source_url: str | None = None
    evidence_strength: Literal["weak", "moderate", "strong"] = "weak"
