"""
Create database tables required by the API.

Creates only the tables defined in the SQLAlchemy ORM models:
  - dangerous_road_clusters
  - cluster_accidents

Tables already managed by load_csv_to_db.py (accidents, road_segments)
are also registered in Base.metadata and will be created if missing,
but skipped with no error if they already exist.

Safe to run multiple times — uses CREATE TABLE IF NOT EXISTS internally.

Usage (from api/TrafficJamsBackend/):
    python scripts/create_tables.py

Inside a running Docker container:
    docker exec accidents_api python scripts/create_tables.py
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import inspect, text

from app.database import sync_engine

# Import all models so Base.metadata knows about every table
import app.models  # noqa: F401
from app.database import Base

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

# Tables this script is specifically responsible for
_TARGET_TABLES = ["dangerous_road_clusters", "cluster_accidents"]


def main() -> None:
    log.info("Connecting to: %s", sync_engine.url)

    with sync_engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis;"))
        conn.commit()
        log.info("PostGIS extension ready.")

    inspector = inspect(sync_engine)
    existing = inspector.get_table_names()

    for table in _TARGET_TABLES:
        if table in existing:
            log.info("  %-35s already exists — skipping.", table)
        else:
            log.info("  %-35s will be created.", table)

    # create_all with checkfirst=True skips tables that already exist
    Base.metadata.create_all(sync_engine, checkfirst=True)

    # Verify
    inspector = inspect(sync_engine)
    after = inspector.get_table_names()
    for table in _TARGET_TABLES:
        status = "✓ created" if table in after else "✗ MISSING"
        log.info("  %-35s %s", table, status)

    missing = [t for t in _TARGET_TABLES if t not in after]
    if missing:
        log.error("Some tables were not created: %s", missing)
        sys.exit(1)

    log.info("Done — all required tables exist.")


if __name__ == "__main__":
    main()
