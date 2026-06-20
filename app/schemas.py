from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, field_validator

ALLOWED_PAID_PLAN_CODES = frozenset({"monthly", "yearly", "lifetime"})


class CreateCheckoutRequest(BaseModel):
    email: EmailStr
    full_name: str
    plan_code: str

    @field_validator("plan_code")
    @classmethod
    def validate_plan_code(cls, v: str) -> str:
        if v not in ALLOWED_PAID_PLAN_CODES:
            raise ValueError(f"plan_code must be one of: {', '.join(sorted(ALLOWED_PAID_PLAN_CODES))}")
        return v


class CreateCheckoutResponse(BaseModel):
    order_id: str
    approve_url: str


class CreateTrialRequest(BaseModel):
    email: EmailStr
    full_name: str


class CreateTrialResponse(BaseModel):
    license_key: str
    expires_at: datetime


class LicenseValidationResponse(BaseModel):
    valid: bool
    email: str | None = None
    expires_at: datetime | None = None
    reason: str | None = None
