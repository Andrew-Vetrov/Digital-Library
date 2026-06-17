import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "default_secret")
    DB_NAME = os.getenv("DB_NAME")
    DB_USER = os.getenv("DB_USER")
    DB_PASSWORD = os.getenv("DB_PASSWORD")
    DB_HOST = os.getenv("DB_HOST", "postgres_db")
    DB_PORT = os.getenv("DB_PORT", "5432")
    BUCKET_NAME = os.getenv("BUCKET_NAME", "librarybucket")
    DB_DRIVER = os.getenv("DB_DRIVER", "postgresql")
    DB_LIB = os.getenv("DB_LIB", "psycopg2")

    # Стартовый администратор. Если заданы ADMIN_EMAIL и ADMIN_PASSWORD,
    # при запуске приложения такой пользователь создаётся (или повышается
    # до admin) автоматически — удобно при частом пересоздании базы.
    ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
    ADMIN_EMAIL = os.getenv("ADMIN_EMAIL")
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")

    @property
    def DATABASE_URL(self):
        #return f"dbname={self.DB_NAME} user={self.DB_USER} password={self.DB_PASSWORD} host={self.DB_HOST} port={self.DB_PORT}"
        return f"{self.DB_DRIVER}://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"