from sqlalchemy import Column, BigInteger, Integer, Boolean, Float, DateTime, Text
from sqlalchemy.dialects.postgresql import JSONB
from geoalchemy2 import Geography
from models.road import Base


class TrafficJam(Base):
    __tablename__ = "traffic_jams"

    id = Column(BigInteger, primary_key=True)
    external_ids = Column(JSONB, nullable=False)
    event_time = Column(DateTime(timezone=True))
    ingested_at = Column(DateTime(timezone=True), nullable=False)
    first_seen = Column(DateTime(timezone=True))
    last_seen = Column(DateTime(timezone=True))
    jam_line_geog = Column(Geography(geometry_type='LINESTRING', srid=4326))
    city = Column(Text)
    street_name = Column(Text)
    road_number = Column(Text)
    road_type_code = Column(Text)
    delay_seconds = Column(Float)
    length_m = Column(Float)
    speed_kmh = Column(Float)
    speed_normal_kmh = Column(Float)
    severity = Column(Text)
    quality_score = Column(Integer)
    raw = Column(JSONB, nullable=False)
    segment_id = Column(BigInteger)


class Accident(Base):
    __tablename__ = "accidents"

    id = Column(BigInteger, primary_key=True)
    external_ids = Column(JSONB, nullable=False)
    event_time = Column(DateTime(timezone=True))
    ingested_at = Column(DateTime(timezone=True), nullable=False)
    first_seen = Column(DateTime(timezone=True))
    last_seen = Column(DateTime(timezone=True))
    location_geog = Column(Geography(geometry_type='POINT', srid=4326))
    city = Column(Text)
    street_name = Column(Text)
    road_number = Column(Text)
    road_type_code = Column(Text)
    accident_type = Column(Text)
    accident_subtype = Column(Text)
    cause_primary = Column(Text)
    cause_secondary = Column(Text)
    severity = Column(Text)
    fatalities_count = Column(Integer)
    serious_injuries = Column(Integer)
    minor_injuries = Column(Integer)
    persons_involved = Column(Integer)
    vehicles_involved = Column(Integer)
    damage_czk = Column(Integer)
    damage_category = Column(Text)
    weather_condition = Column(Text)
    road_surface = Column(Text)
    light_condition = Column(Text)
    road_condition = Column(Text)
    alcohol_involved = Column(Boolean)
    drugs_involved = Column(Boolean)
    alcohol_level = Column(Float)
    quality_score = Column(Integer)
    raw = Column(JSONB, nullable=False)
    segment_id = Column(BigInteger)


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(BigInteger, primary_key=True)
    external_ids = Column(JSONB, nullable=False)
    ingested_at = Column(DateTime(timezone=True), nullable=False)
    first_seen = Column(DateTime(timezone=True))
    last_seen = Column(DateTime(timezone=True))
    location_geog = Column(Geography(geometry_type='POINT', srid=4326))
    city = Column(Text)
    street_name = Column(Text)
    road_number = Column(Text)
    road_type_code = Column(Text)
    alert_type = Column(Text)
    alert_subtype = Column(Text)
    severity = Column(Text)
    description = Column(Text)
    quality_score = Column(Integer)
    active = Column(Boolean)
    raw = Column(JSONB, nullable=False)
    segment_id = Column(BigInteger)


class Restriction(Base):
    __tablename__ = "restrictions"

    id = Column(BigInteger, primary_key=True)
    external_ids = Column(JSONB, nullable=False)
    external_version = Column(Integer)
    event_time = Column(DateTime(timezone=True))
    ingested_at = Column(DateTime(timezone=True), nullable=False)
    valid_from = Column(DateTime(timezone=True))
    valid_to = Column(DateTime(timezone=True))
    first_seen = Column(DateTime(timezone=True))
    last_seen = Column(DateTime(timezone=True))
    location_point_geog = Column(Geography(geometry_type='POINT', srid=4326))
    location_line_geog = Column(Geography(geometry_type='LINESTRING', srid=4326))
    city = Column(Text)
    street_name = Column(Text)
    road_number = Column(Text)
    road_type_code = Column(Text)
    km_from = Column(Float)
    km_to = Column(Float)
    direction = Column(Text)
    restriction_type = Column(Text)
    restriction_subtype = Column(Text)
    urgency = Column(Text)
    probability = Column(Text)
    severity = Column(Text)
    status = Column(Text)
    max_speed_kmh = Column(Integer)
    description_cs = Column(Text)
    quality_score = Column(Integer)
    raw = Column(JSONB, nullable=False)
    segment_id = Column(BigInteger)

