#########################
#Author: Patrik Haas (xhaasp00)
#########################

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

load_dotenv()

CENTRAL_DATABASE_URL = "postgresql+psycopg2://" + os.getenv("POSTGRES_USER_CENTRAL") + ":" +os.getenv("POSTGRES_PASSWORD_CENTRAL") + "@" + os.getenv("DB_HOST_CENTRAL") + ":" + os.getenv("DB_PORT") + "/" + os.getenv("POSTGRES_DB_CENTRAL")

central_engine = create_engine(CENTRAL_DATABASE_URL)
CentralSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=central_engine)