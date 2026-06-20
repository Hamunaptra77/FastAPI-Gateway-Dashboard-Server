import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()

_WEAK_SECRET_VALUES = {
    "",
    "change-me",
    "change-this-to-a-long-random-secret",
}
_WEAK_ADMIN_PASSWORDS = {"", "admin", "admin123", "support", "support123", "password"}

ADMIN_ROLES = frozenset({"superadmin", "support"})


@dataclass
class Settings:
    app_name: str = os.getenv("APP_NAME", "FastAPI License Gateway")
    app_env: str = os.getenv("APP_ENV", "development")
    app_debug: bool = os.getenv("APP_DEBUG", "true").lower() == "true"
    app_secret_key: str = os.getenv("APP_SECRET_KEY", "change-me")
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./licenses.db")
    app_base_url: str = os.getenv("APP_BASE_URL", "http://localhost:8000")

    paypal_client_id: str = os.getenv("PAYPAL_CLIENT_ID", "")
    paypal_client_secret: str = os.getenv("PAYPAL_CLIENT_SECRET", "")
    paypal_mode: str = os.getenv("PAYPAL_MODE", "sandbox")
    paypal_webhook_id: str = os.getenv("PAYPAL_WEBHOOK_ID", "")

    plan_monthly_price_eur: float = float(os.getenv("PLAN_MONTHLY_PRICE_EUR", "9.99"))
    plan_yearly_price_eur: float = float(os.getenv("PLAN_YEARLY_PRICE_EUR", "29.00"))
    plan_lifetime_price_eur: float = float(os.getenv("PLAN_LIFETIME_PRICE_EUR", "99.00"))
    trial_inactive_delete_after_days: int = int(os.getenv("TRIAL_INACTIVE_DELETE_AFTER_DAYS", "30"))
    trial_cleanup_interval_seconds: int = int(os.getenv("TRIAL_CLEANUP_INTERVAL_SECONDS", "3600"))
    trial_rate_limit_window_seconds: int = int(os.getenv("TRIAL_RATE_LIMIT_WINDOW_SECONDS", "60"))
    trial_rate_limit_max_requests: int = int(os.getenv("TRIAL_RATE_LIMIT_MAX_REQUESTS", "3"))

    brute_force_max_attempts: int = int(os.getenv("BRUTE_FORCE_MAX_ATTEMPTS", "5"))
    brute_force_lockout_minutes: int = int(os.getenv("BRUTE_FORCE_LOCKOUT_MINUTES", "15"))
    session_timeout_minutes: int = int(os.getenv("SESSION_TIMEOUT_MINUTES", "60"))
    session_cookie_secure: str = os.getenv("SESSION_COOKIE_SECURE", "")

    smtp_enabled: bool = os.getenv("SMTP_ENABLED", "false").lower() == "true"
    smtp_host: str = os.getenv("SMTP_HOST", "")
    smtp_port: int = int(os.getenv("SMTP_PORT", "587"))
    smtp_user: str = os.getenv("SMTP_USER", "")
    smtp_password: str = os.getenv("SMTP_PASSWORD", "")
    smtp_from_email: str = os.getenv("SMTP_FROM_EMAIL", "noreply@example.com")
    smtp_use_tls: bool = os.getenv("SMTP_USE_TLS", "true").lower() == "true"

    default_superadmin_username: str = os.getenv("DEFAULT_SUPERADMIN_USERNAME", "admin")
    default_superadmin_password: str = os.getenv("DEFAULT_SUPERADMIN_PASSWORD", "admin123")
    default_support_username: str = os.getenv("DEFAULT_SUPPORT_USERNAME", "support")
    default_support_password: str = os.getenv("DEFAULT_SUPPORT_PASSWORD", "support123")

    def support_account_enabled(self) -> bool:
        return bool(self.default_support_username.strip())

    def session_cookie_secure_enabled(self) -> bool:
        flag = self.session_cookie_secure.strip().lower()
        if flag in {"true", "1", "yes", "on"}:
            return True
        if flag in {"false", "0", "no", "off"}:
            return False
        return self.app_env.lower() == "production"

    def security_warnings(self) -> list[str]:
        warnings: list[str] = []

        if self.app_secret_key in _WEAK_SECRET_VALUES:
            warnings.append("APP_SECRET_KEY uses an insecure placeholder value.")

        if self.default_superadmin_password in _WEAK_ADMIN_PASSWORDS:
            warnings.append("DEFAULT_SUPERADMIN_PASSWORD is weak and should be changed.")

        if self.support_account_enabled() and self.default_support_password in _WEAK_ADMIN_PASSWORDS:
            warnings.append("DEFAULT_SUPPORT_PASSWORD is weak and should be changed.")

        return warnings

    def ensure_security_for_runtime(self) -> None:
        warnings = self.security_warnings()

        # Weak secret key is never acceptable – abort in all environments.
        if self.app_secret_key in _WEAK_SECRET_VALUES:
            raise RuntimeError(
                "APP_SECRET_KEY is set to an insecure placeholder. "
                "Set a strong random value (≥32 chars) in your .env file."
            )

        # Weak admin credentials abort startup only in production.
        if self.app_env.lower() == "production" and warnings:
            raise RuntimeError("Unsafe production configuration: " + " | ".join(warnings))


settings = Settings()
