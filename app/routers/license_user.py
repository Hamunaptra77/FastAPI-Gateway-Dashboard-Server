from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.i18n import SUPPORTED_LANGUAGES, apply_language_cookie, resolve_language, translator
from app.models import Customer, License, LicenseLoginAttempt, LicenseRenewalOrder
from app.security import get_csrf_token, validate_csrf_token
from app.services.license_service import get_active_plans, get_plan_by_code
from app.services.paypal_service import PayPalError, PayPalService

router = APIRouter(tags=["license-user"])
templates = Jinja2Templates(directory="app/templates")
paypal = PayPalService()


def _base_i18n_context(request: Request) -> tuple[str, bool, dict]:
    language, should_set_cookie = resolve_language(request)
    t = translator(language)
    return language, should_set_cookie, {
        "lang": language,
        "supported_languages": SUPPORTED_LANGUAGES,
        "t": t,
    }


def _check_license_brute_force(db: Session, ip: str, email: str) -> bool:
    import datetime as dt
    normalized_email = email.lower().strip()
    window_start = dt.datetime.now(dt.UTC).replace(tzinfo=None) - dt.timedelta(
        seconds=settings.trial_rate_limit_window_seconds * 10  # 10x larger window for login
    )
    count = (
        db.query(LicenseLoginAttempt)
        .filter(
            LicenseLoginAttempt.ip_address == ip,
            LicenseLoginAttempt.email == normalized_email,
            LicenseLoginAttempt.created_at >= window_start,
        )
        .count()
    )
    return count >= settings.brute_force_max_attempts


def _log_license_attempt(db: Session, ip: str, email: str) -> None:
    db.add(LicenseLoginAttempt(ip_address=ip, email=email.lower().strip()))
    db.commit()


def _license_client_ip(request: Request) -> str:
    if request.client:
        return request.client.host
    return "unknown"


def _active_license_user(request: Request, db: Session) -> tuple[dict | None, License | None]:
    session_user = request.session.get("license_user")
    if not session_user:
        return None, None

    license_obj = (
        db.query(License)
        .join(Customer, Customer.id == License.customer_id)
        .filter(
            License.id == session_user.get("license_id"),
            Customer.email == session_user.get("email"),
        )
        .first()
    )
    return session_user, license_obj


@router.get("/license/login", response_class=HTMLResponse)
def license_login_page(request: Request):
    language, should_set_cookie, i18n_ctx = _base_i18n_context(request)
    response = templates.TemplateResponse(
        request,
        "license_login.html",
        {
            "app_name": settings.app_name,
            "error": "",
            "csrf_token": get_csrf_token(request),
            **i18n_ctx,
        },
    )
    apply_language_cookie(response, language, should_set_cookie)
    return response


@router.post("/license/login", response_class=HTMLResponse)
def license_login(
    request: Request,
    email: str = Form(...),
    license_key: str = Form(...),
    csrf_token: str = Form(""),
    db: Session = Depends(get_db),
):
    language, should_set_cookie, i18n_ctx = _base_i18n_context(request)
    t = i18n_ctx["t"]
    ip = _license_client_ip(request)
    validate_csrf_token(request, csrf_token)

    if _check_license_brute_force(db, ip, email):
        response = templates.TemplateResponse(
            request,
            "license_login.html",
            {
                "app_name": settings.app_name,
                "error": t("account_locked"),
                "csrf_token": get_csrf_token(request),
                **i18n_ctx,
            },
            status_code=429,
        )
        apply_language_cookie(response, language, should_set_cookie)
        return response

    license_obj = (
        db.query(License)
        .join(Customer, Customer.id == License.customer_id)
        .filter(Customer.email == email.lower().strip(), License.key == license_key.strip())
        .first()
    )

    if not license_obj:
        _log_license_attempt(db, ip, email)
        response = templates.TemplateResponse(
            request,
            "license_login.html",
            {
                "app_name": settings.app_name,
                "error": t("license_or_email_invalid"),
                "csrf_token": get_csrf_token(request),
                **i18n_ctx,
            },
            status_code=401,
        )
        apply_language_cookie(response, language, should_set_cookie)
        return response

    request.session["license_user"] = {
        "license_id": license_obj.id,
        "email": license_obj.customer.email,
    }

    response = RedirectResponse(url="/license/dashboard", status_code=303)
    apply_language_cookie(response, language, should_set_cookie)
    return response


