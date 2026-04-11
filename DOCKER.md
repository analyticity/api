# Docker Deployment Guide

## Overview

The Analyticity API is containerized using Docker and can be deployed with Docker Compose.

## Services

### API Service
- **Image**: Python 3.13 slim
- **Port**: 8000
- **Auto-reload**: Enabled (development)
- **Volumes**: Source code mounted for hot-reload

### Database Service
- **Image**: timescale/timescaledb-ha:pg16
- **Extensions**: TimescaleDB + PostGIS
- **Port**: 5432
- **Volumes**: Persistent data storage

## Quick Start

### 1. Start Services

```bash
docker-compose up -d
```

This will:
- Build the API image
- Pull TimescaleDB image
- Create network
- Start both containers
- Create persistent volume for database

### 2. Check Status

```bash
# View running containers
docker-compose ps

# View API logs
docker-compose logs -f api

# View database logs
docker-compose logs -f db
```

### 3. Access API

- **API**: http://localhost:8000
- **Swagger**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **Health**: http://localhost:8000/health

### 4. Stop Services

```bash
# Stop containers (keep data)
docker-compose down

# Stop and remove data
docker-compose down -v
```

## Configuration

### Environment Variables

Create `.env` file in project root:

```env
# Database
POSTGRES_HOST_BRNO=db
POSTGRES_PORT_BRNO=5432
POSTGRES_DB_BRNO=analyticity
POSTGRES_USER_BRNO=postgres
POSTGRES_PASSWORD_BRNO=postgres
```

Or use defaults from `docker-compose.yml`.

### Custom Port Mapping

Edit `docker-compose.yml`:

```yaml
services:
  api:
    ports:
      - "3000:8000"  # Change 3000 to your preferred port
  
  db:
    ports:
      - "5433:5432"  # Change 5433 to your preferred port
```

## Database Setup

### Initial Setup

TimescaleDB and PostGIS extensions are automatically loaded.

To create tables and load data, connect to the database:

```bash
# Access database container
docker-compose exec db psql -U postgres -d analyticity

# Or from host (if psql installed)
psql -h localhost -p 5432 -U postgres -d analyticity
```

### Enable Extensions

```sql
CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE EXTENSION IF NOT EXISTS postgis;
```

## Development Workflow

### Hot Reload

Code changes are automatically detected:

```bash
# Edit code in your editor
# Docker container detects changes
# Uvicorn reloads automatically
```

### Rebuild After Dependency Changes

```bash
# If you modify requirements.txt
docker-compose up -d --build
```

### View Logs

```bash
# All services
docker-compose logs -f

# API only
docker-compose logs -f api

# Database only
docker-compose logs -f db
```

## Production Deployment

### Build Production Image

Update `docker-compose.yml` or create `docker-compose.prod.yml`:

```yaml
services:
  api:
    build:
      context: .
      dockerfile: Dockerfile
    command: uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
    volumes: []  # Remove volume mount
    restart: always
```

### Run Production

```bash
docker-compose -f docker-compose.prod.yml up -d
```

## Troubleshooting

### Container Won't Start

```bash
# Check logs
docker-compose logs api

# Rebuild
docker-compose up -d --build --force-recreate
```

### Database Connection Issues

```bash
# Check if database is running
docker-compose ps

# Test connection
docker-compose exec db psql -U postgres -d analyticity -c "SELECT version();"

# Check API logs
docker-compose logs api | grep -i "database"
```

### Port Already in Use

```bash
# Check what's using port 8000
lsof -i :8000

# Change port in docker-compose.yml
# ports: - "8001:8000"
```

## Cleanup

### Remove Containers

```bash
docker-compose down
```

### Remove Containers and Volumes

```bash
docker-compose down -v
```

### Remove Images

```bash
docker-compose down --rmi all -v
```

## Notes

- Database data persists in Docker volume `postgres_data`
- API runs with hot-reload in development mode
- Fallback mode works even if database is not running
- AdminBackend folder is excluded via `.dockerignore`

