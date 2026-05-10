# Traffic Jams Backend

FastAPI service that clusters historical traffic accident data using DBSCAN,
identifies dangerous road segments, and serves ML-based danger predictions.

---

## Prerequisites

- Python ≥ 3.13 with [uv](https://docs.astral.sh/uv/)
- Docker
- Access to a PostgreSQL / PostGIS database
- A `.env` file (see below)

---

## Deployment

### 1 — Get the `.env` file

Copy the template and fill in your database credentials:

```bash
cp .env.example .env
```

Minimum required values:

```bash
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/accidents_db
DATABASE_URL_SYNC=postgresql+psycopg2://user:pass@host:5432/accidents_db
DATA_SOURCE=postgres
AUTO_CLUSTER_ON_STARTUP=true
```

---

### 2 — Create database tables

Run once before starting the API for the first time:

```bash
uv run python scripts/create_tables.py
```

Creates `dangerous_road_clusters` and `cluster_accidents`. Safe to re-run.

---

### 3 — Load road segments

Load from the bundled CSV (fast, no internet needed):

```bash
uv run python scripts/update_road_segments.py --csv brno_roads_updated.csv
```

Or download a fresh snapshot from OpenStreetMap:

```bash
uv run python scripts/update_road_segments.py --place "Brno, Czechia"
```

---

### 4 — Build and run the API

```bash
docker build -t traffic-jams-api:latest .

docker run -d \
  --name traffic-jams-api \
  --restart unless-stopped \
  -p 8000:8000 \
  --env-file .env \
  traffic-jams-api:latest
```

With `AUTO_CLUSTER_ON_STARTUP=true` the API runs DBSCAN automatically on
the first boot if `dangerous_road_clusters` is empty.

---

## Local development with Docker Compose

Starts a PostGIS container alongside the API:

```bash
docker compose up --build
```

---

## Retraining ML models

```bash
uv run python scripts/train_model.py        # full grid search
uv run python scripts/train_model.py --quick  # faster iteration
```

Restart the container to load the new weights:

```bash
docker restart traffic-jams-api
```
