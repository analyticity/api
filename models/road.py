from sqlalchemy import Column, BigInteger, Integer, Text
from geoalchemy2 import Geography
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class RoadSegment(Base):
    __tablename__ = "road_segments"

    id = Column(BigInteger, primary_key=True)
    osm_id = Column(BigInteger)
    geog = Column(Geography(geometry_type='LINESTRING', srid=4326), nullable=False)
    name = Column(Text)
    road_ref = Column(Text)
    road_class = Column(Text, nullable=False)
    city = Column(Text)
    max_speed = Column(Integer)

