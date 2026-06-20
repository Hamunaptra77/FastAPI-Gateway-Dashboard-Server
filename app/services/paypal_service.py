import base64
import datetime as dt
import logging
import uuid
from typing import Any

import requests

from app.config import settings

logger = logging.getLogger(__name__)


class PayPalError(Exception):
    pass


class _TokenCache:
    def __init__(self) -> None:
        self._token: str | None = None
        self._expires_at: dt.datetime = dt.datetime.min

    def get(self, fetcher) -> str:
        if self._token and dt.datetime.utcnow() < self._expires_at:
            return self._token
        token, expires_in = fetcher()
        self._token = token
        self._expires_at = dt.datetime.utcnow() + dt.timedelta(seconds=max(expires_in - 60, 30))
        return self._token


class PayPalService:
    def __init__(self) -> None:
        self.base_url = (
            "https://api-m.paypal.com"
            if settings.paypal_mode == "live"
            else "https://api-m.sandbox.paypal.com"
        )
        self._cache = _TokenCache()

    def _fetch_access_token(self) -> tuple[str, int]:
        credentials = f"{settings.paypal_client_id}:{settings.paypal_client_secret}".encode("utf-8")
        encoded = base64.b64encode(credentials).decode("ascii")

        response = requests.post(
            f"{self.base_url}/v1/oauth2/token",
            headers={
                "Authorization": f"Basic {encoded}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={"grant_type": "client_credentials"},
            timeout=20,
        )
        if response.status_code >= 300:
            logger.error("paypal_token_error status=%s", response.status_code)
            raise PayPalError("Could not obtain PayPal access token.")
        data = response.json()
        return data["access_token"], int(data.get("expires_in", 3600))

    def _access_token(self) -> str:
        return self._cache.get(self._fetch_access_token)

    def create_order(self, amount_eur: str, return_url: str, cancel_url: str, idempotency_key: str | None = None) -> dict[str, Any]:
        token = self._access_token()
        payload = {
            "intent": "CAPTURE",
            "purchase_units": [
                {
                    "amount": {
                        "currency_code": "EUR",
                        "value": amount_eur,
                    }
                }
            ],
            "application_context": {
                "return_url": return_url,
                "cancel_url": cancel_url,
                "brand_name": settings.app_name,
                "landing_page": "LOGIN",
                "user_action": "PAY_NOW",
            },
        }

        headers: dict[str, str] = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        if idempotency_key:
            headers["PayPal-Request-Id"] = idempotency_key

        response = requests.post(
            f"{self.base_url}/v2/checkout/orders",
            headers=headers,
            json=payload,
            timeout=20,
        )
        if response.status_code >= 300:
            logger.error("paypal_create_order_error status=%s", response.status_code)
            raise PayPalError("Could not create PayPal order.")
        return response.json()

    def capture_order(self, order_id: str) -> dict[str, Any]:
        token = self._access_token()
        response = requests.post(
            f"{self.base_url}/v2/checkout/orders/{order_id}/capture",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "PayPal-Request-Id": str(uuid.uuid4()),
            },
            timeout=20,
        )
        if response.status_code >= 300:
            logger.error("paypal_capture_error status=%s order=%s", response.status_code, order_id)
            raise PayPalError("Could not capture PayPal order.")
        return response.json()

    def verify_webhook_signature(
        self,
        transmission_id: str,
        transmission_time: str,
        cert_url: str,
        auth_algo: str,
        transmission_sig: str,
        webhook_event: dict[str, Any],
        webhook_id: str,
    ) -> bool:
        token = self._access_token()
        payload = {
            "transmission_id": transmission_id,
            "transmission_time": transmission_time,
            "cert_url": cert_url,
            "auth_algo": auth_algo,
            "transmission_sig": transmission_sig,
            "webhook_id": webhook_id,
            "webhook_event": webhook_event,
        }
        response = requests.post(
            f"{self.base_url}/v1/notifications/verify-webhook-signature",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=20,
        )
        if response.status_code >= 300:
            logger.error("paypal_webhook_verify_error status=%s", response.status_code)
            raise PayPalError("Could not verify PayPal webhook signature.")
        result = response.json().get("verification_status")
        if result != "SUCCESS":
            logger.warning("paypal_webhook_invalid_signature verification_status=%s", result)
            return False
        return True
