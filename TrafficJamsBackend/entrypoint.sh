#!/bin/sh
# Entrypoint for the Traffic Jams API container.
# Add pre-start steps here (e.g. Alembic migrations) before the server starts.
set -e

echo "Starting Traffic Jams API…"
echo "  DATA_SOURCE : ${DATA_SOURCE:-csv}"
echo "  WORKERS     : ${WORKERS:-1}"
echo "  PORT        : ${PORT:-8000}"

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
