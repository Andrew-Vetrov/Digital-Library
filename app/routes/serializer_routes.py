from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from models.models import (
    Bookmark,
    BookRating,
    Favourite,
    Friendship,
    Note,
    ReadingHistory,
    ReadingProgress,
    SearchHistory,
    User,
)


# ---------------------------------------------------------------------------
# Вспомогательные сериализаторы для каждой модели
# ---------------------------------------------------------------------------

def _book_brief(book) -> dict[str, Any] | None:
    """Минимальное представление книги (без вложенных связей)."""
    if book is None:
        return None
    return {
        "id": book.id,
        "title": book.title,
        "author": book.author,
        "language": book.language,
        "genre": book.genre,
        "cover_key": book.cover_key,
        "average_rating": book.average_rating,
    }


def _serialize_favourite(fav: Favourite) -> dict[str, Any]:
    return {
        "id": fav.id,
        "book": _book_brief(fav.book),
    }


def _serialize_reading_history(rh: ReadingHistory) -> dict[str, Any]:
    return {
        "id": rh.id,
        "book": _book_brief(rh.book),
        "progress": rh.progress,
        "last_read_at": rh.last_read_at.isoformat() if rh.last_read_at else None,
    }


def _serialize_search_history(sh: SearchHistory) -> dict[str, Any]:
    return {
        "id": sh.id,
        "query": sh.query,
        "created_at": sh.created_at.isoformat() if sh.created_at else None,
    }


def _serialize_bookmark(bm: Bookmark) -> dict[str, Any]:
    return {
        "id": bm.id,
        "title": bm.title,
        "book_id": bm.book_id,
        "position": bm.position,
        "cfi": bm.cfi,
        "is_shared": bm.is_shared,
    }


def _serialize_note(note: Note) -> dict[str, Any]:
    return {
        "id": note.id,
        "title": note.title,
        "book_id": note.book_id,
        # NOTE: в Note.__init__ есть опечатка: self.poistion вместо self.position,
        # поэтому обращаемся к колонке напрямую через __dict__ / getattr с fallback.
        "position": getattr(note, "position", None),
        "cfi": note.cfi,
        "selected_text": note.selected_text,
        "comment": note.comment,
        "is_shared": note.is_shared,
    }


def _serialize_rating(rating: BookRating) -> dict[str, Any]:
    return {
        "id": rating.id,
        "book_id": rating.book_id,
        "score": rating.score,
    }


def _serialize_reading_progress(rp: ReadingProgress) -> dict[str, Any]:
    return {
        "id": rp.id,
        "book_id": rp.book_id,
        "cfi": rp.cfi,
        "last_position": rp.last_position,
    }


def _serialize_friendship(fs: Friendship, current_user_id: int) -> dict[str, Any]:
    """
    Возвращает данные о дружбе относительно текущего пользователя:
    - direction: 'outgoing' — текущий пользователь отправил запрос,
                 'incoming' — запрос получен.
    """
    direction = "outgoing" if fs.user_id == current_user_id else "incoming"
    other_user_id = fs.friend_id if direction == "outgoing" else fs.user_id
    return {
        "id": fs.id,
        "direction": direction,
        "other_user_id": other_user_id,
        "status": fs.status,
        "created_at": fs.created_at.isoformat() if fs.created_at else None,
    }


# ---------------------------------------------------------------------------
# Основная функция
# ---------------------------------------------------------------------------

def serialize_user(
    session: Session,
    user_id: int,
    *,
    include_bookmarks: bool = True,
    include_notes: bool = True,
    include_ratings: bool = True,
    include_reading_progress: bool = True,
    include_friendships: bool = True,
) -> dict[str, Any]:
    """
    Собирает все данные пользователя в один словарь.

    Параметры
    ---------
    session : SQLAlchemy Session
    user_id : int
        ID пользователя.
    include_* : bool
        Флаги для включения/исключения отдельных разделов
        (удобно при необходимости лёгкого профиля).

    Возвращает
    ----------
    dict — полный снимок данных пользователя, или {"error": "..."} если не найден.
    """
    user: User | None = session.get(User, user_id)
    if user is None:
        return {"error": f"User with id={user_id} not found"}

    result: dict[str, Any] = {
        # --- Базовые поля пользователя ---
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "has_read_book_achievement": user.has_read_book_achievement,
        "invite_token": user.invite_token,

        # --- Связи через relationship (загружаются автоматически) ---
        "favorites": [_serialize_favourite(f) for f in user.favorites],
        "reading_history": [_serialize_reading_history(rh) for rh in user.recent_books],
        "search_history": [_serialize_search_history(sh) for sh in user.search_history],
    }

    # --- Связи без FK-relationship на User (хранят user_id как Integer) ---
    if include_bookmarks:
        bookmarks = session.query(Bookmark).filter(Bookmark.user_id == user_id).all()
        result["bookmarks"] = [_serialize_bookmark(bm) for bm in bookmarks]

    if include_notes:
        notes = session.query(Note).filter(Note.user_id == user_id).all()
        result["notes"] = [_serialize_note(n) for n in notes]

    if include_ratings:
        ratings = session.query(BookRating).filter(BookRating.user_id == user_id).all()
        result["ratings"] = [_serialize_rating(r) for r in ratings]

    if include_reading_progress:
        progress = session.query(ReadingProgress).filter(ReadingProgress.user_id == user_id).all()
        result["reading_progress"] = [_serialize_reading_progress(rp) for rp in progress]

    if include_friendships:
        friendships = (
            session.query(Friendship)
            .filter(
                (Friendship.user_id == user_id) | (Friendship.friend_id == user_id)
            )
            .all()
        )
        result["friendships"] = [_serialize_friendship(fs, user_id) for fs in friendships]

    return result

from flask import Blueprint, request, jsonify, session
from db import SessionLocal
 
serialize_bp = Blueprint("serialize_bp", __name__)
 
 
@serialize_bp.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "http://127.0.0.1:3000"
    response.headers["Access-Control-Allow-Credentials"] = "true"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    return response
 
 
@serialize_bp.route("/serialize", methods=["GET", "OPTIONS"])
def serialize():
    if request.method == "OPTIONS":
        return jsonify({}), 200
 
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401
 
    # Опциональные флаги через query-параметры: /serialize?include_notes=false
    def flag(name: str) -> bool:
        return request.args.get(name, "true").lower() != "false"
 
    db = SessionLocal()
    try:
        data = serialize_user(
            db,
            user_id,
            include_bookmarks=flag("include_bookmarks"),
            include_notes=flag("include_notes"),
            include_ratings=flag("include_ratings"),
            include_reading_progress=flag("include_reading_progress"),
            include_friendships=flag("include_friendships"),
        )
        if "error" in data:
            return jsonify(data), 404
        return jsonify(data), 200
    finally:
        db.close()