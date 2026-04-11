# Running the Application

## Install Dependencies

```bash
pip install -r requirements.txt
```

## Run Development Server

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## Access Documentation

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **API Root**: http://localhost:8000/
- **Health Check**: http://localhost:8000/health

## Environment Variables

Create a `.env` file in the project root:

```env
# Database configuration
POSTGRES_HOST_BRNO=localhost
POSTGRES_PORT_BRNO=5433
POSTGRES_DB_BRNO=your_database
POSTGRES_USER_BRNO=your_user
POSTGRES_PASSWORD_BRNO=your_password
```

## Fallback Mode

**The API automatically switches to fallback mode if the database is unavailable!**

When running without a database connection:
- API loads example data from `example_data_from_database/` folder
- All endpoints work with mock data
- Perfect for testing and development without database setup
- Status visible at `/health` endpoint

### Testing Fallback Mode

Simply run the app without configuring database credentials:

```bash
# No .env file needed
uvicorn main:app --reload
```

The API will automatically use example data and log:
```
Database connection failed: ... Using example data fallback
```

## Logging

The application logs:
- ✅ All HTTP requests (method, path, client IP)
- ✅ Response status codes
- ✅ Request duration in seconds
- ✅ Database connection status
- ✅ Fallback mode activation
- ✅ Query execution and results count
- ✅ Errors with full stack traces

### Log Format
```
2026-04-11 10:30:45 | INFO     | main | Starting Analyticity API v1.0.0
2026-04-11 10:30:45 | WARNING  | db.connection_to_db | Database connection failed: ... Using example data fallback
2026-04-11 10:30:50 | INFO     | core.middleware | Request started: POST /api/v1/map/street-segments from 127.0.0.1
2026-04-11 10:30:50 | INFO     | modules.map.service | Loaded 10 segments from example data for streets: ['Jihlavská']
2026-04-11 10:30:50 | INFO     | core.middleware | Request completed: POST /api/v1/map/street-segments | Status: 200 | Duration: 0.042s | Client: 127.0.0.1
```

## API Endpoints

### Map Module

#### POST /api/v1/map/street-segments
Get street segments with statistics for specified streets and date range.

**Request Body:**
```json
{
  "street_names": ["Jihlavská", "Úvoz"],
  "date_from": "2026-04-01T00:00:00",
  "date_to": "2026-04-11T23:59:59"
}
```

**Response:**
```json
{
  "segments": [
    {
      "id": 8181,
      "osm_id": 205262250,
      "name": "Jihlavská",
      "road_ref": "602",
      "road_class": "secondary",
      "city": "Brno",
      "max_speed": 50,
      "coordinates": [[16.563631, 49.174137], [16.564209, 49.174157]],
      "statistics": {
        "jams_count": 5,
        "accidents_count": 3,
        "alerts_count": 2,
        "restrictions_count": 1
      }
    }
  ],
  "total_count": 1,
  "date_from": "2026-04-01T00:00:00",
  "date_to": "2026-04-11T23:59:59"
}
```

### Health Check

#### GET /health
Check API and database status.

**Response:**
```json
{
  "status": "healthy",
  "database_available": false
}
```

