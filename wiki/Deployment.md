# Deployment

## Docker-Betrieb

- Service: `fastapi-license-gateway`
- Container-Port: `8000`
- Persistenz: Volume `gateway_data` nach `/app/data`
- Datenbank-Datei: `/app/data/licenses.db`

## Image-Details

- Basis: `python:3.12-slim`
- Startkommando: `uvicorn app.main:app --host 0.0.0.0 --port 8000`
- Container laeuft als unprivilegierter Benutzer `appuser`
- Healthcheck gegen `http://localhost:8000/health`

## Produktionsempfehlung

- Reverse Proxy vor die App (z. B. Nginx/Caddy)
- HTTPS erzwingen
- `APP_ENV=production`
- `APP_DEBUG=false`
- Starke und einzigartige Secrets/Passwoerter
- Regelmaessige Volume-Backups
