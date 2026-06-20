import datetime as dt

from app.models import License, LicensePlan, LicenseRenewalOrder
from app.routers import payments


def test_webhook_rejects_invalid_signature(client):
    payments.paypal.verify_webhook_signature = lambda *args, **kwargs: False

    event_payload = {
        "event_type": "PAYMENT.CAPTURE.COMPLETED",
        "resource": {},
    }

    response = client.post("/api/payments/paypal/webhook", json=event_payload)

    assert response.status_code == 400
    payload = response.json()
    assert payload["error"]["code"] == "http_error"
    assert "Invalid webhook signature" in payload["error"]["message"]


def test_webhook_processes_renewal_order(client, test_db_session, seeded_license: License, monkeypatch):
    monkeypatch.setattr(payments.paypal, "verify_webhook_signature", lambda *args, **kwargs: True)

    now = dt.datetime.now(dt.UTC).replace(tzinfo=None)
    current_expiry = now + dt.timedelta(days=5)
    seeded_license.expires_at = current_expiry
    test_db_session.add(seeded_license)

    yearly = LicensePlan(code="yearly", name="Yearly", price_eur=29.0, duration_days=365, is_active=True)
    test_db_session.add(yearly)

    renewal = LicenseRenewalOrder(
        paypal_order_id="ORDER-RENEW-1",
        status="CREATED",
        is_processed=False,
        license_id=seeded_license.id,
        plan_code="yearly",
    )
    test_db_session.add(renewal)
    test_db_session.commit()

    event_payload = {
        "event_type": "PAYMENT.CAPTURE.COMPLETED",
        "resource": {
            "id": "CAPTURE-123",
            "supplementary_data": {
                "related_ids": {
                    "order_id": "ORDER-RENEW-1"
                }
            },
        },
    }

    headers = {
        "paypal-transmission-id": "tid",
        "paypal-transmission-time": "2026-01-01T00:00:00Z",
        "paypal-cert-url": "https://example.com/cert",
        "paypal-auth-algo": "SHA256withRSA",
        "paypal-transmission-sig": "sig",
    }

    response = client.post("/api/payments/paypal/webhook", json=event_payload, headers=headers)
    assert response.status_code == 200
    assert response.json() == {"ok": True}

    updated = test_db_session.query(LicenseRenewalOrder).filter(LicenseRenewalOrder.id == renewal.id).first()
    updated_license = test_db_session.query(License).filter(License.id == seeded_license.id).first()

    assert updated is not None
    assert updated.is_processed is True
    assert updated.status == "COMPLETED"
    assert updated.paypal_capture_id == "CAPTURE-123"

    assert updated_license is not None
    assert updated_license.is_active is True
    assert updated_license.expires_at is not None
    assert updated_license.expires_at > current_expiry
