#########################
#Author: Patrik Haas (xhaasp00)
#########################

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os
import adminEndPoints

load_dotenv()
origins = [
    os.getenv("ORIGINS"), #Frontend url
]

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

app.include_router(adminEndPoints.router)