# API Project Structure

FastAPI application for traffic analytics with PostgreSQL + TimescaleDB + PostGIS database.

## Project Overview

This is a FastAPI-based backend providing REST API endpoints for traffic and road data analysis.

### Technology Stack
- **FastAPI** - Modern Python web framework
- **SQLAlchemy** - ORM for database operations
- **PostgreSQL** - Primary database
- **TimescaleDB** - Time-series data extension
- **PostGIS** - Geographic data extension
- **Shapely** - Geometry parsing and manipulation
- **GeoAlchemy2** - SQLAlchemy extension for spatial databases

## Directory Structure

```
api/
├── main.py                          # Application entry point
├── requirements.txt                 # Python dependencies
├── README.md                        # This file
├── RUN.md                          # Runtime instructions
│
├── core/                           # Core application components
│   ├── config.py                   # Configuration settings
│   ├── example_data.py             # Example data loader (fallback mode)
│   ├── logging_config.py           # Logging setup
│   └── middleware.py               # Request/response middleware
│
├── models/                         # Shared database models (SQLAlchemy)
│   ├── __init__.py                # Model exports
│   ├── road.py                    # RoadSegment model + Base
│   └── traffic.py                 # TrafficJam, Accident, Alert, Restriction models
│
├── db/                            # Database connection
│   └── connection_to_db.py        # Database session management
│
├── api/                           # API version routing
│   └── api_v1.py                  # API v1 router aggregation
│
├── modules/                       # Feature modules (domain-driven)
│   ├── map/                       # Map-related endpoints
│   │   ├── router.py             # FastAPI route definitions
│   │   ├── service.py            # Business logic
│   │   ├── schema.py             # Pydantic request/response models
│   │   └── (model.py deprecated) # Models moved to /models
│   │
│   ├── chart/                    # Chart data endpoints (planned)
│   │   ├── router.py
│   │   ├── service.py
│   │   ├── schema.py
│   │   └── model.py
│   │
│   └── admin/                    # Admin endpoints (planned)
│
└── example_data_from_database/   # CSV files for testing without DB
    ├── schema_db.csv
    ├── constraints_db.csv
    ├── example_road_segments.csv
    ├── example_jams.csv
    ├── example_accidents.csv
    ├── example_alerts.csv
    └── example_restrictions.csv
```

## Architecture Patterns

### Module Structure
Each feature module follows a consistent structure:
- `router.py` - API endpoints and request handling
- `service.py` - Service orchestration and automatic fallback logic
- `service_db.py` - Database operations and queries
- `service_examples.py` - Example data operations for fallback mode
- `schema.py` - Pydantic models for validation and serialization

### Database Models
Shared across all modules in `/models`:
- **Road Models** (`road.py`): Road network data
- **Traffic Models** (`traffic.py`): Traffic events and incidents

### Fallback Mode
The application includes automatic fallback to example CSV data when the database is unavailable:
- Configured in `core/example_data.py`
- Enables local development and testing
- Automatically parses PostGIS WKB geometry from CSV files

### Logging & Middleware
- Request/response logging with timing
- Automatic error tracking
- Configured in `core/logging_config.py` and `core/middleware.py`

## Database Schema

### Main Tables
- `road_segments` - Road network segments with geometry
- `traffic_jams` - Traffic congestion events
- `accidents` - Traffic accident records
- `alerts` - Road alerts and warnings
- `restrictions` - Road restrictions and closures

All tables use:
- TimescaleDB for time-series optimization
- PostGIS for geographic data (SRID 4326 - WGS84)

## API Documentation

Interactive API documentation available at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## SQLAlchemy

SQLAlchemy is a Python SQL toolkit and Object-Relational Mapping (ORM) library that:
- Maps database tables to Python classes
- Provides database-agnostic query interface
- Handles connections, transactions, and migrations
- Offers both ORM and Core (SQL Expression Language) layers

In this project, SQLAlchemy is used to:
- Define database models as Python classes
- Query PostgreSQL/PostGIS databases
- Handle geographic data types via GeoAlchemy2 extension

