# INSTALL_DE.md

Diese Anleitung beschreibt die Installation des FastAPI Gateway + Dashboard Server praezise und praxisnah.

## 1. Ziel und Umfang

Die Anwendung besteht aus:
- FastAPI API (Gateway, Payments, Admin)
- Lizenz-Benutzerbereich (Login, Verlaengerung, Kuendigung)
- HTML Dashboard (Public + Admin)
- SQLite Datenbank
- PayPal Checkout/Webhook Integration
- Optional SMTP Versand fuer Lizenz-E-Mails

Empfohlene Betriebsart: Docker Compose mit einem App-Container und persistentem Volume fuer die Datenbank.

## 2. Voraussetzungen

### 2.1 Fuer Docker-Installation (empfohlen)
- Docker Desktop (oder Docker Engine + Compose Plugin)
- Freier Port 8000 am Host
- Internetzugang fuer Build (Python Packages)

### 2.2 Fuer lokale Installation (optional)
- Python 3.12
- pip
- Virtuelle Umgebung (venv)

## 3. Projektdateien pruefen

Im Projektordner muessen vorhanden sein:
- Dockerfile
- docker-compose.yml
- requirements.txt
- .env.example
- app/

## 4. Konfiguration vorbereiten (.env)

1. In den Projektordner wechseln.
2. .env aus .env.example erstellen.
3. Mindestens folgende Werte setzen:

Pflichtwerte (immer):
- APP_SECRET_KEY: starker geheimer Schluessel (keine Platzhalterwerte; schwache Platzhalter werden zur Laufzeit abgewiesen)
- DEFAULT_SUPERADMIN_USERNAME: z. B. "admin"
- DEFAULT_SUPERADMIN_PASSWORD: komplexes Passwort (min 10 Zeichen, Groß/Klein/Zahl/Sonderzeichen)
- DEFAULT_SUPPORT_USERNAME: optional, z. B. "support" (beide Support-Werte leer lassen, um das Support-Seeding zu deaktivieren)
- DEFAULT_SUPPORT_PASSWORD: komplexes Passwort (min 10 Zeichen, Groß/Klein/Zahl/Sonderzeichen; beide Support-Werte leer lassen, wenn das Support-Seeding deaktiviert ist)
- APP_ENV: production (oder development)
- APP_DEBUG: false (false in Produktion!)

PayPal Werte (falls Checkout genutzt wird):
- PAYPAL_CLIENT_ID
- PAYPAL_CLIENT_SECRET
- PAYPAL_MODE (sandbox oder live)
- PAYPAL_WEBHOOK_ID

SMTP Werte (nur wenn E-Mail Versand aktiv):
- SMTP_ENABLED=true
- SMTP_HOST
- SMTP_PORT
- SMTP_USER
- SMTP_PASSWORD
- SMTP_FROM_EMAIL
- SMTP_USE_TLS

Wichtiger Hinweis:
- Die Datei .env enthaelt Geheimnisse und darf nicht in ein Git-Repository eingecheckt werden.

## 5. Installation mit Docker (empfohlen)

### 5.1 Build und Start

Im Projektordner ausfuehren:

```bash
docker compose up -d --build
```

### 5.2 Laufstatus pruefen

```bash
docker compose ps
```

Erwartung:
- Service fastapi-license-gateway ist Up
- Port-Mapping 8000:8000 aktiv

### 5.3 Logs pruefen

```bash
docker compose logs -f
```

### 5.4 Healthcheck testen

```bash
curl http://localhost:8000/health
```

Erwartete Antwort:

```json
{"status":"ok","service":"FastAPI License Gateway"}
```

### 5.5 Datenpersistenz

- Die SQLite-Datenbank liegt im Volume gateway_data unter /app/data/licenses.db.
- Bei Neustart/Update bleibt die Datenbank erhalten, solange das Volume nicht geloescht wird.

## 6. Optionale lokale Installation (ohne Docker)

### 6.1 Abhaengigkeiten installieren

```bash
python -m venv .venv
```

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

Dann:

```bash
pip install -r requirements.txt
```

### 6.2 Starten

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Hinweis lokal:
- Standard-DATABASE_URL ist sqlite:///./licenses.db.
- Die Datei licenses.db wird im Projektordner erzeugt.

## 7. Erste Inbetriebnahme

Nach erfolgreichem Start:
- Dashboard: http://localhost:8000/
- Admin Login: http://localhost:8000/admin/login

Sofortmassnahmen:
1. Mit Default-Admin einloggen.
2. Passwoerter sofort auf sichere Werte aendern.
3. APP_SECRET_KEY mit starkem Zufallswert setzen.
4. PayPal Webhook auf produktive Domain konfigurieren (bei Livebetrieb).

Sprachumschaltung:
- `?lang=de`
- `?lang=en`
- `?lang=es`

Beispiele:
- `http://localhost:8000/?lang=en`
- `http://localhost:8000/admin/login?lang=es`

## 8. PayPal-spezifische Punkte

- Return URL und Cancel URL werden aus APP_BASE_URL erzeugt.
- Daher muss APP_BASE_URL zur echten, von außen erreichbaren URL passen.
- Webhook URL fuer PayPal:
  - https://deine-domain/api/payments/paypal/webhook
- Event:
  - PAYMENT.CAPTURE.COMPLETED

Wichtig fuer Livebetrieb:
- HTTPS zwingend verwenden.
- Reverse Proxy (z. B. Nginx oder Caddy) vor die App setzen.

## 9. Sicherheits- und Betriebs-Hinweise

- Niemals Default-Passwoerter im Betrieb lassen.
- .env niemals veroeffentlichen.
- Regelmaessige Backups des Volumes gateway_data einplanen.
- Logs auf fehlgeschlagene Logins und PayPal/Webhook-Fehler beobachten.

## 10. Update-Prozess

Bei Codeaenderungen:

```bash
docker compose up -d --build
```

Danach pruefen:
1. docker compose ps
2. docker compose logs --tail 200
3. GET /health

## 11. Troubleshooting

### Problem: Container startet nicht
Pruefen:
- .env vorhanden?
- APP_SECRET_KEY gesetzt?
- Fehlende Variablen fuer PayPal/SMTP?
- Logs: docker compose logs --tail 200

### Problem: Health nicht erreichbar
Pruefen:
- Port 8000 belegt?
- Containerstatus Up?
- Firewall/Proxy blockiert localhost:8000?

### Problem: PayPal Checkout/Webhook funktioniert nicht
Pruefen:
- PAYPAL_MODE korrekt (sandbox/live)
- Client ID/Secret korrekt
- PAYPAL_WEBHOOK_ID korrekt
- APP_BASE_URL zeigt auf richtige externe URL

### Problem: Keine Lizenz-Mail
Pruefen:
- SMTP_ENABLED=true
- SMTP Zugangsdaten korrekt
- SMTP_HOST/PORT erreichbar
- TLS-Einstellung passend zum Mailprovider

## 12. Minimal-Checkliste vor Produktion

1. APP_SECRET_KEY stark und einzigartig
2. Admin-Passwoerter geaendert
3. PAYPAL_MODE=live und Live-Credentials gesetzt
4. Webhook auf HTTPS Domain aktiv
5. Reverse Proxy + TLS aktiv
6. Backup-Strategie fuer gateway_data vorhanden
7. Monitoring/Log-Auswertung eingerichtet
