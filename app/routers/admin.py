import datetime as dt
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload

from app.config import ADMIN_ROLES, settings
from app.db import get_db
from app.i18n import SUPPORTED_LANGUAGES, apply_language_cookie, resolve_language, translator
from app.models import AdminHeroContent, AdminUiSettings, AdminUser, AuditLog, License, Payment, TrialCleanupLog
from app.security import get_csrf_token, validate_csrf_token
from app.services.auth_service import (
    authenticate_admin,
    change_admin_password,
    hash_password,
    validate_password_complexity,
)
from app.services.license_service import get_or_create_customer, get_plan_by_code, issue_license

router = APIRouter(tags=["admin"])
templates = Jinja2Templates(directory="app/templates")

_ADMIN_UI_THEMES = frozenset({"default", "ocean", "sunset", "forest", "mono"})
_ADMIN_UI_FONT_SCALES = frozenset({90, 100, 110, 120})
_ADMIN_UI_HEADER_MAX_LEN = 60
_CONTROL_CENTER_TITLE_MAX_LEN = 60
_CONTROL_CENTER_HEADLINE_MAX_LEN = 180
_CONTROL_CENTER_DESCRIPTION_MAX_LEN = 500


def _base_i18n_context(request: Request) -> tuple[str, bool, dict]:
    language, should_set_cookie = resolve_language(request)
    t = translator(language)
    return language, should_set_cookie, {
        "lang": language,
        "supported_languages": SUPPORTED_LANGUAGES,
        "t": t,
    }


def _require_admin(request: Request, required_roles: frozenset = ADMIN_ROLES) -> dict | None:
    admin = request.session.get("admin")
    if not admin or admin.get("role") not in required_roles:
        return None
    return admin


def _check_session_timeout(request: Request) -> bool:
    last_active = request.session.get("last_active")
    if last_active is None:
        return False
    elapsed = (dt.datetime.utcnow() - dt.datetime.fromisoformat(last_active)).total_seconds()
    return elapsed > settings.session_timeout_minutes * 60


def _touch_session(request: Request) -> None:
    request.session["last_active"] = dt.datetime.utcnow().isoformat()


def _normalize_admin_ui_settings(theme: str, font_scale: str | int, header_name: str) -> dict:
    normalized_theme = str(theme).strip().lower()
    if normalized_theme not in _ADMIN_UI_THEMES:
        normalized_theme = "default"

    try:
        normalized_font_scale = int(font_scale)
    except (TypeError, ValueError):
        normalized_font_scale = 100
    if normalized_font_scale not in _ADMIN_UI_FONT_SCALES:
        normalized_font_scale = 100

    normalized_header_name = str(header_name).strip()[:_ADMIN_UI_HEADER_MAX_LEN]

    return {
        "theme": normalized_theme,
        "font_scale": normalized_font_scale,
        "header_name": normalized_header_name,
    }


def _get_admin_ui_settings(db: Session, admin_id: int) -> dict:
    row = db.query(AdminUiSettings).filter(AdminUiSettings.admin_user_id == admin_id).first()
    if row is None:
        return {
            "theme": "default",
            "font_scale": 100,
            "header_name": "",
        }

    theme = str(row.theme).strip().lower()
    if theme not in _ADMIN_UI_THEMES:
        theme = "default"

    try:
        font_scale = int(row.font_scale)
    except (TypeError, ValueError):
        font_scale = 100
    if font_scale not in _ADMIN_UI_FONT_SCALES:
        font_scale = 100

    header_name = str(row.header_name or "").strip()[:_ADMIN_UI_HEADER_MAX_LEN]

    return {
        "theme": theme,
        "font_scale": font_scale,
        "header_name": header_name,
    }


def _normalize_control_center_content(title: str, headline: str, description: str) -> dict:
    return {
        "title": str(title).strip()[:_CONTROL_CENTER_TITLE_MAX_LEN],
        "headline": str(headline).strip()[:_CONTROL_CENTER_HEADLINE_MAX_LEN],
        "description": str(description).strip()[:_CONTROL_CENTER_DESCRIPTION_MAX_LEN],
    }


