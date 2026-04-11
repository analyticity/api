# Analyticity API

FastAPI application for traffic data analytics backend with PostgreSQL + TimescaleDB + PostGIS support.

## 🚀 Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Start server
python main.py
```

API runs on `http://localhost:8000`
- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc

## 📁 Project Structure

For detailed project structure documentation see [STRUCTURE.md](STRUCTURE.md)

```
api/
├── main.py                          # Application entry point
├── core/                           # Configuration, logging, middleware
├── models/                         # Shared database models
├── db/                            # Database connections
├── api/                           # API routing
├── modules/                       # Feature modules (map, chart, admin)
└── example_data_from_database/    # CSV data for testing
```

## 🔑 Key Features

### 🔄 Automatic Fallback
API automatically switches to example data when database is unavailable.

### 📊 Comprehensive Logging
All requests, response times, errors and database operations are logged.

### 🗺️ PostGIS Support
Automatic geometry conversion to `[[lng, lat], ...]` format for frontend.

## 🛠 Technologies

- **FastAPI** - Web framework
- **SQLAlchemy** - ORM for database operations
- **PostgreSQL** + **TimescaleDB** + **PostGIS** - Database
- **Shapely** - Geometry parsing
- **Pydantic** - Data validation

## 📊 Data Model

Database contains traffic and geographic data from various sources (Waze, Czech Police, OpenStreetMap).

### Main Tables

#### `road_segments` - Road Segments
- **Source:** OpenStreetMap
- **Geometry:** LineString (PostGIS)
- **Key attributes:** street name, road class, max speed, OSM ID

#### `traffic_jams` - Traffic Jams
- **Source:** Waze
- **Geometry:** LineString
- **Key attributes:** speed, length, delay, severity
- **Relationship:** `segment_id` → `road_segments`

#### `accidents` - Traffic Accidents
- **Source:** Czech Police
- **Geometry:** Point
- **Key attributes:** type, severity, injuries count, damage, weather
- **Relationship:** `segment_id` → `road_segments`

#### `alerts` - Traffic Alerts
- **Source:** Waze
- **Geometry:** Point
- **Key attributes:** type (HAZARD, JAM), subtype, active/inactive
- **Relationship:** `segment_id` → `road_segments`

#### `restrictions` - Traffic Restrictions
- **Source:** Waze, NDIC
- **Geometry:** Point or LineString
- **Key attributes:** restriction type, validity period, speed limit
- **Relationship:** `segment_id` → `road_segments`

### Common Properties

**All tables contain:**
- `external_ids` (JSONB) - IDs from external sources
- `quality_score` - data quality rating (0-100)
- `raw` (JSONB) - complete raw data
- `segment_id` - reference to road_segments

**TimescaleDB time columns:**
- `event_time` - event timestamp
- `ingested_at` - data ingestion timestamp
- `first_seen` / `last_seen` - detection and last update timestamps

**PostGIS:**
- All geographic data uses SRID 4326 (WGS84)

## 📚 Documentation

- **[STRUCTURE.md](STRUCTURE.md)** - Detailed project structure and architecture
- **[RUN.md](RUN.md)** - Runtime instructions

## 📝 Notes

- `AdminBackend/` folder contains legacy backend (ignore, will be migrated)
- For development without database use CSV data in `example_data_from_database/`
- Database models are shared in `/models` for use across all modules


