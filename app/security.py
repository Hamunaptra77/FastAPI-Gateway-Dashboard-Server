import hmac
import secrets

from fastapi import HTTPException, Request


_CSRF_SESSION_KEY = "csrf_token"


def get_csrf_token(request: Request) -> str:
    token = request.session.get(_CSRF_SESSION_KEY)
    if isinstance(token, str) and token:
        return token

    token = secrets.token_urlsafe(32)
    request.session[_CSRF_SESSION_KEY] = token
    return token


def validate_csrf_token(request: Request, submitted_token: str) -> None:
    stored_token = request.session.get(_CSRF_SESSION_KEY)
    if not isinstance(stored_token, str) or not stored_token:
        raise HTTPException(status_code=403, detail="Invalid CSRF token")

    if not submitted_token or not hmac.compare_digest(stored_token, submitted_token):
        raise HTTPException(status_code=403, detail="Invalid CSRF token")
