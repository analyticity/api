import csv
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from shapely import wkb
from core.logging_config import get_logger

logger = get_logger(__name__)

EXAMPLE_DATA_DIR = Path(__file__).parent.parent / "example_data_from_database"


class ExampleDataLoader:
    """Loads example data from CSV files as fallback when database is unavailable"""

    @staticmethod
    def _parse_value(value: str, column_name: str) -> Any:
        """Parse CSV value to appropriate Python type"""
        if value == "NULL" or value == "":
            return None

        # Check if column contains datetime data
        datetime_indicators = ["time", "date", "_seen", "_from", "_to", "_at"]
        is_datetime_column = any(indicator in column_name.lower() for indicator in datetime_indicators)

        if is_datetime_column:
            try:
                # PostgreSQL exports timestamps with space: "2025-01-12 19:10:00+00"
                # or with microseconds: "2026-04-10 04:32:28.199697+00"
                # Replace space with T for ISO format compatibility
                iso_value = value.replace(" ", "T")
                # Fix timezone format: +00 -> +00:00
                if iso_value.endswith("+00"):
                    iso_value = iso_value[:-3] + "+00:00"
                dt = datetime.fromisoformat(iso_value)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except (ValueError, AttributeError) as e:
                logger.warning(f"Failed to parse datetime '{value}' in column '{column_name}': {e}")
                return value

        if value.lower() == "true":
            return True
        if value.lower() == "false":
            return False

        try:
            if "." in value:
                return float(value)
            return int(value)
        except ValueError:
            return value

    @staticmethod
    def _parse_geometry(geom_str: str) -> Optional[List[List[float]]]:
        """Parse PostGIS EWKB geometry to coordinate list [[lng, lat], ...]"""
        if not geom_str or geom_str == "NULL":
            return None

        try:
            geometry = wkb.loads(geom_str, hex=True)

            if geometry.geom_type == 'LineString':
                return [[coord[0], coord[1]] for coord in geometry.coords]
            elif geometry.geom_type == 'Point':
                return [[geometry.x, geometry.y]]
            else:
                logger.warning(f"Unsupported geometry type: {geometry.geom_type}")
                return None

        except Exception as e:
            logger.warning(f"Failed to parse geometry: {e}")
            return None

    @staticmethod
    def load_csv(filename: str) -> List[Dict[str, Any]]:
        """Load CSV file and return list of dictionaries"""
        file_path = EXAMPLE_DATA_DIR / filename

        if not file_path.exists():
            logger.warning(f"Example data file not found: {filename}")
            return []

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                data = []
                for row in reader:
                    parsed_row = {}
                    for key, value in row.items():
                        if key.endswith("_geog") or key == "geog":
                            parsed_row[key] = ExampleDataLoader._parse_geometry(value)
                        else:
                            parsed_row[key] = ExampleDataLoader._parse_value(value, key)
                    data.append(parsed_row)

            logger.info(f"Loaded {len(data)} rows from {filename}")
            return data

        except Exception as e:
            logger.error(f"Error loading {filename}: {e}")
            return []

    @staticmethod
    def get_road_segments(street_names: List[str] = None) -> List[Dict[str, Any]]:
        """Get road segments from example data"""
        segments = ExampleDataLoader.load_csv("example_road_segments.csv")

        if street_names:
            segments = [s for s in segments if s.get("name") in street_names]

        return segments

    @staticmethod
    def get_accidents(
        segment_ids: List[int] = None,
        date_from: datetime = None,
        date_to: datetime = None
    ) -> List[Dict[str, Any]]:
        """Get accidents from example data with optional filters"""
        accidents = ExampleDataLoader.load_csv("example_accidents.csv")

        if segment_ids:
            accidents = [a for a in accidents if a.get("segment_id") in segment_ids]

        if date_from or date_to:
            if date_from and date_from.tzinfo is None:
                date_from = date_from.replace(tzinfo=timezone.utc)
            if date_to and date_to.tzinfo is None:
                date_to = date_to.replace(tzinfo=timezone.utc)

            filtered = []
            for accident in accidents:
                event_time = accident.get("event_time")
                if not event_time:
                    continue

                if isinstance(event_time, datetime) and event_time.tzinfo is None:
                    event_time = event_time.replace(tzinfo=timezone.utc)

                try:
                    if date_from and event_time < date_from:
                        continue
                    if date_to and event_time > date_to:
                        continue
                    filtered.append(accident)
                except TypeError:
                    logger.warning(f"Skipping accident {accident.get('id')} due to datetime comparison error")
                    continue
            accidents = filtered

        return accidents

    @staticmethod
    def get_jams(
        segment_ids: List[int] = None,
        date_from: datetime = None,
        date_to: datetime = None
    ) -> List[Dict[str, Any]]:
        """Get traffic jams from example data with optional filters"""
        jams = ExampleDataLoader.load_csv("example_jams.csv")

        if segment_ids:
            jams = [j for j in jams if j.get("segment_id") in segment_ids]

        if date_from or date_to:
            if date_from and date_from.tzinfo is None:
                date_from = date_from.replace(tzinfo=timezone.utc)
            if date_to and date_to.tzinfo is None:
                date_to = date_to.replace(tzinfo=timezone.utc)

            filtered = []
            for jam in jams:
                event_time = jam.get("event_time")
                if not event_time:
                    continue

                if isinstance(event_time, datetime) and event_time.tzinfo is None:
                    event_time = event_time.replace(tzinfo=timezone.utc)

                try:
                    if date_from and event_time < date_from:
                        continue
                    if date_to and event_time > date_to:
                        continue
                    filtered.append(jam)
                except TypeError:
                    logger.warning(f"Skipping jam {jam.get('id')} due to datetime comparison error")
                    continue
            jams = filtered

        return jams

    @staticmethod
    def get_alerts(
        segment_ids: List[int] = None,
        date_from: datetime = None,
        date_to: datetime = None
    ) -> List[Dict[str, Any]]:
        """Get alerts from example data with optional filters"""
        alerts = ExampleDataLoader.load_csv("example_alerts.csv")

        if segment_ids:
            alerts = [a for a in alerts if a.get("segment_id") in segment_ids]

        if date_from or date_to:
            if date_from and date_from.tzinfo is None:
                date_from = date_from.replace(tzinfo=timezone.utc)
            if date_to and date_to.tzinfo is None:
                date_to = date_to.replace(tzinfo=timezone.utc)

            filtered = []
            for alert in alerts:
                first_seen = alert.get("first_seen")
                last_seen = alert.get("last_seen")

                if isinstance(first_seen, datetime) and first_seen.tzinfo is None:
                    first_seen = first_seen.replace(tzinfo=timezone.utc)
                if isinstance(last_seen, datetime) and last_seen.tzinfo is None:
                    last_seen = last_seen.replace(tzinfo=timezone.utc)

                if not (first_seen or last_seen):
                    continue

                try:
                    if date_from and last_seen and last_seen < date_from:
                        continue
                    if date_to and first_seen and first_seen > date_to:
                        continue
                    filtered.append(alert)
                except TypeError:
                    logger.warning(f"Skipping alert {alert.get('id')} due to datetime comparison error")
                    continue
            alerts = filtered

        return alerts

    @staticmethod
    def get_restrictions(
        segment_ids: List[int] = None,
        date_from: datetime = None,
        date_to: datetime = None
    ) -> List[Dict[str, Any]]:
        """Get restrictions from example data with optional filters"""
        restrictions = ExampleDataLoader.load_csv("example_restrictions.csv")

        if segment_ids:
            restrictions = [r for r in restrictions if r.get("segment_id") in segment_ids]

        if date_from or date_to:
            if date_from and date_from.tzinfo is None:
                date_from = date_from.replace(tzinfo=timezone.utc)
            if date_to and date_to.tzinfo is None:
                date_to = date_to.replace(tzinfo=timezone.utc)

            filtered = []
            for restriction in restrictions:
                valid_from = restriction.get("valid_from")
                valid_to = restriction.get("valid_to")

                if isinstance(valid_from, datetime) and valid_from.tzinfo is None:
                    valid_from = valid_from.replace(tzinfo=timezone.utc)
                if isinstance(valid_to, datetime) and valid_to.tzinfo is None:
                    valid_to = valid_to.replace(tzinfo=timezone.utc)

                if not valid_from and not valid_to:
                    filtered.append(restriction)
                    continue

                try:
                    if date_from and valid_to and valid_to < date_from:
                        continue
                    if date_to and valid_from and valid_from > date_to:
                        continue
                    filtered.append(restriction)
                except TypeError:
                    logger.warning(f"Skipping restriction {restriction.get('id')} due to datetime comparison error")
                    continue
            restrictions = filtered

        return restrictions

