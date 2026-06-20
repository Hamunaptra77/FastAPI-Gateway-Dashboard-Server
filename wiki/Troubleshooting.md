# Troubleshooting

## Container startet nicht

Pruefen:

- Ist `.env` vorhanden?
- Ist `APP_SECRET_KEY` auf einen sicheren Wert gesetzt?
- Sind PayPal/SMTP-Werte korrekt, falls aktiviert?
- Logs lesen:

```bash
docker compose logs --tail 200
```

## Healthcheck nicht erreichbar

Pruefen:

- Laeuft der Container?
- Ist Port 8000 am Host frei?
- Blockiert Firewall oder Proxy?

## PayPal Checkout oder Webhook fehlschlaegt

Pruefen:

- `PAYPAL_MODE` korrekt (`sandbox`/`live`)
- `PAYPAL_CLIENT_ID`/`PAYPAL_CLIENT_SECRET` korrekt
- `PAYPAL_WEBHOOK_ID` korrekt
- `APP_BASE_URL` ist extern erreichbar und korrekt

## Keine Lizenz-E-Mail

Pruefen:

- `SMTP_ENABLED=true`
- SMTP Host/Port/User/Password korrekt
- TLS-Einstellung korrekt
- Mailserver erreichbar

## CSRF-Fehler bei Formularen (403)

Ursache:

- Token fehlt oder ist ungueltig.

Loesung:

- Formularseite neu laden und hidden `csrf_token` mitsenden.

## Tests schlagen unerwartet fehl

Wichtig:

- Testlauf erwartet `APP_ENV=testing` und `DATABASE_URL=sqlite://` vor App-Import.
