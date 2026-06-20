# Installation

## Empfohlen: Docker Compose

1. `.env` vorbereiten.
2. Container bauen und starten:

```bash
docker compose up -d --build
```

3. Status pruefen:

```bash
docker compose ps
```

4. Logs verfolgen:

```bash
docker compose logs -f
```

5. Healthcheck testen:

```bash
curl http://localhost:8000/health
```

Erwartete Antwort:

```json
{"status":"ok","service":"FastAPI License Gateway"}
```

## Optional: Lokale Installation ohne Docker

```bash
python -m venv .venv
```

PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

```bash
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Hinweis:

- Standard-Datenbank lokal: `sqlite:///./licenses.db`
- In Docker wird ueber Compose `sqlite:////app/data/licenses.db` gesetzt.