def _get_control_center_content(db: Session, admin_id: int, t) -> dict:
    row = db.query(AdminHeroContent).filter(AdminHeroContent.admin_user_id == admin_id).first()

    default_title = t("control_center_default_title")
    default_headline = t("control_center_default_headline")
    default_description = t("control_center_default_description")

    if row is None:
        return {
            "title": default_title,
            "headline": default_headline,
            "description": default_description,
            "raw_title": "",
            "raw_headline": "",
            "raw_description": "",
        }

    raw_title = str(row.control_center_title or "").strip()[:_CONTROL_CENTER_TITLE_MAX_LEN]
    raw_headline = str(row.control_center_headline or "").strip()[:_CONTROL_CENTER_HEADLINE_MAX_LEN]
    raw_description = str(row.control_center_description or "").strip()[:_CONTROL_CENTER_DESCRIPTION_MAX_LEN]

    return {
        "title": raw_title or default_title,
        "headline": raw_headline or default_headline,
        "description": raw_description or default_description,
        "raw_title": raw_title,
        "raw_headline": raw_headline,
        "raw_description": raw_description,
    }


@router.get("/admin/login", response_class=HTMLResponse)
def admin_login_page(request: Request):
    language, should_set_cookie, i18n_ctx = _base_i18n_context(request)
    response = templates.TemplateResponse(
        request,
        "admin_login.html",
        {
            "app_name": settings.app_name,
            "error": "",
            "csrf_token": get_csrf_token(request),
            **i18n_ctx,
        },
    )
    apply_language_cookie(response, language, should_set_cookie)
    return response


@router.post("/admin/login", response_class=HTMLResponse)
def admin_login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    csrf_token: str = Form(""),
    db: Session = Depends(get_db),
):
    language, should_set_cookie, i18n_ctx = _base_i18n_context(request)
    t = i18n_ctx["t"]
    validate_csrf_token(request, csrf_token)

    user = authenticate_admin(db, username=username.strip(), password=password)
    if not user:
        # Check whether the account is locked to give a specific message.
        locked_user = db.query(AdminUser).filter(AdminUser.username == username.strip()).first()
        import datetime as dt
        is_locked = (
            locked_user is not None
            and locked_user.locked_until is not None
            and dt.datetime.now(dt.UTC).replace(tzinfo=None) < locked_user.locked_until
        )
        error_msg = t("account_locked") if is_locked else t("invalid_credentials")
        response = templates.TemplateResponse(
            request,
            "admin_login.html",
            {
                "app_name": settings.app_name,
                "error": error_msg,
                "csrf_token": get_csrf_token(request),
                **i18n_ctx,
            },
            status_code=401,
        )
        apply_language_cookie(response, language, should_set_cookie)
        return response

    request.session["admin"] = {
        "id": user.id,
        "username": user.username,
        "role": user.role,
    }
    _touch_session(request)
    response = RedirectResponse(url="/admin", status_code=303)
    apply_language_cookie(response, language, should_set_cookie)
    return response


@router.get("/admin/logout")
def admin_logout(request: Request):
    language, should_set_cookie, _ = _base_i18n_context(request)
    request.session.pop("admin", None)
    response = RedirectResponse(url="/admin/login", status_code=303)
    apply_language_cookie(response, language, should_set_cookie)
    return response


