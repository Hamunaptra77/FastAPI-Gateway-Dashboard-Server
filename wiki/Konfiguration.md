# Konfiguration

## Umgebungsvariablen (Uebersicht)

### Core

- `APP_NAME`
- `APP_ENV` (`development` oder `production`)
- `APP_DEBUG`
- `APP_SECRET_KEY`
- `DATABASE_URL`
- `APP_BASE_URL`

### PayPal

- `PAYPAL_CLIENT_ID`
- `PAYPAL_CLIENT_SECRET`
- `PAYPAL_MODE` (`sandbox` oder `live`)
- `PAYPAL_WEBHOOK_ID`

### Preise

- `PLAN_MONTHLY_PRICE_EUR`
- `PLAN_YEARLY_PRICE_EUR`
- `PLAN_LIFETIME_PRICE_EUR`

### Trial und Limits

- `TRIAL_INACTIVE_DELETE_AFTER_DAYS`
- `TRIAL_CLEANUP_INTERVAL_SECONDS`
- `TRIAL_RATE_LIMIT_WINDOW_SECONDS`
- `TRIAL_RATE_LIMIT_MAX_REQUESTS`

### Login-Schutz und Session

- `BRUTE_FORCE_MAX_ATTEMPTS`
- `BRUTE_FORCE_LOCKOUT_MINUTES`
- `SESSION_TIMEOUT_MINUTES`
- `SESSION_COOKIE_SECURE` (optional, Auto-Mode per `APP_ENV`)

### SMTP (optional)

- `SMTP_ENABLED`
- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USER`
- `SMTP_PASSWORD`
- `SMTP_FROM_EMAIL`
- `SMTP_USE_TLS`

### Admin-Seeding

- `DEFAULT_SUPERADMIN_USERNAME`
- `DEFAULT_SUPERADMIN_PASSWORD`
- `DEFAULT_SUPPORT_USERNAME`
- `DEFAULT_SUPPORT_PASSWORD`

## Wichtige Konfigurationsregeln

- `APP_SECRET_KEY` darf kein Platzhalter sein, sonst bricht der Start mit RuntimeError ab.
- In Produktion stoppt die App bei unsicheren Default-Admin-Passwoertern.
- Support-Seeding ist deaktivierbar, wenn `DEFAULT_SUPPORT_USERNAME` und `DEFAULT_SUPPORT_PASSWORD` leer sind.
- `APP_BASE_URL` muss mit der extern erreichbaren URL uebereinstimmen (wichtig fuer PayPal Return/Cancel/Webhook-Flows).

## Mehrsprachigkeit

Unterstuetzte Sprachen:

- `de`
- `en`
- `es`

Sprache kann per `?lang=<code>` gesetzt werden und wird als Cookie gespeichert.
