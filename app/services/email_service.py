import logging
import smtplib
import time
from email.message import EmailMessage

from app.config import settings
from app.models import Customer, License

logger = logging.getLogger(__name__)

_EMAIL_SUBJECTS = {
    "de": "Deine Lizenz fuer {app_name}",
    "en": "Your license for {app_name}",
    "es": "Tu licencia para {app_name}",
}

_EMAIL_BODIES = {
    "de": (
        "Hallo {name},\n\n"
        "deine Zahlung war erfolgreich. Hier sind deine Lizenzdaten:\n\n"
        "Lizenzschluessel: {key}\n"
        "Plan: {plan}\n"
        "Gueltig bis: {expires}\n\n"
        "Viele Gruesse"
    ),
    "en": (
        "Hello {name},\n\n"
        "your payment was successful. Here are your license details:\n\n"
        "License key: {key}\n"
        "Plan: {plan}\n"
        "Valid until: {expires}\n\n"
        "Kind regards"
    ),
    "es": (
        "Hola {name},\n\n"
        "tu pago fue exitoso. Aqui estan los detalles de tu licencia:\n\n"
        "Clave de licencia: {key}\n"
        "Plan: {plan}\n"
        "Valido hasta: {expires}\n\n"
        "Saludos"
    ),
}

_RETRY_ATTEMPTS = 3
_RETRY_DELAY_SECONDS = 2


def send_license_email(
    customer: Customer, license_obj: License, language: str = "de"
) -> tuple[bool, str | None]:
    if not settings.smtp_enabled:
        return False, "smtp_disabled"

    lang = language if language in _EMAIL_SUBJECTS else "de"
    expires_text = "Lifetime" if license_obj.expires_at is None else str(license_obj.expires_at)

    message = EmailMessage()
    message["Subject"] = _EMAIL_SUBJECTS[lang].format(app_name=settings.app_name)
    message["From"] = settings.smtp_from_email
    message["To"] = customer.email
    message.set_content(
        _EMAIL_BODIES[lang].format(
            name=customer.full_name,
            key=license_obj.key,
            plan=license_obj.plan_code,
            expires=expires_text,
        )
    )

    last_error: str | None = None
    for attempt in range(1, _RETRY_ATTEMPTS + 1):
        try:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as smtp:
                if settings.smtp_use_tls:
                    smtp.starttls()
                if settings.smtp_user:
                    smtp.login(settings.smtp_user, settings.smtp_password)
                smtp.send_message(message)
            return True, None
        except Exception as exc:
            last_error = type(exc).__name__
            logger.warning("email_send_failed attempt=%s/%s error=%s", attempt, _RETRY_ATTEMPTS, last_error)
            if attempt < _RETRY_ATTEMPTS:
                time.sleep(_RETRY_DELAY_SECONDS)

    return False, last_error
