# Traffic Jams Backend

FastAPI service that clusters historical traffic accident data using DBSCAN,
identifies dangerous road segments, and serves ML-based danger predictions.

---

## Prerequisites

| Tool | Version |
|---|---|
| Python | ≥ 3.13 |
| [uv](https://docs.astral.sh/uv/) | latest |
| Docker + Docker Compose | for containerised runs |

---

## Configuration

All settings are read from environment variables (or a `.env` file in this directory).
Copy the template and fill in your values:

```bash
cp .env.example .env
```

Key variables:

| Variable | Default | Description |
|---|---|---|
| `DATA_SOURCE` | `csv` | `csv` — no DB needed; `postgres` — use PostGIS |
| `DATABASE_URL` | localhost:5432 | Async SQLAlchemy URL (runtime) |
| `DATABASE_URL_SYNC` | localhost:5432 | Sync SQLAlchemy URL (Alembic migrations) |
| `ACCIDENTS_CSV_PATH` | `accidents_data.csv` | Path to accident data CSV |
| `ROAD_SEGMENTS_CSV_PATH` | `../../road_segments.csv` | Path to road segments CSV |
| `MODELS_DIR` | `models` | Directory with `classifier.joblib` / `regressor.joblib` |
| `WORKERS` | `1` | Uvicorn worker count (keep at 1 for `DATA_SOURCE=csv`) |

---

## 1 — Run locally (no Docker)

```bash
# Install dependencies
uv sync

# Train ML models (required before /api/prediction endpoints work)
uv run python scripts/train_model.py

# Start the API  (DATA_SOURCE=csv by default — no database needed)
uv run uvicorn app.main:app --reload --port 8000
```

API docs: http://localhost:8000/docs

---

## 2 — Local development with Docker Compose (PostgreSQL)

`docker-compose.yml` starts a PostGIS container alongside the API.
Use this when you need a real database locally.

```bash
# Build the image and start both services
docker compose up --build

# Start only the database (connect your local uvicorn to it)
docker compose up db

# Stop everything and remove the postgres volume
docker compose down -v
```

After the stack is up, run Alembic migrations to create the schema:

```bash
# Inside the running api container
docker compose exec api alembic upgrade head

# Or from your host machine (requires DATABASE_URL_SYNC in .env pointing to localhost:5432)
uv run alembic upgrade head
```

API docs: http://localhost:8000/docs

---

## 3 — Production (Docker only, external PostgreSQL)

On the server you run **only the Docker image** — no Compose, no local DB.

### Build the image

```bash
# From api/TrafficJamsBackend/
docker build -t traffic-jams-api:latest .
```

### Run the container

```bash
docker run -d \
  --name traffic-jams-api \
  --restart unless-stopped \
  -p 8000:8000 \
  -e DATA_SOURCE=postgres \
  -e DATABASE_URL="postgresql+asyncpg://user:pass@your-db-host:5432/accidents_db" \
  -e DATABASE_URL_SYNC="postgresql+psycopg2://user:pass@your-db-host:5432/accidents_db" \
  -e MODELS_DIR=/app/models \
  -v /srv/traffic-jams/models:/app/models \
  traffic-jams-api:latest
```

> **Tip:** pass all variables via `--env-file /path/to/.env` instead of individual `-e` flags.

Run migrations once after the first deploy:

```bash
docker exec traffic-jams-api alembic upgrade head
```

---

## Retraining ML models

```bash
# Locally
uv run python scripts/train_model.py --accidents-csv accidents_data.csv

# Inside the container
docker exec traffic-jams-api python scripts/train_model.py
```

New `.joblib` files are written to `MODELS_DIR`.
The API loads models at startup — restart the container (or compose service) to pick up new weights:

```bash
docker compose restart api   # compose
docker restart traffic-jams-api  # standalone
```
