import datetime as dt
import re

import pytest
from sqlalchemy.orm import Session

from app.models import AdminUser
from app.services.auth_service import authenticate_admin, hash_password


def _get_csrf_token(client, path: str) -> str:
    response = client.get(path, follow_redirects=False)
    match = re.search(r'name="csrf_token"\s+value="([^"]+)"', response.text)
    assert match is not None
    return match.group(1)


def test_admin_login_success(client, superadmin_user: AdminUser):
    csrf_token = _get_csrf_token(client, "/admin/login")
    response = client.post(
        "/admin/login",
        data={"username": "testadmin", "password": "SecurePass1!", "csrf_token": csrf_token},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/admin"


def test_admin_login_wrong_password(client, superadmin_user: AdminUser):
    csrf_token = _get_csrf_token(client, "/admin/login")
    response = client.post(
        "/admin/login",
        data={"username": "testadmin", "password": "wrongpassword", "csrf_token": csrf_token},
        follow_redirects=False,
    )
    assert response.status_code == 401


def test_admin_login_nonexistent_user(client):
    csrf_token = _get_csrf_token(client, "/admin/login")
    response = client.post(
        "/admin/login",
        data={"username": "nobody", "password": "anything", "csrf_token": csrf_token},
        follow_redirects=False,
    )
    assert response.status_code == 401


def test_admin_login_inactive_user(client, test_db_session: Session):
    user = AdminUser(
        username="inactive_admin",
        password_hash=hash_password("SecurePass3!"),
        role="support",
        is_active=False,
    )
    test_db_session.add(user)
    test_db_session.commit()

    csrf_token = _get_csrf_token(client, "/admin/login")
    response = client.post(
        "/admin/login",
        data={"username": "inactive_admin", "password": "SecurePass3!", "csrf_token": csrf_token},
        follow_redirects=False,
    )
    assert response.status_code == 401


def test_admin_brute_force_lockout(client, test_db_session: Session, superadmin_user: AdminUser):
    from app.config import settings

    for _ in range(settings.brute_force_max_attempts):
        csrf_token = _get_csrf_token(client, "/admin/login")
        client.post(
            "/admin/login",
            data={"username": "testadmin", "password": "wrongpassword", "csrf_token": csrf_token},
            follow_redirects=False,
        )

    test_db_session.refresh(superadmin_user)
    assert superadmin_user.locked_until is not None
    assert superadmin_user.locked_until > dt.datetime.now(dt.UTC).replace(tzinfo=None)

    # Even correct password should fail while locked.
    csrf_token = _get_csrf_token(client, "/admin/login")
    response = client.post(
        "/admin/login",
        data={"username": "testadmin", "password": "SecurePass1!", "csrf_token": csrf_token},
        follow_redirects=False,
    )
    assert response.status_code == 401


def test_admin_brute_force_resets_on_success(client, test_db_session: Session, superadmin_user: AdminUser):
    # Cause some failed attempts without hitting lockout threshold.
    csrf_token = _get_csrf_token(client, "/admin/login")
    client.post(
        "/admin/login",
        data={"username": "testadmin", "password": "wrongpassword", "csrf_token": csrf_token},
        follow_redirects=False,
    )
    test_db_session.refresh(superadmin_user)
    assert superadmin_user.failed_login_attempts == 1

    # Successful login resets counter.
    csrf_token = _get_csrf_token(client, "/admin/login")
    client.post(
        "/admin/login",
        data={"username": "testadmin", "password": "SecurePass1!", "csrf_token": csrf_token},
        follow_redirects=False,
    )
    test_db_session.refresh(superadmin_user)
    assert superadmin_user.failed_login_attempts == 0
    assert superadmin_user.locked_until is None
