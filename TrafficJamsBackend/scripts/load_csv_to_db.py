"""
Load accidents_data.csv and road_segments.csv into PostgreSQL.

The DB schema is derived from the CSV columns — exactly matching the
`accidents` ORM model and the road_segments table read by the CSV repository.

Usage (from api/TrafficJamsBackend/):
    python scripts/load_csv_to_db.py
    python scripts/load_csv_to_db.py --accidents-csv ../../accidents_data.csv
    python scripts/load_csv_to_db.py --roads-csv ../../brno_roads_updated.csv
    python scripts/load_csv_to_db.py --accidents-csv a.csv --roads-csv r.csv --batch-size 500
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text

# Make `app.*` importable when running from the repo root or from this dir
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import get_settings

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

# ── Columns that exist in the CSV but are NOT in the accidents DB table ────────
_ACCIDENTS_CSV_EXTRA_COLS = {"external_ids", "first_seen", "last_seen", "vehicle_types", "raw"}

# ── Accidents table DDL ────────────────────────────────────────────────────────
_ACCIDENTS_DDL = """
CREATE TABLE IF NOT EXISTS accidents (
    id                  VARCHAR(50)  PRIMARY KEY,
    event_time          TIMESTAMPTZ,
    ingested_at         TIMESTAMPTZ,
    city                VARCHAR(100),
    street_name         VARCHAR(255),
    road_number         VARCHAR(50),
    road_type_code      VARCHAR(50),
    accident_type       VARCHAR(255),
    accident_subtype    VARCHAR(255),
    cause_primary       VARCHAR(255),
    cause_secondary     VARCHAR(255),
    severity            VARCHAR(50),
    fatalities_count    INTEGER,
    serious_injuries    INTEGER,
    minor_injuries      INTEGER,
    persons_involved    INTEGER,
    vehicles_involved   INTEGER,
    damage_czk          BIGINT,
    damage_category     VARCHAR(50),
    weather_condition   VARCHAR(255),
    road_surface        VARCHAR(255),
    light_condition     VARCHAR(255),
    road_condition      VARCHAR(255),
    alcohol_involved    BOOLEAN,
    drugs_involved      BOOLEAN,
    alcohol_level       FLOAT,
    quality_score       FLOAT,
    segment_id          INTEGER,
    location_geog       GEOMETRY(POINT, 4326)
);
"""

# ── Road segments table DDL (mirrors the CSV schema) ──────────────────────────
_ROAD_SEGMENTS_DDL = """
CREATE TABLE IF NOT EXISTS road_segments (
    id          SERIAL PRIMARY KEY,
    osm_id      BIGINT,
    name        VARCHAR(255),
    road_ref    VARCHAR(50),
    road_class  VARCHAR(50),
    max_speed   INTEGER,
    city        VARCHAR(100),
    geog        GEOMETRY(LINESTRING, 4326)
);
"""


def _ensure_postgis(engine) -> None:
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis;"))
    log.info("PostGIS extension ready.")


def _create_tables(engine) -> None:
    with engine.begin() as conn:
        conn.execute(text(_ACCIDENTS_DDL))
        conn.execute(text(_ROAD_SEGMENTS_DDL))
    log.info("Tables created (or already exist).")


def _load_accidents(engine, csv_path: str, batch_size: int) -> None:
    log.info("Reading accidents from %s …", csv_path)
    df = pd.read_csv(csv_path, low_memory=False)
    log.info("  %d rows loaded from CSV.", len(df))

    # Drop columns not present in the DB table
    df.drop(columns=[c for c in _ACCIDENTS_CSV_EXTRA_COLS if c in df.columns], inplace=True)

    # Replace "NULL" strings then cast to object dtype so that NaN in
    # integer-like float columns becomes Python None (not float nan).
    # Without astype(object), to_dict() still returns float nan for columns
    # like persons_involved, which psycopg2 cannot insert into INTEGER.
    df.replace("NULL", None, inplace=True)
    df = df.astype(object).where(pd.notna(df), other=None)

    # Build the upsert — ON CONFLICT DO NOTHING so re-running is safe
    cols = list(df.columns)
    col_list = ", ".join(f'"{c}"' for c in cols)
    placeholders = ", ".join(f":{c}" for c in cols)
    upsert_sql = text(
        f"INSERT INTO accidents ({col_list}) VALUES ({placeholders}) "
        "ON CONFLICT (id) DO NOTHING"
    )

    inserted = 0
    with engine.begin() as conn:
        for start in range(0, len(df), batch_size):
            batch = df.iloc[start : start + batch_size]
            conn.execute(upsert_sql, batch.to_dict(orient="records"))
            inserted += len(batch)
            log.info("  … %d / %d rows inserted.", inserted, len(df))

    log.info("Accidents: %d rows written to DB.", inserted)


def _first_list_item(s: str) -> str:
    """Return the first element of a Python-list-style string ("[a, b]")."""
    inner = s.strip("[]").split(",", 1)[0].strip()
    return inner.strip("'\"").strip()


def _normalize_int(value):
    """Coerce a value into an int or None.

    Some rows in brno_roads_updated.csv contain list-like strings such as
    "[54754873, 332341726]" or "['40', '50']" for segments merged from
    multiple OSM ways — keep the first value in that case.
    """
    if value is None:
        return None
    if isinstance(value, float):
        if value != value:  # NaN
            return None
        return int(value)
    if isinstance(value, int):
        return value
    s = str(value).strip()
    if not s or s.upper() in {"NULL", "NAN"}:
        return None
    if s.startswith("["):
        s = _first_list_item(s)
        if not s:
            return None
    try:
        return int(float(s))
    except (TypeError, ValueError):
        return None


def _normalize_str(value):
    """Coerce a value into a single string or None.

    Merged-segment rows store list-like strings such as
    "['Poříčí', 'Opuštěná']" — keep the first name.
    """
    if value is None:
        return None
    if isinstance(value, float) and value != value:  # NaN
        return None
    s = str(value).strip()
    if not s or s.upper() in {"NULL", "NAN"}:
        return None
    if s.startswith("["):
        s = _first_list_item(s)
        if not s:
            return None
    return s


def _load_road_segments(engine, csv_path: str, batch_size: int) -> None:
    log.info("Reading road segments from %s …", csv_path)
    df = pd.read_csv(csv_path, low_memory=False)
    raw_count = len(df)
    log.info("  %d rows loaded from CSV.", raw_count)

    df.replace("NULL", None, inplace=True)

    # Coerce numeric columns — handles ints, floats, NaN and list-like strings
    for int_col in ("osm_id", "max_speed"):
        if int_col in df.columns:
            df[int_col] = df[int_col].apply(_normalize_int)
    # Coerce string columns — collapses list-like values to the first item
    for str_col in ("name", "road_ref", "road_class", "city"):
        if str_col in df.columns:
            df[str_col] = df[str_col].apply(_normalize_str)

    # Drop rows we cannot insert at all (missing osm_id or geometry)
    if "osm_id" in df.columns:
        before = len(df)
        df = df[df["osm_id"].notna()].copy()
        dropped = before - len(df)
        if dropped:
            log.info("  dropped %d rows with invalid/missing osm_id.", dropped)
    if "geog" in df.columns:
        before = len(df)
        df = df[df["geog"].notna() & (df["geog"].astype(str).str.len() > 0)].copy()
        dropped = before - len(df)
        if dropped:
            log.info("  dropped %d rows with missing geometry.", dropped)

    # Final NaN sweep: any remaining numpy NaN must become Python None so
    # psycopg2 sends NULL instead of 'NaN'::float.
    df = df.astype(object).where(pd.notna(df), other=None)

    # The CSV geometry column is named "geog" and contains WKB hex.
    # We store it as native PostGIS geometry via ST_GeomFromWKB.
    cols = [c for c in df.columns if c != "geog"]
    col_list = ", ".join(f'"{c}"' for c in cols)
    placeholders = ", ".join(f":{c}" for c in cols)
    upsert_sql = text(
        f"INSERT INTO road_segments ({col_list}, geog) "
        f"VALUES ({placeholders}, ST_GeomFromWKB(decode(:geog, 'hex'), 4326)) "
        "ON CONFLICT DO NOTHING"
    )

    inserted = 0
    with engine.begin() as conn:
        for start in range(0, len(df), batch_size):
            batch = df.iloc[start : start + batch_size]
            conn.execute(upsert_sql, batch.to_dict(orient="records"))
            inserted += len(batch)
            log.info("  … %d / %d rows inserted.", inserted, len(df))

    log.info("Road segments: %d rows written to DB (skipped %d).",
             inserted, raw_count - inserted)


def main() -> None:
    settings = get_settings()

    parser = argparse.ArgumentParser(description="Load CSV data into PostgreSQL.")
    parser.add_argument("--accidents-csv", default=settings.accidents_csv_path,
                        help="Path to accidents CSV (default: from .env)")
    parser.add_argument("--roads-csv", default=settings.road_segments_csv_path,
                        help="Path to road segments CSV (default: from .env)")
    parser.add_argument("--batch-size", type=int, default=1000,
                        help="Rows per INSERT batch (default: 1000)")
    parser.add_argument("--skip-accidents", action="store_true",
                        help="Skip loading accidents (load only road segments)")
    parser.add_argument("--skip-roads", action="store_true",
                        help="Skip loading road segments (load only accidents)")
    args = parser.parse_args()

    engine = create_engine(settings.database_url_sync, echo=False)

    _ensure_postgis(engine)
    _create_tables(engine)

    if not args.skip_accidents:
        _load_accidents(engine, args.accidents_csv, args.batch_size)
    if not args.skip_roads:
        _load_road_segments(engine, args.roads_csv, args.batch_size)

    log.info("Done.")


if __name__ == "__main__":
    main()
