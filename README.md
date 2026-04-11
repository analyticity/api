# Analyticity API

FastAPI aplikace pro analytický backend.

## Struktura projektu

```
api/
├── main.py                      # Hlavní vstupní bod aplikace
├── api/
│   └── api_v1.py               # API router pro verzi 1
├── core/
│   └── config.py               # Konfigurace aplikace
├── db/
│   └── connection_to_db.py     # Správa databázových připojení (PostgreSQL)
├── example_data_from_database/  # Ukázková data pro vývoj bez DB
│   ├── schema_db.csv           # Schéma databáze (tabulky, sloupce, typy)
│   ├── constraints_db.csv      # Databázové constrainty (PK, FK, UNIQUE)
│   ├── example_accidents.csv   # Ukázková data - dopravní nehody
│   ├── example_alerts.csv      # Ukázková data - upozornění
│   ├── example_jams.csv        # Ukázková data - dopravní zácpy
│   ├── example_restrictions.csv # Ukázková data - dopravní omezení
│   └── example_road_segments.csv # Ukázková data - silniční segmenty
└── modules/
    ├── admin/                   # Modul pro administraci (připraveno pro budoucí migraci)
    ├── chart/                   # Modul pro grafy/charty
    │   ├── model.py            # SQLAlchemy modely
    │   ├── router.py           # FastAPI endpointy
    │   ├── schema.py           # Pydantic schémata
    │   └── service.py          # Byznys logika
    └── map/                     # Modul pro mapové funkcionality
        ├── model.py            # SQLAlchemy modely
        ├── router.py           # FastAPI endpointy
        ├── schema.py           # Pydantic schémata
        └── service.py          # Byznys logika
```

### Popis složek

#### `main.py`
Hlavní vstupní bod FastAPI aplikace. Vytváří instanci aplikace a registruje API routery.

#### `api/`
Obsahuje definice API routerů pro různé verze API.
- `api_v1.py` - Agreguje všechny moduly do API verze 1

#### `core/`
Základní konfigurace a nastavení aplikace.
- `config.py` - Konfigurační soubory (environment variables, settings)
- `logging_config.py` - Konfigurace logování pro celou aplikaci
- `middleware.py` - HTTP middleware (LoggingMiddleware pro request/response logging)
- `example_data.py` - **ExampleDataLoader** - univerzální fallback systém pro načítání example dat když DB není dostupná

#### `db/`
Správa databázových připojení.
- `connection_to_db.py` - PostgreSQL připojení (momentálně s psycopg2)

#### `modules/`
Modulární struktura aplikace. Každý modul představuje samostatnou funkční oblast:

**Struktura modulů:**
Každý modul obsahuje:
- `model.py` - SQLAlchemy databázové modely
- `router.py` - FastAPI endpointy a HTTP routing
- `schema.py` - Pydantic schémata pro validaci a serializaci
- `service.py` - Byznys logika a datové operace

**Současné moduly:**
- `admin/` - Administrační funkce (připraveno pro migraci z AdminBackend)
- `chart/` - Funkce pro práci s grafy a vizualizacemi
- `map/` - Funkce pro práci s mapovými daty

## Architektura

Projekt používá **modulární architekturu** s následujícími vrstvami:

1. **Router Layer** (`router.py`) - HTTP endpointy, request/response handling
2. **Schema Layer** (`schema.py`) - Validace dat pomocí Pydantic
3. **Service Layer** (`service.py`) - Byznys logika
4. **Model Layer** (`model.py`) - Databázové modely a ORM

## Klíčové funkce

### 🔄 Automatický Fallback Systém
- API automaticky přepne na example data pokud databáze není dostupná
- Žádná konfigurace nutná - funguje out-of-the-box
- Perfektní pro vývoj a testování bez databáze
- Implementováno v `core/example_data.py` jako univerzální systém

### 📊 Komplexní Logging
- **Request/Response logging** - metoda, path, status, duration, client IP
- **Database status** - připojení/fallback mode
- **Error tracking** - full stack traces
- **Query logging** - počty načtených záznamů
- Implementováno pomocí `LoggingMiddleware` v `core/middleware.py`

### 🗺️ PostGIS Podpora
- Automatická konverze PostGIS geometrie na coordinate arrays
- Format `[[lng, lat], ...]` kompatibilní s frontend mapovými knihovnami
- Podpora LineString, Point geometrií