@router.get("/admin", response_class=HTMLResponse)
def admin_dashboard(request: Request, db: Session = Depends(get_db)):
    language, should_set_cookie, i18n_ctx = _base_i18n_context(request)
    t = i18n_ctx["t"]

    if _check_session_timeout(request):
        request.session.pop("admin", None)
    admin = _require_admin(request)
    if not admin:
        response = RedirectResponse(url="/admin/login", status_code=303)
        apply_language_cookie(response, language, should_set_cookie)
        return response

    _touch_session(request)
    ui_settings = _get_admin_ui_settings(db, admin["id"])
    control_center_content = _get_control_center_content(db, admin["id"], t)
    display_app_name = ui_settings["header_name"] or settings.app_name

    licenses = (
        db.query(License)
        .options(joinedload(License.customer), joinedload(License.plan))
        .order_by(License.created_at.desc())
        .limit(200)
        .all()
    )
    now = dt.datetime.now(dt.UTC).replace(tzinfo=None)
    license_rows: list[dict] = []
    for license_obj in licenses:
        if not license_obj.is_active:
            state = "inactive"
        elif license_obj.expires_at is not None and license_obj.expires_at < now:
            state = "expired"
        else:
            state = "active"

        remaining_days: int | None
        if license_obj.expires_at is None:
            remaining_days = None
        else:
            delta = license_obj.expires_at - now
            remaining_days = max(delta.days, 0)

        customer_name = ""
        customer_email = ""
        if license_obj.customer is not None:
            customer_name = (license_obj.customer.full_name or "").strip()
            customer_email = (license_obj.customer.email or "").strip()

        license_rows.append(
            {
                "license": license_obj,
                "state": state,
                "remaining_days": remaining_days,
                "customer_name": customer_name,
                "customer_email": customer_email,
            }
        )

    payments = db.query(Payment).order_by(Payment.created_at.desc()).limit(200).all()
    admins = db.query(AdminUser).order_by(AdminUser.created_at.desc()).all()
    latest_cleanup = db.query(TrialCleanupLog).order_by(TrialCleanupLog.created_at.desc()).first()

    trial_feedback = {
        "status": request.query_params.get("trial_status", "").strip(),
        "key": request.query_params.get("trial_key", "").strip(),
        "expires": request.query_params.get("trial_expires", "").strip(),
        "email": request.query_params.get("trial_email", "").strip(),
    }
    user_feedback = {
        "status": request.query_params.get("user_status", "").strip(),
        "username": request.query_params.get("user_username", "").strip(),
    }

    response = templates.TemplateResponse(
        request,
        "admin_dashboard.html",
        {
            "app_name": settings.app_name,
            "display_app_name": display_app_name,
            "admin": admin,
            "csrf_token": get_csrf_token(request),
            "ui_settings": ui_settings,
            "control_center_content": control_center_content,
            "licenses": licenses,
            "license_rows": license_rows,
            "payments": payments,
            "admins": admins,
            "latest_cleanup": latest_cleanup,
            "trial_feedback": trial_feedback,
            "user_feedback": user_feedback,
            **i18n_ctx,
        },
    )
    apply_language_cookie(response, language, should_set_cookie)
    return response


@router.get("/admin/settings", response_class=HTMLResponse)
def admin_settings_page(request: Request, db: Session = Depends(get_db)):
    language, should_set_cookie, i18n_ctx = _base_i18n_context(request)
    t = i18n_ctx["t"]

    if _check_session_timeout(request):
        request.session.pop("admin", None)
    admin = _require_admin(request)
    if not admin:
        response = RedirectResponse(url="/admin/login", status_code=303)
        apply_language_cookie(response, language, should_set_cookie)
        return response

    ui_settings = _get_admin_ui_settings(db, admin["id"])
    control_center_content = _get_control_center_content(db, admin["id"], t)
    status = request.query_params.get("status")
    if status == "saved":
        success = t("settings_saved")
    elif status == "reset":
        success = t("settings_reset")
    else:
        success = ""

    response = templates.TemplateResponse(
        request,
        "admin_settings.html",
        {
            "app_name": settings.app_name,
            "admin": admin,
            "csrf_token": get_csrf_token(request),
            "ui_settings": ui_settings,
            "control_center_content": control_center_content,
            "error": "",
            "success": success,
            **i18n_ctx,
        },
    )
    apply_language_cookie(response, language, should_set_cookie)
    return response


@router.post("/admin/settings")
def admin_settings_update(
    request: Request,
    theme: str = Form("default"),
    font_scale: str = Form("100"),
    header_name: str = Form(""),
    control_center_title: str = Form(""),
    control_center_headline: str = Form(""),
    control_center_description: str = Form(""),
    csrf_token: str = Form(""),
    db: Session = Depends(get_db),
):
    language, should_set_cookie, _ = _base_i18n_context(request)
    validate_csrf_token(request, csrf_token)

    if _check_session_timeout(request):
        request.session.pop("admin", None)
    admin = _require_admin(request)
    if not admin:
        response = RedirectResponse(url="/admin/login", status_code=303)
        apply_language_cookie(response, language, should_set_cookie)
        return response

    normalized = _normalize_admin_ui_settings(theme=theme, font_scale=font_scale, header_name=header_name)
    normalized_control_center = _normalize_control_center_content(
        title=control_center_title,
        headline=control_center_headline,
        description=control_center_description,
    )

    current = db.query(AdminUiSettings).filter(AdminUiSettings.admin_user_id == admin["id"]).first()
    if current is None:
        current = AdminUiSettings(admin_user_id=admin["id"])

    current.theme = normalized["theme"]
    current.font_scale = normalized["font_scale"]
    current.header_name = normalized["header_name"]
    db.add(current)

    hero_content = db.query(AdminHeroContent).filter(AdminHeroContent.admin_user_id == admin["id"]).first()
    if hero_content is None:
        hero_content = AdminHeroContent(admin_user_id=admin["id"])

    hero_content.control_center_title = normalized_control_center["title"]
    hero_content.control_center_headline = normalized_control_center["headline"]
    hero_content.control_center_description = normalized_control_center["description"]
    db.add(hero_content)
    db.commit()

    _touch_session(request)

    response = RedirectResponse(url="/admin/settings?status=saved", status_code=303)
    apply_language_cookie(response, language, should_set_cookie)
    return response


