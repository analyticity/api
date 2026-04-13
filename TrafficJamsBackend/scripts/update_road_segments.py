"""
Download road segments for Brno from OpenStreetMap and load them into
the road_segments PostgreSQL table.

Replaces all existing rows on each run (TRUNCATE + INSERT) so re-running
always gives a fresh, consistent snapshot of the OSM data.

Usage (from api/TrafficJamsBackend/):
    python scripts/update_road_segments.py
    python scripts/update_road_segments.py --place "Brno, Czechia" --batch-size 500
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import osmnx as ox
from sqlalchemy import create_engine, text

sys.path.insert(0, str(Path(__file__).parent.parent))
from app.config import get_settings

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)


def _parse_max_speed(value) -> int | None:
    """Convert OSM maxspeed strings like '50', '50 mph', 'CZ:urban' to int km/h."""
    if value is None:
        return None
    # OSM sometimes returns a list when multiple values exist — take the first
    if isinstance(value, list):
        value = value[0]
    try:
        return int(str(value).split()[0])
    except (ValueError, AttributeError):
        return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Load OSM road segments into road_segments table.")
    parser.add_argument("--place", default="Brno, Czechia")
    parser.add_argument("--batch-size", type=int, default=1000)
    args = parser.parse_args()

    settings = get_settings()
    engine = create_engine(settings.database_url_sync, echo=False)

    # ── 1. Download from OSM ──────────────────────────────────────────────────
    log.info("Downloading road network for '%s' from OpenStreetMap…", args.place)
    graph = ox.graph_from_place(args.place, network_type="drive")
    _, edges = ox.graph_to_gdfs(graph)
    osm_data = edges.reset_index()
    log.info("Downloaded %d road segments.", len(osm_data))

    # ── 2. Build rows ─────────────────────────────────────────────────────────
    rows = []
    for _, row in osm_data.iterrows():
        name = row.get("name")
        if isinstance(name, list):
            name = name[0]

        rows.append({
            "osm_id":     int(row["osmid"]) if "osmid" in row.index else None,
            "name":       str(name)[:255] if name else None,
            "road_ref":   str(row["ref"])[:50] if "ref" in row.index and row["ref"] is not None else None,
            "road_class": str(row["highway"])[:50] if "highway" in row.index else None,
            "max_speed":  _parse_max_speed(row.get("maxspeed")),
            "city":       args.place.split(",")[0].strip(),
            "geog":       row["geometry"].wkb_hex,
        })

    # ── 3. Truncate existing data and insert fresh rows ───────────────────────
    insert_sql = text("""
        INSERT INTO road_segments (osm_id, name, road_ref, road_class, max_speed, city, geog)
        VALUES (:osm_id, :name, :road_ref, :road_class, :max_speed, :city,
                ST_GeomFromWKB(decode(:geog, 'hex'), 4326))
    """)

    with engine.begin() as conn:
        conn.execute(text("TRUNCATE TABLE road_segments RESTART IDENTITY"))
        log.info("Existing road segments cleared.")

        inserted = 0
        for start in range(0, len(rows), args.batch_size):
            batch = rows[start: start + args.batch_size]
            conn.execute(insert_sql, batch)
            inserted += len(batch)
            log.info("  … %d / %d rows inserted.", inserted, len(rows))

    log.info("Done — %d road segments written to road_segments table.", inserted)


if __name__ == "__main__":
    main()