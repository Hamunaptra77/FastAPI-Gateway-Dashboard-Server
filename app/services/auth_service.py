import datetime as dt
import hashlib
import logging
import re

from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.config import settings
from app.models import AdminUser

logger = logging.getLogger(__name__)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

_PASSWORD_MIN_LENGTH = 10
_PASSWORD_RE = re.compile(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[\W_]).+$")


def _legacy_hash_password(password: str) -> str:
    raw = f"{settings.app_secret_key}:{password}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    if password_hash.startswith("$2"):
        return pwd_context.verify(password, password_hash)
    return password_hash == _legacy_hash_password(password)


def validate_password_complexity(password: str) -> tuple[bool, str]:
    if len(password) < _PASSWORD_MIN_LENGTH:
        return False, "new_password_too_short"
    if not _PASSWORD_RE.match(password):
        return False, "new_password_too_weak"
    return True, "ok"


def seed_admin_users(db: Session) -> None:
    defaults = [
        (settings.default_superadmin_username, settings.default_superadmin_password, "superadmin"),
        (settings.default_support_username, settings.default_support_password, "support"),
    ]

    for username, password, role in defaults:
        normalized_username = username.strip().lower()
        if not normalized_username or not password:
            continue

        existing = db.query(AdminUser).filter(AdminUser.username == normalized_username).first()
        if existing:
            continue
        db.add(
            AdminUser(
                username=normalized_username,
                password_hash=hash_password(password),
                role=role,
                is_active=True,
            )
        )
    db.commit()


def _is_account_locked(user: AdminUser) -> bool:
    if user.locked_until is None:
        return False
    return dt.datetime.now(dt.UTC).replace(tzinfo=None) < user.locked_until


def authenticate_admin(db: Session, username: str, password: str) -> AdminUser | None:
    user = db.query(AdminUser).filter(AdminUser.username == username).first()

    # Always perform a dummy verify to prevent timing attacks that leak username existence.
    dummy_hash = "$2b$12$KIXtpIHnHiWF3oGKxYHgpOBWS5VyRF9u/X4N2oi3E9xFGKdF0ueEa"
    candidate_hash = user.password_hash if user else dummy_hash

    password_ok = verify_password(password, candidate_hash)

    if not user or not user.is_active:
        return None

    if _is_account_locked(user):
        logger.warning("admin_login_blocked username=%s locked_until=%s", username, user.locked_until)
        return None

    if not password_ok:
        user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
        if user.failed_login_attempts >= settings.brute_force_max_attempts:
            user.locked_until = dt.datetime.now(dt.UTC).replace(tzinfo=None) + dt.timedelta(
                minutes=settings.brute_force_lockout_minutes
            )
            logger.warning(
                "admin_account_locked username=%s until=%s", username, user.locked_until
            )
        db.add(user)
        db.commit()
        return None

    # Successful login – reset counters.
    user.failed_login_attempts = 0
    user.locked_until = None

    # Upgrade legacy SHA256 hashes to bcrypt after first successful login.
    if not user.password_hash.startswith("$2"):
        user.password_hash = hash_password(password)

    user.last_login_at = dt.datetime.now(dt.UTC).replace(tzinfo=None)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def change_admin_password(
    db: Session,
    admin_id: int,
    current_password: str,
    new_password: str,
) -> tuple[bool, str]:
    admin = db.query(AdminUser).filter(AdminUser.id == admin_id, AdminUser.is_active.is_(True)).first()
    if not admin:
        return False, "admin_not_found"

    ok, code = validate_password_complexity(new_password)
    if not ok:
        return False, code

    if not verify_password(current_password, admin.password_hash):
        return False, "current_password_invalid"

    admin.password_hash = hash_password(new_password)
    db.add(admin)
    db.commit()

    return True, "ok"