@router.get("/license/logout")
def license_logout(request: Request):
    language, should_set_cookie, _ = _base_i18n_context(request)
    request.session.pop("license_user", None)
    response = RedirectResponse(url="/license/login", status_code=303)
    apply_language_cookie(response, language, should_set_cookie)
    return response


@router.get("/license/dashboard", response_class=HTMLResponse)
def license_dashboard(request: Request, db: Session = Depends(get_db)):
    language, should_set_cookie, i18n_ctx = _base_i18n_context(request)
    _, license_obj = _active_license_user(request, db)
    if not license_obj:
        response = RedirectResponse(url="/license/login", status_code=303)
        apply_language_cookie(response, language, should_set_cookie)
        return response

    plans = [p for p in get_active_plans(db) if p.code not in {"trial5"}]

    response = templates.TemplateResponse(
        request,
        "license_dashboard.html",
        {
            "app_name": settings.app_name,
            "license": license_obj,
            "plans": plans,
            "csrf_token": get_csrf_token(request),
            "message": request.query_params.get("msg", ""),
            **i18n_ctx,
        },
    )
    apply_language_cookie(response, language, should_set_cookie)
    return response


@router.post("/license/cancel")
def license_cancel(
    request: Request,
    csrf_token: str = Form(""),
    db: Session = Depends(get_db),
):
    language, should_set_cookie, _ = _base_i18n_context(request)
    validate_csrf_token(request, csrf_token)
    _, license_obj = _active_license_user(request, db)
    if not license_obj:
        response = RedirectResponse(url="/license/login", status_code=303)
        apply_language_cookie(response, language, should_set_cookie)
        return response

    license_obj.is_active = False
    db.add(license_obj)
    db.commit()

    response = RedirectResponse(url="/license/dashboard?msg=canceled", status_code=303)
    apply_language_cookie(response, language, should_set_cookie)
    return response


@router.post("/license/renew")
def license_renew(
    request: Request,
    plan_code: str = Form(...),
    csrf_token: str = Form(""),
    db: Session = Depends(get_db),
):
    language, should_set_cookie, _ = _base_i18n_context(request)
    validate_csrf_token(request, csrf_token)
    _, license_obj = _active_license_user(request, db)
    if not license_obj:
        response = RedirectResponse(url="/license/login", status_code=303)
        apply_language_cookie(response, language, should_set_cookie)
        return response

    selected_plan = get_plan_by_code(db, plan_code)
    if not selected_plan or selected_plan.is_trial:
        response = RedirectResponse(url="/license/dashboard?msg=plan_invalid", status_code=303)
        apply_language_cookie(response, language, should_set_cookie)
        return response

    try:
        order = paypal.create_order(
            amount_eur=f"{selected_plan.price_eur:.2f}",
            return_url=f"{settings.app_base_url}/api/payments/paypal/return",
            cancel_url=f"{settings.app_base_url}/license/dashboard?msg=renew_cancelled",
        )
    except PayPalError:
        response = RedirectResponse(url="/license/dashboard?msg=renew_failed", status_code=303)
        apply_language_cookie(response, language, should_set_cookie)
        return response

    renewal = LicenseRenewalOrder(
        paypal_order_id=order["id"],
        status=order.get("status", "CREATED"),
        license_id=license_obj.id,
        plan_code=selected_plan.code,
    )
    db.add(renewal)
    db.commit()

    approve_url = ""
    for link in order.get("links", []):
        if link.get("rel") == "approve":
            approve_url = link.get("href", "")
            break

    response = RedirectResponse(url=approve_url or "/license/dashboard?msg=renew_failed", status_code=303)
    apply_language_cookie(response, language, should_set_cookie)
    return response

