from sqlalchemy import Column, String, Integer, ForeignKey, Float
from sqlalchemy.orm import relationship
from db import Base


class Favourite(Base):
    __tablename__ = "favourites"

    id = Column(Integer, primary_key=True)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    book_id = Column(Integer, ForeignKey("books.id"), nullable=False)

    user = relationship("User", back_populates="favorites")
    book = relationship("Book", back_populates="favorited_by")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String(64), nullable=False, unique=True)
    email = Column(String(64), nullable=False, unique=True)
    password_hash = Column(String(256), nullable=False)

    favorites = relationship(
        "Favourite",
        back_populates="user",
        cascade="all, delete-orphan"
    )

    def __init__(self, username, email, password_hash):
        self.username = username
        self.email = email
        self.password_hash = password_hash


class Book(Base):
    __tablename__ = "books"

    id = Column(Integer, primary_key=True)
    title = Column(String(255), nullable=False)
    author = Column(String(255), nullable=False)
    language = Column(String(50))
    genre = Column(String(100))
    minio_key = Column(String(255), nullable=False)
    cover_key = Column(String(255))
    last_position = Column(Float)
    # список Favourite объектов
    favorited_by = relationship(
        "Favourite",
        back_populates="book",
        cascade="all, delete-orphan"
    )

    bookmarked_by = relationship(
        "Bookmark",
        back_populates = "book",
        cascade="all, delete-orphan"
    )
    def __init__(self, title, author, language, genre, minio_key, cover_key=None):
        self.title = title
        self.author = author
        self.language = language
        self.genre = genre
        self.minio_key = minio_key
        self.cover_key = cover_key
        self.last_position = 0

class Bookmark(Base):
    __tablename__ = "bookmarks"
    id = Column(Integer, primary_key=True)
    title = Column(String(255), nullable=False)
    book_id = Column(Integer, ForeignKey("books.id"), nullable=False)
    position = Column(Float)
    book = relationship(
        "Book",
        back_populates = "bookmarked_by"
    )
    def __init__(self, title, position):
        self.title = title
        self.poistion = position