### 📈 Časové řady (TimescaleDB)
- Efektivní filtrování podle časových rozsahů
- Statistiky počítané na úrovni databáze
- Podpora pro event_time, first_seen/last_seen, valid_from/valid_to

## Technologie

- **FastAPI** - Moderní web framework pro Python API
- **PostgreSQL** - Relační databáze
- **TimescaleDB** - Rozšíření PostgreSQL pro časové řady
- **PostGIS** - Rozšíření PostgreSQL pro geografická/prostorová data
- **psycopg2** - PostgreSQL adapter pro Python
- **SQLAlchemy** - ORM (Object-Relational Mapping) - mapování databázových tabulek na Python třídy
- **Pydantic** - Validace dat a serializace

## Datový model

Databáze obsahuje dopravní a geografická data z různých zdrojů (Waze, Policie ČR, atd.).

### Hlavní tabulky

#### `accidents` - Dopravní nehody
- **Zdroj:** Policie ČR
- **Klíčové atributy:** poloha (PostGIS geography), typ nehody, závažnost, počet zraněných/obětí, škoda, počasí
- **Vazby:** `segment_id` → `road_segments`
- **Časové údaje:** TimescaleDB - `event_time`, `first_seen`, `last_seen`, `ingested_at`

#### `traffic_jams` - Dopravní zácpy
- **Zdroj:** Waze
- **Klíčové atributy:** linie zácpy (PostGIS LineString), rychlost, délka, zpoždění, závažnost (light/moderate/heavy/standstill)
- **Vazby:** `segment_id` → `road_segments`, propojení s `alerts` přes `external_ids`
- **Časové údaje:** TimescaleDB - `event_time`, `first_seen`, `last_seen`, `ingested_at`

#### `alerts` - Dopravní upozornění
- **Zdroj:** Waze
- **Klíčové atributy:** typ alertu (HAZARD, JAM), podtyp (výmol, nehoda, auto na krajnici), závažnost, aktivní/neaktivní
- **Vazby:** `segment_id` → `road_segments`
- **Časové údaje:** TimescaleDB - `first_seen`, `last_seen`, `ingested_at`

#### `restrictions` - Dopravní omezení
- **Zdroj:** Waze, NDIC
- **Klíčové atributy:** bod nebo linie (PostGIS), typ omezení (road_closed, atd.), platnost od-do, rychlostní limit
- **Vazby:** `segment_id` → `road_segments`
- **Časové údaje:** TimescaleDB - `event_time`, `valid_from`, `valid_to`, `first_seen`, `last_seen`

#### `road_segments` - Silniční segmenty
- **Zdroj:** OpenStreetMap
- **Klíčové atributy:** geometrie (PostGIS LineString), název ulice, třída silnice, maximální rychlost
- **Vazby:** Referenční tabulka pro všechny dopravní události
- **OSM ID:** `osm_id` - vazba na OpenStreetMap data

#### `event_links` - Propojení událostí
- Umožňuje propojení různých typů událostí (accidents ↔ jams, alerts ↔ restrictions)
- **Atributy:** `source_type`, `source_id`, `target_type`, `target_id`, `link_type`, `confidence`

### Společné vlastnosti

**Všechny hlavní tabulky obsahují:**
- `external_ids` (JSONB) - ID z externích zdrojů (Waze UUID, Policie ČR kódy)
- `location_geog` nebo `jam_line_geog` (PostGIS geography) - geografická poloha
- `city`, `street_name`, `road_number`, `road_type_code` - lokalizační údaje
- `quality_score` - hodnocení kvality dat (0-100)
- `raw` (JSONB) - kompletní surová data z API
- `segment_id` - vazba na `road_segments`

**TimescaleDB časové sloupce:**
- `event_time` - čas události
- `ingested_at` - čas příjmu dat do DB
- `first_seen` - první detekce události
- `last_seen` - poslední aktualizace události

## Poznámky

- Složka `AdminBackend/` obsahuje původní backend a bude postupně migrována do `modules/admin/`
- Projekt je připraven na rozšíření o další moduly podle stejného vzoru
- Pro vývoj bez databáze použijte data v `example_data_from_database/`