@router.post("/admin/settings/reset")
def admin_settings_reset(
    request: Request,
    csrf_token: str = Form(""),
    db: Session = Depends(get_db),
):
    language, should_set_cookie, _ = _base_i18n_context(request)
    validate_csrf_token(request, csrf_token)

    if _check_session_timeout(request):
        request.session.pop("admin", None)
    admin = _require_admin(request)
    if not admin:
        response = RedirectResponse(url="/admin/login", status_code=303)
        apply_language_cookie(response, language, should_set_cookie)
        return response

    current = db.query(AdminUiSettings).filter(AdminUiSettings.admin_user_id == admin["id"]).first()
    if current is not None:
        current.theme = "default"
        current.font_scale = 100
        current.header_name = ""
        db.add(current)

    hero_content = db.query(AdminHeroContent).filter(AdminHeroContent.admin_user_id == admin["id"]).first()
    if hero_content is not None:
        hero_content.control_center_title = ""
        hero_content.control_center_headline = ""
        hero_content.control_center_description = ""
        db.add(hero_content)

    db.commit()

    _touch_session(request)

    response = RedirectResponse(url="/admin/settings?status=reset", status_code=303)
    apply_language_cookie(response, language, should_set_cookie)
    return response


@router.post("/admin/licenses/{license_id}/toggle")
def toggle_license(
    license_id: int,
    request: Request,
    csrf_token: str = Form(""),
    db: Session = Depends(get_db),
):
    language, should_set_cookie, _ = _base_i18n_context(request)
    validate_csrf_token(request, csrf_token)

    if _check_session_timeout(request):
        request.session.pop("admin", None)
    admin = _require_admin(request, frozenset({"superadmin"}))
    if not admin:
        response = RedirectResponse(url="/admin/login", status_code=303)
        apply_language_cookie(response, language, should_set_cookie)
        return response

    license_obj = db.query(License).filter(License.id == license_id).first()
    if not license_obj:
        response = RedirectResponse(url="/admin", status_code=303)
        apply_language_cookie(response, language, should_set_cookie)
        return response

    previous_state = license_obj.is_active
    license_obj.is_active = not license_obj.is_active
    db.add(license_obj)

    audit = AuditLog(
        actor_username=admin["username"],
        action="toggle_license",
        target_type="license",
        target_id=str(license_id),
        detail=f"is_active changed from {previous_state} to {license_obj.is_active}",
    )
    db.add(audit)
    db.commit()
    _touch_session(request)

    response = RedirectResponse(url="/admin", status_code=303)
    apply_language_cookie(response, language, should_set_cookie)
    return response


