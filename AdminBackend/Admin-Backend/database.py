#########################
#Author: Patrik Haas (xhaasp00)
#########################

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

load_dotenv()

CENTRAL_DATABASE_URL = "postgresql+psycopg2://" + os.getenv("DB_CENTRAL_USER") + ":" +os.getenv("DB_CENTRAL_PASSWORD") + "@" + os.getenv("DB_CENTRAL_HOST") + ":" + os.getenv("DB_CENTRAL_PORT") + "/" + os.getenv("DB_CENTRAL_NAME")

central_engine = create_engine(CENTRAL_DATABASE_URL)
CentralSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=central_engine)