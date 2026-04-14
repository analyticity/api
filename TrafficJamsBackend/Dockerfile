# ── Stage 1: dependency installer ─────────────────────────────────────────────
# Uses uv to create a virtual environment from the locked dependency manifest.
# Keeping this in a separate stage means application-code changes never
# invalidate the (slow) dependency-installation layer.
FROM python:3.13-slim AS builder

# Pull the uv binary from the official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy only the dependency manifests first.
# Docker will cache this layer and skip re-installing when only app code changes.
COPY pyproject.toml uv.lock ./

# Install all production dependencies into a virtual environment.
# --frozen         — use exact versions from uv.lock, never resolve
# --no-install-project — skip installing the project itself (we COPY source directly)
RUN uv sync --frozen --no-install-project


# ── Stage 2: runtime image ────────────────────────────────────────────────────
FROM python:3.13-slim AS runtime

# scikit-learn uses OpenMP for parallelism; libgomp1 is not present in slim
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# CSV data files baked into the image
COPY data/ /app/data/

# Bring the pre-built virtual environment from the builder stage
COPY --from=builder /app/.venv /app/.venv

# Application source
COPY app/ ./app/

# Trained model weights.
# In production these are baked into the image.
# Override by mounting a volume: -v ./models:/app/models
COPY models/ ./models/

# Training and utility scripts (available for ad-hoc runs inside the container)
COPY scripts/ ./scripts/

# Entrypoint script
COPY entrypoint.sh ./
RUN chmod +x entrypoint.sh

# Make the venv the active Python environment
ENV PATH="/app/.venv/bin:$PATH"
# Ensure Python output is sent straight to the container logs
ENV PYTHONUNBUFFERED=1
# Do not write .pyc files inside the container
ENV PYTHONDONTWRITEBYTECODE=1
# Allow `from app.xxx import …` without installing the package
ENV PYTHONPATH=/app

EXPOSE 8000

ENTRYPOINT ["./entrypoint.sh"]