@router.post("/admin/licenses/trial")
def issue_or_activate_trial_license(
    request: Request,
    email: str = Form(...),
    full_name: str = Form(default=""),
    csrf_token: str = Form(""),
    db: Session = Depends(get_db),
):
    language, should_set_cookie, _ = _base_i18n_context(request)
    validate_csrf_token(request, csrf_token)

    if _check_session_timeout(request):
        request.session.pop("admin", None)
    admin = _require_admin(request, frozenset({"superadmin"}))
    if not admin:
        response = RedirectResponse(url="/admin/login", status_code=303)
        apply_language_cookie(response, language, should_set_cookie)
        return response

    normalized_email = email.strip().lower()
    if not normalized_email:
        response = RedirectResponse(url="/admin?trial_status=error", status_code=303)
        apply_language_cookie(response, language, should_set_cookie)
        return response

    customer = get_or_create_customer(db, normalized_email, full_name.strip())
    trial_plan = get_plan_by_code(db, "trial5")
    if not trial_plan:
        response = RedirectResponse(url="/admin?trial_status=missing_plan", status_code=303)
        apply_language_cookie(response, language, should_set_cookie)
        return response

    existing_trial = (
        db.query(License)
        .filter(License.customer_id == customer.id, License.plan_code == trial_plan.code)
        .order_by(License.created_at.desc())
        .first()
    )

    if existing_trial:
        expires = dt.datetime.now(dt.UTC).replace(tzinfo=None) + dt.timedelta(days=5)
        existing_trial.is_active = True
        existing_trial.expires_at = expires
        db.add(existing_trial)

        audit = AuditLog(
            actor_username=admin["username"],
            action="activate_trial_license",
            target_type="license",
            target_id=str(existing_trial.id),
            detail=f"trial license activated for {normalized_email}",
        )
        db.add(audit)
        db.commit()

        params = urlencode(
            {
                "trial_status": "activated",
                "trial_key": existing_trial.key,
                "trial_expires": existing_trial.expires_at,
                "trial_email": normalized_email,
            }
        )
        response = RedirectResponse(url=f"/admin?{params}", status_code=303)
        apply_language_cookie(response, language, should_set_cookie)
        return response

    new_trial = issue_license(db, customer, trial_plan)
    audit = AuditLog(
        actor_username=admin["username"],
        action="issue_trial_license",
        target_type="license",
        target_id=str(new_trial.id),
        detail=f"trial license issued for {normalized_email}",
    )
    db.add(audit)
    db.commit()

    params = urlencode(
        {
            "trial_status": "issued",
            "trial_key": new_trial.key,
            "trial_expires": new_trial.expires_at,
            "trial_email": normalized_email,
        }
    )
    response = RedirectResponse(url=f"/admin?{params}", status_code=303)
    apply_language_cookie(response, language, should_set_cookie)
    return response


@router.post("/admin/users/create")
def create_admin_user(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    role: str = Form(...),
    csrf_token: str = Form(""),
    db: Session = Depends(get_db),
):
    language, should_set_cookie, _ = _base_i18n_context(request)
    validate_csrf_token(request, csrf_token)

    if _check_session_timeout(request):
        request.session.pop("admin", None)
    admin = _require_admin(request)
    if not admin:
        response = RedirectResponse(url="/admin/login", status_code=303)
        apply_language_cookie(response, language, should_set_cookie)
        return response

    normalized_username = username.strip().lower()
    if not normalized_username:
        response = RedirectResponse(url="/admin?user_status=invalid_input", status_code=303)
        apply_language_cookie(response, language, should_set_cookie)
        return response

    if role not in ADMIN_ROLES:
        response = RedirectResponse(url="/admin?user_status=invalid_role", status_code=303)
        apply_language_cookie(response, language, should_set_cookie)
        return response

    ok, code = validate_password_complexity(password)
    if not ok:
        response = RedirectResponse(url=f"/admin?user_status={code}", status_code=303)
        apply_language_cookie(response, language, should_set_cookie)
        return response

    existing = db.query(AdminUser).filter(AdminUser.username == normalized_username).first()
    if existing:
        response = RedirectResponse(url="/admin?user_status=username_exists", status_code=303)
        apply_language_cookie(response, language, should_set_cookie)
        return response

    new_user = AdminUser(
        username=normalized_username,
        password_hash=hash_password(password),
        role=role,
        is_active=True,
    )
    db.add(new_user)

    audit = AuditLog(
        actor_username=admin["username"],
        action="create_admin_user",
        target_type="admin_user",
        target_id=normalized_username,
        detail=f"role={role}",
    )
    db.add(audit)
    db.commit()

    params = urlencode({"user_status": "created", "user_username": normalized_username})
    response = RedirectResponse(url=f"/admin?{params}", status_code=303)
    apply_language_cookie(response, language, should_set_cookie)
    return response


