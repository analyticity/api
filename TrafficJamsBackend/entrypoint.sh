#!/bin/sh
# Entrypoint for the Traffic Jams API container.
set -e

echo "Starting Traffic Jams API…"
echo "  DATA_SOURCE : ${DATA_SOURCE:-csv}"
echo "  WORKERS     : ${WORKERS:-1}"
echo "  PORT        : ${PORT:-8000}"

# ── Wait for database and create schema (postgres only) ──────────────────────
# The image ships with no schema — first boot creates the required tables.
# create_tables.py is idempotent (CREATE TABLE IF NOT EXISTS), so it is safe
# to run on every start. If the DB is not yet reachable we retry for up to
# DB_WAIT_TIMEOUT seconds before giving up.
if [ "${DATA_SOURCE:-csv}" = "postgres" ]; then
    DB_WAIT_TIMEOUT="${DB_WAIT_TIMEOUT:-60}"
    elapsed=0
    until python scripts/create_tables.py; do
        if [ "$elapsed" -ge "$DB_WAIT_TIMEOUT" ]; then
            echo "ERROR: database not reachable after ${DB_WAIT_TIMEOUT}s — aborting." >&2
            exit 1
        fi
        echo "  database not ready yet — retrying in 3s (waited ${elapsed}s)…"
        sleep 3
        elapsed=$((elapsed + 3))
    done

    # Optional CSV seeding — controlled by env flag so it does not run in
    # production where the accidents table is fed by the Kafka transformer.
    # When enabled (local dev), we truncate the four owned tables first so
    # that re-running `docker compose up` always yields a fresh, complete
    # dataset and forces auto-cluster to regenerate.
    if [ "${LOAD_CSV_ON_STARTUP:-false}" = "true" ]; then
        echo "LOAD_CSV_ON_STARTUP=true — wiping previous local data…"
        python - <<'PY'
from sqlalchemy import create_engine, text
from app.config import get_settings

engine = create_engine(get_settings().database_url_sync)
tables = ("cluster_accidents", "dangerous_road_clusters",
          "accidents", "road_segments")
with engine.begin() as conn:
    for t in tables:
        exists = conn.execute(
            text("SELECT to_regclass(:t)"), {"t": t}
        ).scalar()
        if exists:
            conn.execute(text(f"TRUNCATE TABLE {t} CASCADE"))
            print(f"INFO: truncated {t}")
        else:
            print(f"INFO: {t} not present yet — skipping truncate")
PY
        echo "Loading CSV data into postgres…"
        python scripts/load_csv_to_db.py
    fi
fi

# ── Auto-train if no model weights exist yet ──────────────────────────────────
# This only runs on the very first boot when no pre-trained weights are present
# (e.g. an empty volume was mounted or the models/ dir was not baked into the image).
# On subsequent starts the files are already there and this block is skipped.
MODELS_DIR="${MODELS_DIR:-models}"
if [ ! -f "${MODELS_DIR}/classifier.joblib" ] || [ ! -f "${MODELS_DIR}/regressor.joblib" ]; then
    echo "No model weights found in '${MODELS_DIR}/' — running train_model.py …"
    python scripts/train_model.py
    echo "Training complete."
else
    echo "Model weights found in '${MODELS_DIR}/' — skipping training."
fi

exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port "${PORT:-8000}" \
    --workers "${WORKERS:-1}"
