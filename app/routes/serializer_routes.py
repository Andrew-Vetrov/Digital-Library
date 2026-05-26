from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from models.models import (
    Book,
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

from flask import Blueprint, request, jsonify, session, redirect, url_for, render_template
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


# ---------------------------------------------------------------------------
# Десериализация / импорт данных
# ---------------------------------------------------------------------------

_MAX_IMPORT_BYTES = 5 * 1024 * 1024  # 5 МБ


def deserialize_user_data(
    db: Session,
    user_id: int,
    data: dict[str, Any],
) -> dict[str, Any]:
    """
    Импортирует данные из JSON-снимка в аккаунт пользователя.
    Книги, которых нет в БД, и уже существующие записи — пропускаются.
    Возвращает статистику: сколько записей каждого типа импортировано / пропущено.
    """
    stats: dict[str, dict[str, int]] = {
        k: {"imported": 0, "skipped": 0}
        for k in ("favorites", "bookmarks", "notes", "ratings", "reading_progress", "search_history", "friendships")
    }

    def book_exists(book_id: object) -> bool:
        if not isinstance(book_id, int):
            return False
        return db.get(Book, book_id) is not None

    # --- Favorites ---
    existing_favs = {
        f.book_id
        for f in db.query(Favourite).filter(Favourite.user_id == user_id).all()
    }
    for item in data.get("favorites", []):
        book = item.get("book") if isinstance(item, dict) else None
        book_id = book.get("id") if isinstance(book, dict) else None
        if not book_exists(book_id) or book_id in existing_favs:
            stats["favorites"]["skipped"] += 1
            continue
        db.add(Favourite(user_id=user_id, book_id=book_id))
        existing_favs.add(book_id)
        stats["favorites"]["imported"] += 1

    # --- Bookmarks ---
    existing_bms = {
        (bm.book_id, bm.cfi)
        for bm in db.query(Bookmark).filter(Bookmark.user_id == user_id).all()
    }
    for item in data.get("bookmarks", []):
        if not isinstance(item, dict):
            stats["bookmarks"]["skipped"] += 1
            continue
        book_id = item.get("book_id")
        cfi = item.get("cfi") or ""
        if not book_exists(book_id) or (book_id, cfi) in existing_bms:
            stats["bookmarks"]["skipped"] += 1
            continue
        db.add(Bookmark(
            book_id=book_id,
            title=str(item.get("title") or "")[:255],
            position=float(item.get("position") or 0.0),
            cfi=cfi,
            user_id=user_id,
            is_shared=False,
        ))
        existing_bms.add((book_id, cfi))
        stats["bookmarks"]["imported"] += 1

    # --- Notes ---
    existing_notes = {
        (n.book_id, n.cfi)
        for n in db.query(Note).filter(Note.user_id == user_id).all()
    }
    for item in data.get("notes", []):
        if not isinstance(item, dict):
            stats["notes"]["skipped"] += 1
            continue
        book_id = item.get("book_id")
        cfi = item.get("cfi") or ""
        if not book_exists(book_id) or (book_id, cfi) in existing_notes:
            stats["notes"]["skipped"] += 1
            continue
        db.add(Note(
            book_id=book_id,
            title=str(item.get("title") or "")[:255],
            position=float(item.get("position") or 0.0),
            selected_text=item.get("selected_text"),
            cfi=cfi,
            comment=item.get("comment"),
            user_id=user_id,
            is_shared=False,
        ))
        existing_notes.add((book_id, cfi))
        stats["notes"]["imported"] += 1

    # --- Ratings ---
    existing_ratings = {
        r.book_id
        for r in db.query(BookRating).filter(BookRating.user_id == user_id).all()
    }
    for item in data.get("ratings", []):
        if not isinstance(item, dict):
            stats["ratings"]["skipped"] += 1
            continue
        book_id = item.get("book_id")
        score = item.get("score")
        if not book_exists(book_id) or book_id in existing_ratings:
            stats["ratings"]["skipped"] += 1
            continue
        if not isinstance(score, int) or not (1 <= score <= 5):
            stats["ratings"]["skipped"] += 1
            continue
        db.add(BookRating(user_id=user_id, book_id=book_id, score=score))
        existing_ratings.add(book_id)
        stats["ratings"]["imported"] += 1

    # --- Reading Progress ---
    existing_progress = {
        rp.book_id
        for rp in db.query(ReadingProgress).filter(ReadingProgress.user_id == user_id).all()
    }
    for item in data.get("reading_progress", []):
        if not isinstance(item, dict):
            stats["reading_progress"]["skipped"] += 1
            continue
        book_id = item.get("book_id")
        if not book_exists(book_id) or book_id in existing_progress:
            stats["reading_progress"]["skipped"] += 1
            continue
        db.add(ReadingProgress(
            user_id=user_id,
            book_id=book_id,
            cfi=item.get("cfi") or "",
            last_position=float(item.get("last_position") or 0.0),
        ))
        existing_progress.add(book_id)
        stats["reading_progress"]["imported"] += 1

    # --- Search History ---
    # Дедуплицируем по (query, created_at), чтобы одинаковые запросы
    # в разное время (или без времени, но разные события) импортировались.
    existing_search = {
        (sh.query, sh.created_at.isoformat() if sh.created_at else None)
        for sh in db.query(SearchHistory).filter(SearchHistory.user_id == user_id).all()
    }
    # В рамках одного JSON-файла тоже отслеживаем добавленное, чтобы не дублировать
    seen_in_payload: set[tuple[str, str | None]] = set()
    for item in data.get("search_history", []):
        if not isinstance(item, dict):
            stats["search_history"]["skipped"] += 1
            continue
        query = item.get("query")
        if not query or not isinstance(query, str):
            stats["search_history"]["skipped"] += 1
            continue
        created_at_str: str | None = item.get("created_at")
        key = (query, created_at_str)
        if key in existing_search or key in seen_in_payload:
            stats["search_history"]["skipped"] += 1
            continue
        sh = SearchHistory(user_id=user_id, query=query)
        if created_at_str:
            try:
                sh.created_at = datetime.fromisoformat(created_at_str)
            except ValueError:
                pass
        db.add(sh)
        seen_in_payload.add(key)
        stats["search_history"]["imported"] += 1

    # --- Friendships ---
    # Для каждого друга из снимка кидаем запрос дружбы, если пользователь
    # существует и связи между ними ещё нет.
    existing_friend_ids = {
        (fs.friend_id if fs.user_id == user_id else fs.user_id)
        for fs in db.query(Friendship).filter(
            (Friendship.user_id == user_id) | (Friendship.friend_id == user_id)
        ).all()
    }
    for item in data.get("friendships", []):
        if not isinstance(item, dict):
            stats["friendships"]["skipped"] += 1
            continue
        other_id = item.get("other_user_id")
        if not isinstance(other_id, int) or other_id == user_id:
            stats["friendships"]["skipped"] += 1
            continue
        if db.get(User, other_id) is None:
            stats["friendships"]["skipped"] += 1
            continue
        if other_id in existing_friend_ids:
            stats["friendships"]["skipped"] += 1
            continue
        fs = Friendship()
        fs.user_id = user_id
        fs.friend_id = other_id
        fs.status = "pending"
        fs.created_at = datetime.utcnow()
        db.add(fs)
        existing_friend_ids.add(other_id)
        stats["friendships"]["imported"] += 1

    db.commit()
    return stats


@serialize_bp.route("/import-data", methods=["GET"])
def import_data_page():
    if not session.get("user_id"):
        return redirect(url_for("auth.authorization"))
    return render_template("import_data.html")


@serialize_bp.route("/deserialize", methods=["POST", "OPTIONS"])
def deserialize():
    if request.method == "OPTIONS":
        return jsonify({}), 200

    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    if "file" in request.files:
        f = request.files["file"]
        if not f.filename.lower().endswith(".json"):
            return jsonify({"error": "Поддерживаются только JSON файлы"}), 400
        raw = f.read(_MAX_IMPORT_BYTES + 1)
        if len(raw) > _MAX_IMPORT_BYTES:
            return jsonify({"error": "Файл слишком большой (максимум 5 МБ)"}), 413
        try:
            payload = json.loads(raw)
        except (ValueError, UnicodeDecodeError):
            return jsonify({"error": "Невалидный JSON файл"}), 400
    elif request.is_json:
        payload = request.get_json(silent=True) or {}
    else:
        return jsonify({"error": "Загрузите JSON файл или отправьте JSON тело запроса"}), 400

    if not isinstance(payload, dict):
        return jsonify({"error": "JSON должен быть объектом"}), 400

    db = SessionLocal()
    try:
        stats = deserialize_user_data(db, user_id, payload)
        return jsonify({"success": True, "imported": stats}), 200
    except Exception:
        db.rollback()
        return jsonify({"error": "Внутренняя ошибка при импорте данных"}), 500
    finally:
        db.close()