@router.post("/admin/users/{user_id}/delete")
def delete_admin_user(
    user_id: int,
    request: Request,
    csrf_token: str = Form(""),
    db: Session = Depends(get_db),
):
    language, should_set_cookie, _ = _base_i18n_context(request)
    validate_csrf_token(request, csrf_token)

    if _check_session_timeout(request):
        request.session.pop("admin", None)
    admin = _require_admin(request)
    if not admin:
        response = RedirectResponse(url="/admin/login", status_code=303)
        apply_language_cookie(response, language, should_set_cookie)
        return response

    user_obj = db.query(AdminUser).filter(AdminUser.id == user_id).first()
    if not user_obj:
        response = RedirectResponse(url="/admin?user_status=user_not_found", status_code=303)
        apply_language_cookie(response, language, should_set_cookie)
        return response

    if user_obj.id == admin["id"]:
        response = RedirectResponse(url="/admin?user_status=cannot_delete_self", status_code=303)
        apply_language_cookie(response, language, should_set_cookie)
        return response

    if user_obj.role == "superadmin":
        superadmin_count = db.query(AdminUser).filter(AdminUser.role == "superadmin", AdminUser.is_active.is_(True)).count()
        if superadmin_count <= 1:
            response = RedirectResponse(url="/admin?user_status=last_superadmin", status_code=303)
            apply_language_cookie(response, language, should_set_cookie)
            return response

    deleted_username = user_obj.username
    db.delete(user_obj)

    audit = AuditLog(
        actor_username=admin["username"],
        action="delete_admin_user",
        target_type="admin_user",
        target_id=str(user_id),
        detail=f"username={deleted_username}",
    )
    db.add(audit)
    db.commit()

    params = urlencode({"user_status": "deleted", "user_username": deleted_username})
    response = RedirectResponse(url=f"/admin?{params}", status_code=303)
    apply_language_cookie(response, language, should_set_cookie)
    return response


@router.get("/admin/password", response_class=HTMLResponse)
def admin_password_page(request: Request):
    language, should_set_cookie, i18n_ctx = _base_i18n_context(request)

    if _check_session_timeout(request):
        request.session.pop("admin", None)
    admin = _require_admin(request)
    if not admin:
        response = RedirectResponse(url="/admin/login", status_code=303)
        apply_language_cookie(response, language, should_set_cookie)
        return response

    response = templates.TemplateResponse(
        request,
        "admin_password.html",
        {
            "app_name": settings.app_name,
            "admin": admin,
            "csrf_token": get_csrf_token(request),
            "error": "",
            "success": "",
            **i18n_ctx,
        },
    )
    apply_language_cookie(response, language, should_set_cookie)
    return response


@router.post("/admin/password", response_class=HTMLResponse)
def admin_password_update(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
    csrf_token: str = Form(""),
    db: Session = Depends(get_db),
):
    language, should_set_cookie, i18n_ctx = _base_i18n_context(request)
    t = i18n_ctx["t"]
    validate_csrf_token(request, csrf_token)

    if _check_session_timeout(request):
        request.session.pop("admin", None)
    admin = _require_admin(request)
    if not admin:
        response = RedirectResponse(url="/admin/login", status_code=303)
        apply_language_cookie(response, language, should_set_cookie)
        return response

    if new_password != confirm_password:
        response = templates.TemplateResponse(
            request,
            "admin_password.html",
            {
                "app_name": settings.app_name,
                "admin": admin,
                "csrf_token": get_csrf_token(request),
                "error": t("passwords_mismatch"),
                "success": "",
                **i18n_ctx,
            },
            status_code=400,
        )
        apply_language_cookie(response, language, should_set_cookie)
        return response

    ok, code = change_admin_password(
        db,
        admin_id=admin["id"],
        current_password=current_password,
        new_password=new_password,
    )
    if not ok:
        mapping = {
            "admin_not_found": t("admin_not_found"),
            "new_password_too_short": t("new_password_too_short"),
            "new_password_too_weak": t("new_password_too_weak"),
            "current_password_invalid": t("current_password_invalid"),
        }
        response = templates.TemplateResponse(
            request,
            "admin_password.html",
            {
                "app_name": settings.app_name,
                "admin": admin,
                "csrf_token": get_csrf_token(request),
                "error": mapping.get(code, t("password_change_failed")),
                "success": "",
                **i18n_ctx,
            },
            status_code=400,
        )
        apply_language_cookie(response, language, should_set_cookie)
        return response

    response = templates.TemplateResponse(
        request,
        "admin_password.html",
        {
            "app_name": settings.app_name,
            "admin": admin,
            "csrf_token": get_csrf_token(request),
            "error": "",
            "success": t("password_changed_success"),
            **i18n_ctx,
        },
    )
    apply_language_cookie(response, language, should_set_cookie)
    return response
