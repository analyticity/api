#########################
#Author: Patrik Haas (xhaasp00)
#########################

from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.sql import func
from sqlalchemy.ext.declarative import declarative_base
from geoalchemy2 import Geometry


Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    passwordhash = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    admintype = Column(String, nullable=False)
    active = Column(Boolean, default=True)
    createdat = Column(DateTime(timezone=True), server_default=func.now())
    updatedat = Column(DateTime(timezone=True), onupdate=func.now())
    town = Column(Integer)

class Town(Base):
    __tablename__ = "towns"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    wazelink = Column(String, nullable=False)
    dbhost = Column(String, nullable=False)
    dbportexternal = Column(Integer, nullable=False)
    dbportinternal = Column(Integer, nullable=False, default=5432)
    dbname = Column(String, nullable=False)
    dbuser = Column(String, nullable=False)
    dbpassword = Column(String, nullable=False)
    description = Column(String)
    active = Column(Boolean, default=True)
    coveragearea = Column(Geometry("POLYGON", srid=4326))
    createdat = Column(DateTime(timezone=True), server_default=func.now())
    updatedat = Column(DateTime(timezone=True), onupdate=func.now())

class Show(Base):
    __tablename__ = "show"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(Boolean, nullable=False)
    dbname = Column(Boolean, nullable=False)
    dbuser = Column(Boolean, nullable=False)
    coveragearea = Column(Boolean, nullable=False)
    wazelink = Column(Boolean, nullable=False)
    dbhost = Column(Boolean, nullable=False)
    dbportexternal = Column(Boolean, nullable=False)
    dbportinternal = Column(Boolean, nullable=False)
    dbpassword = Column(Boolean, nullable=False)
    description = Column(Boolean, nullable=False)
    active = Column(Boolean, nullable=False)
    createdat = Column(Boolean, nullable=False)
    updatedat = Column(Boolean, nullable=False)
    town = Column(Integer, nullable=False)

class Settings(Base):
    __tablename__ = "settings"
    id = Column(Integer, primary_key=True, index=True)
    varname = Column(String, nullable=False)
    settingname = Column(String, nullable=False)
    setting = Column(String, nullable=False)
    town = Column(Integer, nullable=True)
    description = Column(String, nullable=False)
    groupname = Column(String, nullable=False)