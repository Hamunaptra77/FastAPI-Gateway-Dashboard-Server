# Getting Started

## Was ist das?

FastAPI Gateway + Dashboard Server ist ein Lizenzverwaltungssystem mit folgenden Kernfunktionen:

- Lizenzverkauf per PayPal Checkout
- Automatische Lizenz-Ausstellung nach erfolgreicher Zahlung
- Testlizenz-Flow (5 Tage, einmal pro E-Mail)
- Gateway-Validierung fuer Client-Anwendungen
- Admin-Oberflaeche fuer Betrieb, Benutzerverwaltung und Monitoring
- Lizenz-Benutzerbereich fuer Login, Verlaengerung und Kuendigung

## Schnellstart in 5 Schritten

1. Projekt klonen und in den Ordner wechseln.
2. `.env` aus `.env.example` erstellen.
3. Pflichtvariablen setzen: `APP_SECRET_KEY`, Admin-Credentials, PayPal-Werte.
4. Starten mit Docker:

```bash
docker compose up -d --build
```

5. Aufrufen:
- Dashboard: `http://localhost:8000/`
- Admin Login: `http://localhost:8000/admin/login`
- Health: `http://localhost:8000/health`

## Technologien

- FastAPI 0.116.1
- Uvicorn 0.35.0
- SQLAlchemy 2.0.41
- SQLite (default) oder andere SQLAlchemy-kompatible DB
- PayPal REST API
- Jinja2 Templates
- SlowAPI fuer Rate-Limiting
- Pytest fuer Tests
