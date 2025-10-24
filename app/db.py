from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy import create_engine
from config import Config

config = Config()

engine = create_engine(config.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_connection():
    return SessionLocal()


def init_db():
    Base.metadata.create_all(bind=engine)
