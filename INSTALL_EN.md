# INSTALL_EN.md

This guide describes how to install the FastAPI Gateway + Dashboard Server accurately and in a practical way.

## 1. Purpose and Scope

The application includes:
- FastAPI API (gateway, payments, admin)
- License user area (login, renewal, cancellation)
- HTML dashboard (public + admin)
- SQLite database
- PayPal checkout/webhook integration
- Optional SMTP sending for license emails

Recommended operating mode: Docker Compose with one app container and a persistent database volume.

## 2. Requirements

### 2.1 For Docker installation (recommended)
- Docker Desktop (or Docker Engine + Compose plugin)
- Free port 8000 on host
- Internet access for build (Python packages)

### 2.2 For local installation (optional)
- Python 3.12
- pip
- Virtual environment (venv)

## 3. Verify Project Files

The following files must exist in the project directory:
- Dockerfile
- docker-compose.yml
- requirements.txt
- .env.example
- app/

## 4. Prepare Configuration (.env)

1. Change into the project directory.
2. Create .env from .env.example.
3. Set at least the following values:

Required values (always):
- APP_SECRET_KEY: strong secret key (no placeholder values; the app rejects weak placeholders at runtime)
- DEFAULT_SUPERADMIN_USERNAME: e.g. "admin"
- DEFAULT_SUPERADMIN_PASSWORD: complex password (min 10 chars, upper/lower/number/special char)
- DEFAULT_SUPPORT_USERNAME: optional, e.g. "support" (leave both support values empty to disable support seeding)
- DEFAULT_SUPPORT_PASSWORD: complex password (min 10 chars, upper/lower/number/special char; leave both support values empty when support seeding is disabled)
- APP_ENV: production (or development)
- APP_DEBUG: false (must be false in production!)

PayPal values (if checkout is used):
- PAYPAL_CLIENT_ID
- PAYPAL_CLIENT_SECRET
- PAYPAL_MODE (sandbox or live)
- PAYPAL_WEBHOOK_ID

SMTP values (only if email sending is enabled):
- SMTP_ENABLED=true
- SMTP_HOST
- SMTP_PORT
- SMTP_USER
- SMTP_PASSWORD
- SMTP_FROM_EMAIL
- SMTP_USE_TLS

Important note:
- The .env file contains secrets and must not be committed to a Git repository.

## 5. Installation with Docker (Recommended)

### 5.1 Build and Start

Run in project directory:

```bash
docker compose up -d --build
```

### 5.2 Check Runtime Status

```bash
docker compose ps
```

Expected:
- Service fastapi-license-gateway is Up
- Port mapping 8000:8000 is active

### 5.3 Check Logs

```bash
docker compose logs -f
```

### 5.4 Test Healthcheck

```bash
curl http://localhost:8000/health
```

Expected response:

```json
{"status":"ok","service":"FastAPI License Gateway"}
```

### 5.5 Data Persistence

- The SQLite database is stored in volume gateway_data at /app/data/licenses.db.
- On restart/update, the database remains as long as the volume is not deleted.

## 6. Optional Local Installation (Without Docker)

### 6.1 Install Dependencies

```bash
python -m venv .venv
```

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

Then:

```bash
pip install -r requirements.txt
```

### 6.2 Start

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Local note:
- Default DATABASE_URL is sqlite:///./licenses.db.
- File licenses.db is created in the project directory.

## 7. First Startup

After successful startup:
- Dashboard: http://localhost:8000/
- Admin login: http://localhost:8000/admin/login

Immediate actions:
1. Log in with default admin.
2. Change passwords to secure values immediately.
3. Set APP_SECRET_KEY to a strong random value.
4. Configure PayPal webhook for production domain (for live mode).

## 8. PayPal-Specific Notes

- Return URL and cancel URL are generated from APP_BASE_URL.
- Therefore, APP_BASE_URL must match the real externally reachable URL.
- PayPal webhook URL:
  - https://your-domain/api/payments/paypal/webhook
- Event:
  - PAYMENT.CAPTURE.COMPLETED

Important for live operation:
- HTTPS is mandatory.
- Place a reverse proxy (for example Nginx or Caddy) in front of the app.

## 9. Security and Operations Notes

- Never keep default passwords in production.
- Never publish .env.
- Plan regular backups of volume gateway_data.
- Monitor logs for failed logins and PayPal/webhook errors.

## 10. Update Process

For code changes:

```bash
docker compose up -d --build
```

Then verify:
1. docker compose ps
2. docker compose logs --tail 200
3. GET /health

## 11. Troubleshooting

### Problem: Container does not start
Check:
- .env exists?
- APP_SECRET_KEY set?
- Missing variables for PayPal/SMTP?
- Logs: docker compose logs --tail 200

### Problem: Health endpoint not reachable
Check:
- Is port 8000 already in use?
- Is container status Up?
- Is firewall/proxy blocking localhost:8000?

### Problem: PayPal checkout/webhook not working
Check:
- PAYPAL_MODE correct (sandbox/live)
- Client ID/secret correct
- PAYPAL_WEBHOOK_ID correct
- APP_BASE_URL points to correct external URL

### Problem: No license email
Check:
- SMTP_ENABLED=true
- SMTP credentials correct
- SMTP_HOST/PORT reachable
- TLS setting matches your mail provider

## 12. Minimal Pre-Production Checklist

1. APP_SECRET_KEY is strong and unique
2. Admin passwords changed
3. PAYPAL_MODE=live and live credentials set
4. Webhook active on HTTPS domain
5. Reverse proxy + TLS enabled
6. Backup strategy for gateway_data in place
7. Monitoring/log analysis configured
