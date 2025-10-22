import psycopg2
import psycopg2.extras
from app.config import Config

config = Config()

def get_connection():
    return psycopg2.connect(config.DATABASE_URL)

def init_db():
    query = """
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        username VARCHAR(64) UNIQUE NOT NULL,
        email_hash VARCHAR(128) UNIQUE NOT NULL,
        password_hash VARCHAR(128) NOT NULL
    );
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query)
        conn.commit()
