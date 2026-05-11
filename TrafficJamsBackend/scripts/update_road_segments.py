"""
Load road segments into the road_segments PostgreSQL table.

Two modes:
  --csv PATH   Read from a local CSV file (e.g. brno_roads_updated.csv).
               CSV must have columns: osm_id, name, road_ref, road_class,
               max_speed, city, geog (WKB hex).
  (no --csv)   Download fresh data from OpenStreetMap via osmnx.

Replaces all existing rows on each run (TRUNCATE + INSERT).

Usage (from api/TrafficJamsBackend/):
    python scripts/update_road_segments.py --csv brno_roads_updated.csv
    python scripts/update_road_segments.py --place "Brno, Czechia"
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text

sys.path.insert(0, str(Path(__file__).parent.parent))
from app.config import get_settings

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

_INSERT_SQL = text("""
    INSERT INTO road_segments (osm_id, name, road_ref, road_class, max_speed, city, geog)
    VALUES (:osm_id, :name, :road_ref, :road_class, :max_speed, :city,
            ST_GeomFromWKB(decode(:geog, 'hex'), 4326))
""")


def _parse_first(value) -> str | None:
    """
    OSMnx sometimes stores multiple values as a Python list literal string,
    e.g. osm_id='[54754873, 332341726]' or name="['Za vodojemem', 'Jámy']".
    Take the first element in that case.
    """
    if value is None:
        return None
    s = str(value).strip()
    if s.startswith("["):
        try:
            import ast
            parsed = ast.literal_eval(s)
            if isinstance(parsed, list) and parsed:
                return str(parsed[0])
        except (ValueError, SyntaxError):
            pass
    return s


def _rows_from_csv(csv_path: str) -> list[dict]:
    log.info("Reading road segments from %s …", csv_path)
    df = pd.read_csv(csv_path, low_memory=False)
    df.replace("NULL", None, inplace=True)
    df = df.astype(object).where(pd.notna(df), other=None)
    log.info("  %d rows loaded from CSV.", len(df))

    rows = []
    for _, row in df.iterrows():
        osm_id_raw = _parse_first(row.get("osm_id"))
        rows.append({
            "osm_id":     int(osm_id_raw) if osm_id_raw is not None else None,
            "name":       _parse_first(row.get("name")),
            "road_ref":   _parse_first(row.get("road_ref")),
            "road_class": _parse_first(row.get("road_class")),
            "max_speed":  int(float(_parse_first(row.get("max_speed")))) if pd.notna(row.get("max_speed")) else None,
            "city":       row.get("city"),
            "geog":       row.get("geog"),
        })
    return rows


def _rows_from_osm(place: str) -> list[dict]:
    import osmnx as ox

    def _parse_max_speed(value) -> int | None:
        if value is None:
            return None
        if isinstance(value, list):
            value = value[0]
        try:
            return int(str(value).split()[0])
        except (ValueError, AttributeError):
            return None

    log.info("Downloading road network for '%s' from OpenStreetMap…", place)
    graph = ox.graph_from_place(place, network_type="drive")
    _, edges = ox.graph_to_gdfs(graph)
    osm_data = edges.reset_index()
    log.info("  %d segments downloaded.", len(osm_data))

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
            "city":       place.split(",")[0].strip(),
            "geog":       row["geometry"].wkb_hex,
        })
    return rows


def _insert(engine, rows: list[dict], batch_size: int) -> None:
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE TABLE road_segments RESTART IDENTITY"))
        log.info("Existing road segments cleared.")
        inserted = 0
        for start in range(0, len(rows), batch_size):
            conn.execute(_INSERT_SQL, rows[start: start + batch_size])
            inserted += len(rows[start: start + batch_size])
            log.info("  … %d / %d rows inserted.", inserted, len(rows))
    log.info("Done — %d road segments written to road_segments table.", inserted)


def main() -> None:
    parser = argparse.ArgumentParser(description="Load road segments into the road_segments table.")
    parser.add_argument("--csv", metavar="PATH", default=None,
                        help="Load from a local CSV file instead of downloading from OSM")
    parser.add_argument("--place", default="Brno, Czechia",
                        help="OSM place name to download (ignored when --csv is used)")
    parser.add_argument("--batch-size", type=int, default=1000)
    args = parser.parse_args()

    engine = create_engine(get_settings().database_url_sync, echo=False)

    rows = _rows_from_csv(args.csv) if args.csv else _rows_from_osm(args.place)
    _insert(engine, rows, args.batch_size)


if __name__ == "__main__":
    main()