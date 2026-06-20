# API

## Health

- `GET /health`
- Zweck: Liveness/Readiness-Basischeck
- Antwort: `{"status":"ok","service":"..."}`

## Gateway

- `GET /api/gateway/validate`
- Header: `X-License-Key`
- Rate-Limit: `60/minute`
- Antwortmodell:
- `valid: bool`
- `email: string | null`
- `expires_at: datetime | null`
- `reason: string | null`

`reason` kann sein:

- `license_not_found`
- `license_inactive`
- `license_expired`

## Payments

- `POST /api/payments/checkout`
- Body: `email`, `full_name`, `plan_code`
- Erlaubte `plan_code`: `monthly`, `yearly`, `lifetime`
- Antwort: `order_id`, `approve_url`

- `POST /api/payments/trial`
- Body: `email`, `full_name`
- Ergebnis: Trial-Lizenz (`trial5`), wenn noch keine Trial fuer E-Mail existiert
- Rate-Limit ueber Trial-Request-Logs/IP

- `GET /api/payments/paypal/return?token=...`
- Captured eine Bestellung nach Rueckkehr von PayPal
- Finalisiert Kauf oder Renewal

- `GET /api/payments/paypal/cancel`
- Gibt Abbruchmeldung zurueck

- `POST /api/payments/paypal/webhook`
- Verifiziert PayPal-Webhook-Signatur
- Verarbeitet Event `PAYMENT.CAPTURE.COMPLETED`

## Dashboard und Admin (HTML)

- `GET /` (oeffentliches Dashboard)
- `GET /admin/login`
- `POST /admin/login`
- `GET /admin/logout`
- `GET /admin`
- `GET /admin/settings`
- `POST /admin/settings`
- `POST /admin/settings/reset`
- `POST /admin/licenses/{license_id}/toggle` (nur superadmin)
- `POST /admin/licenses/trial` (nur superadmin)
- `POST /admin/users/create`
- `POST /admin/users/{user_id}/delete`
- `GET /admin/password`
- `POST /admin/password`

## Lizenz-Benutzerbereich (HTML)

- `GET /license/login`
- `POST /license/login`
- `GET /license/dashboard`
- `POST /license/renew`
- `POST /license/cancel`
- `GET /license/logout`

## API-Fehlerformat

HTTP- und Validierungsfehler werden zentral als JSON ausgeliefert, z. B.:

```json
{
  "error": {
    "code": "http_error",
    "message": "..."
  }
}
```

Fuer Validation:

```json
{
  "error": {
    "code": "validation_error",
    "message": "Request validation failed",
    "details": []
  }
}
```
