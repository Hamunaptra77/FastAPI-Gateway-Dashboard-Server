from fastapi import APIRouter, Depends, Header, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas import LicenseValidationResponse
from app.services.license_service import validate_license_key

router = APIRouter(prefix="/api/gateway", tags=["gateway"])
limiter = Limiter(key_func=get_remote_address)


@router.get("/validate", response_model=LicenseValidationResponse)
@limiter.limit("60/minute")
def validate_license(
    request: Request,
    x_license_key: str = Header(default=""),
    db: Session = Depends(get_db),
):
    if not x_license_key:
        raise HTTPException(status_code=400, detail="Missing X-License-Key header")

    valid, email, expires_at, reason = validate_license_key(db, x_license_key)
    return LicenseValidationResponse(valid=valid, email=email, expires_at=expires_at, reason=reason)
