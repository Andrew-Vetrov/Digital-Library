from sqlalchemy import Column, Integer, String, Text
from db import Base

class Book(Base):
    __tablename__ = "books"

    id = Column(Integer, primary_key=True)
    title = Column(String(255), nullable=False)
    author = Column(String(255), nullable=False)
    language = Column(String(50))
    genre = Column(String(100))
    minio_key = Column(String(255), nullable=False)
    cover_key = Column(String(255))

    def __init__(self, title, author, language, genre, minio_key, cover_key=None):
        self.title = title
        self.author = author
        self.language = language
        self.genre = genre
        self.minio_key = minio_key
        self.cover_key = cover_key
