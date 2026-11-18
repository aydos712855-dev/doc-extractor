from __future__ import annotations

import re
from enum import Enum
from typing import Optional

from pydantic import BaseModel, field_validator, model_validator


class DocType(str, Enum):
    invoice = "invoice"
    commercial_offer = "commercial_offer"
    act = "act"
    unknown = "unknown"


class Currency(str, Enum):
    KZT = "KZT"
    USD = "USD"
    EUR = "EUR"


class LineItem(BaseModel):
    name: str
    qty: Optional[float] = None
    price: Optional[float] = None


class FieldConfidence(BaseModel):
    supplier_bin: float = 0.0

    @field_validator("supplier_bin")
    @classmethod
    def clamp(cls, v: float) -> float:
        return max(0.0, min(1.0, v))


class DocumentExtraction(BaseModel):
    doc_type: DocType
    supplier_name: Optional[str] = None
    supplier_bin: Optional[str] = None
    doc_number: Optional[str] = None
    doc_date: Optional[str] = None
    currency: Optional[Currency] = None
    total_amount: Optional[float] = None
    vat_amount: Optional[float] = None
    line_items: list[LineItem] = []
    field_confidence: FieldConfidence = FieldConfidence()
    warnings: list[str] = []

    @field_validator("supplier_bin")
    @classmethod
    def validate_bin(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        digits_only = re.sub(r"\D", "", v)
        if len(digits_only) != 12:
            raise ValueError(f"supplier_bin must be 12 digits, got '{v}'")
        return digits_only

    @field_validator("doc_date")
    @classmethod
    def validate_date(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", v):
            raise ValueError(f"doc_date must be YYYY-MM-DD, got '{v}'")
        return v
