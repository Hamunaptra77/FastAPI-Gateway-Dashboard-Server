from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload

from app.config import settings
from app.db import get_db
from app.i18n import SUPPORTED_LANGUAGES, apply_language_cookie, resolve_language, translator
from app.models import License, Payment
from app.services.license_service import get_active_plans

router = APIRouter(tags=["dashboard"])
templates = Jinja2Templates(directory="app/templates")

_PAGE_SIZE = 50


@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request, page: int = 1, db: Session = Depends(get_db)):
    language, should_set_cookie = resolve_language(request)
    t = translator(language)

    admin = request.session.get("admin")
    is_admin = bool(admin and admin.get("role") in {"superadmin", "support"})

    offset = (max(page, 1) - 1) * _PAGE_SIZE

    # Keep purchase flow public, but only load sensitive payment/license data for admins.
    if is_admin:
        licenses = (
            db.query(License)
            .options(joinedload(License.customer), joinedload(License.plan))
            .order_by(License.created_at.desc())
            .offset(offset)
            .limit(_PAGE_SIZE)
            .all()
        )
        payments = (
            db.query(Payment)
            .options(joinedload(Payment.customer))
            .order_by(Payment.created_at.desc())
            .offset(offset)
            .limit(_PAGE_SIZE)
            .all()
        )
    else:
        licenses = []
        payments = []

    plans = get_active_plans(db)

    response = templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "app_name": settings.app_name,
            "admin": admin,
            "licenses": licenses,
            "payments": payments,
            "plans": plans,
            "is_admin": is_admin,
            "page": page,
            "t": t,
            "lang": language,
            "supported_languages": SUPPORTED_LANGUAGES,
        },
    )
    apply_language_cookie(response, language, should_set_cookie)
    return response
