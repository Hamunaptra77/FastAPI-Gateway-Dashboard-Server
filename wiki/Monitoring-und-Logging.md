# Monitoring und Logging

## Request-Logging

Middleware in der App loggt fuer jede Anfrage:

- HTTP-Methode
- Pfad
- Statuscode
- Laufzeit in Millisekunden

## Fehler-Logging

- HTTP-Fehler (warn)
- Validierungsfehler (warn)
- Unbehandelte Ausnahmen (exception)
- Spezifische Security-/Betriebsereignisse (z. B. Account-Lock, PayPal-Fehler)

## Was sollte ueberwacht werden?

- Hauefigkeit von `401`/`403`/`429`
- Login-Lockouts bei Admin und Lizenz-Login
- PayPal Capture-/Webhook-Fehler
- SMTP Versandfehler
- Growth von Trial- und Audit-Logs

## Docker-Logrotation

In Compose konfiguriert:

- `max-size: 10m`
- `max-file: 5`
