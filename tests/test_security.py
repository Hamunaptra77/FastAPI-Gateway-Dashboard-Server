import datetime as dt
import re

import pytest
from sqlalchemy.orm import Session

from app.models import Customer, License, LicenseLoginAttempt
from app.services.auth_service import validate_password_complexity


def _get_csrf_token(client, path: str) -> str:
    response = client.get(path, follow_redirects=False)
    match = re.search(r'name="csrf_token"\s+value="([^"]+)"', response.text)
    assert match is not None
    return match.group(1)


# ─── Password complexity ──────────────────────────────────────────────────────

def test_password_too_short():
    ok, code = validate_password_complexity("Ab1!")
    assert not ok
    assert code == "new_password_too_short"


def test_password_no_uppercase():
    ok, code = validate_password_complexity("abcdefgh1!")
    assert not ok
    assert code == "new_password_too_weak"


def test_password_no_digit():
    ok, code = validate_password_complexity("Abcdefgh!!")
    assert not ok
    assert code == "new_password_too_weak"


def test_password_no_special():
    ok, code = validate_password_complexity("Abcdefgh12")
    assert not ok
    assert code == "new_password_too_weak"


def test_password_valid():
    ok, code = validate_password_complexity("SecurePass1!")
    assert ok
    assert code == "ok"


# ─── License login brute-force ────────────────────────────────────────────────

def test_license_login_brute_force(client, seeded_license: License, test_db_session: Session):
    from app.config import settings

    for _ in range(settings.brute_force_max_attempts + 1):
        csrf_token = _get_csrf_token(client, "/license/login")
        client.post(
            "/license/login",
            data={"email": "tester@example.com", "license_key": "WRONG-KEY", "csrf_token": csrf_token},
            follow_redirects=False,
        )

    # After exceeding limit, correct credentials should also be blocked.
    csrf_token = _get_csrf_token(client, "/license/login")
    response = client.post(
        "/license/login",
        data={"email": "tester@example.com", "license_key": seeded_license.key, "csrf_token": csrf_token},
        follow_redirects=False,
    )
    assert response.status_code == 429


# ─── Dashboard auth ───────────────────────────────────────────────────────────

def test_dashboard_is_public(client):
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 200


def test_admin_dashboard_redirects_unauthenticated(client):
    response = client.get("/admin", follow_redirects=False)
    assert response.status_code == 303
    assert "/admin/login" in response.headers["location"]


# ─── plan_code validation ────────────────────────────────────────────────────

def test_checkout_rejects_trial_plan(client):
    response = client.post(
        "/api/payments/checkout",
        json={"email": "user@example.com", "full_name": "User", "plan_code": "trial5"},
    )
    assert response.status_code == 422


def test_checkout_rejects_unknown_plan(client):
    response = client.post(
        "/api/payments/checkout",
        json={"email": "user@example.com", "full_name": "User", "plan_code": "nonexistent"},
    )
    assert response.status_code == 422


def test_checkout_accepts_valid_plan_code(client, test_db_session, monkeypatch):
    from app.models import LicensePlan
    from app.routers import payments as pay_router

    monthly = LicensePlan(code="monthly", name="Monthly", price_eur=9.99, duration_days=30, is_active=True, is_trial=False)
    test_db_session.add(monthly)
    test_db_session.commit()

    monkeypatch.setattr(pay_router.paypal, "create_order", lambda **_: {"id": "ORDER-123", "status": "CREATED", "links": []})

    response = client.post(
        "/api/payments/checkout",
        json={"email": "user@example.com", "full_name": "User", "plan_code": "monthly"},
    )
    assert response.status_code == 200
