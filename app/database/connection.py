import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

load_dotenv()

database_url = os.getenv("DATABASE_URL")


engine = create_engine(
    database_url, 
    echo=False, 
    pool_size=10, 
    max_overflow=20, 
    pool_timeout=120, 
    pool_recycle=1800
    )

SessinLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    return SessinLocal()
