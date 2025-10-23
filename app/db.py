import psycopg2
import psycopg2.extras
from config import Config
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session
from sqlalchemy import Column, Integer, String, create_engine
config = Config()

engine = create_engine(config.DATABASE_URL)

class Base(DeclarativeBase) : pass

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key = True)
    username = Column(String(64), nullable = False, unique = True)
    email = Column(String(64), nullable = False, unique = True)
    password_hash = Column(String(256), nullable = False)

def get_connection():
    return Session(autoflush=False, bind=engine)

def init_db():
    # query = """
    # CREATE TABLE IF NOT EXISTS users (
    #     id SERIAL PRIMARY KEY,
    #     username VARCHAR(64) UNIQUE NOT NULL,
    #     email_hash VARCHAR(128) UNIQUE NOT NULL,
    #     password_hash VARCHAR(128) NOT NULL
    # );
    # """
    
    Base.metadata.create_all(bind=engine)
    # with get_connection() as conn:
    #     with conn.cursor() as cur:
    #         cur.execute(query)
    #     conn.commit()
