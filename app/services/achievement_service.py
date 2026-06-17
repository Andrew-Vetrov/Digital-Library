# services/achievement_service.py
from db import get_connection
from models.models import (
    User, UserAchievement,
    ReadingHistory, Note, Bookmark, Favourite, BookRating,
)


# ---------------------------------------------------------------------------
# Каталог ачивок описан прямо в коде.
# Каждая ачивка: code, title, description, emoji и предикат `check`,
# который по словарю метрик пользователя решает, заработана ли ачивка.
# ---------------------------------------------------------------------------

# Книга считается "прочитанной", если прогресс >= этого порога
_READ_THRESHOLD = 0.95

ACHIEVEMENTS = [
    {
        "code": "first_book",
        "title": "Первая книга",
        "description": "Прочитайте свою первую книгу до конца",
        "emoji": "🏆",
        "check": lambda m: m["books_read"] >= 1,
    },
    {
        "code": "bookworm_5",
        "title": "Книжный червь",
        "description": "Прочитайте 5 книг",
        "emoji": "📚",
        "check": lambda m: m["books_read"] >= 5,
    },
    {
        "code": "bookworm_25",
        "title": "Библиофил",
        "description": "Прочитайте 25 книг",
        "emoji": "🎓",
        "check": lambda m: m["books_read"] >= 25,
    },
    {
        "code": "first_favorite",
        "title": "Есть любимчик",
        "description": "Добавьте книгу в избранное",
        "emoji": "⭐",
        "check": lambda m: m["favorites"] >= 1,
    },
    {
        "code": "first_bookmark",
        "title": "Заложил страницу",
        "description": "Создайте первую закладку",
        "emoji": "🔖",
        "check": lambda m: m["bookmarks"] >= 1,
    },
    {
        "code": "first_note",
        "title": "На полях",
        "description": "Оставьте первую заметку",
        "emoji": "✍️",
        "check": lambda m: m["notes"] >= 1,
    },
    {
        "code": "note_taker_10",
        "title": "Внимательный читатель",
        "description": "Оставьте 10 заметок",
        "emoji": "📝",
        "check": lambda m: m["notes"] >= 10,
    },
    {
        "code": "first_rating",
        "title": "Своё мнение",
        "description": "Оцените первую книгу",
        "emoji": "👍",
        "check": lambda m: m["ratings"] >= 1,
    },
    {
        "code": "critic_10",
        "title": "Критик",
        "description": "Оцените 10 книг",
        "emoji": "⚖️",
        "check": lambda m: m["ratings"] >= 10,
    },
]

_BY_CODE = {a["code"]: a for a in ACHIEVEMENTS}


def _public(achievement, *, earned, created_at=None):
    """Представление ачивки для фронтенда (без предиката)."""
    return {
        "code": achievement["code"],
        "title": achievement["title"],
        "description": achievement["description"],
        "emoji": achievement["emoji"],
        "earned": earned,
        "earned_at": created_at.isoformat() if created_at else None,
    }


class AchievementService:

    @staticmethod
    def _compute_metrics(session, user_id):
        books_read = session.query(ReadingHistory).filter(
            ReadingHistory.user_id == user_id,
            ReadingHistory.progress >= _READ_THRESHOLD,
        ).count()
        return {
            "books_read": books_read,
            "favorites": session.query(Favourite).filter_by(user_id=user_id).count(),
            "bookmarks": session.query(Bookmark).filter_by(user_id=user_id).count(),
            "notes": session.query(Note).filter_by(user_id=user_id).count(),
            "ratings": session.query(BookRating).filter_by(user_id=user_id).count(),
        }

    @staticmethod
    def evaluate(user_id, session=None):
        """Пересчитать метрики пользователя и выдать новые заработанные ачивки.

        Возвращает список новых ачивок (публичное представление) — для попапов.
        Идемпотентно: уже выданные ачивки не дублируются.
        """
        own_session = session is None
        session = session or get_connection()
        try:
            if not session.query(User).get(user_id):
                return []

            metrics = AchievementService._compute_metrics(session, user_id)

            already = {
                ua.code
                for ua in session.query(UserAchievement).filter_by(user_id=user_id).all()
            }

            newly = []
            for ach in ACHIEVEMENTS:
                if ach["code"] in already:
                    continue
                try:
                    qualifies = ach["check"](metrics)
                except Exception:
                    qualifies = False
                if qualifies:
                    session.add(UserAchievement(user_id=user_id, code=ach["code"]))
                    newly.append(_public(ach, earned=True))

            # Поддерживаем легаси-флаг в синхронном состоянии (используется на главной)
            if "first_book" in already or any(a["code"] == "first_book" for a in newly):
                user = session.query(User).get(user_id)
                if user and not user.has_read_book_achievement:
                    user.has_read_book_achievement = True

            if newly:
                session.commit()
            return newly
        finally:
            if own_session:
                session.close()

    @staticmethod
    def award(user_id, code, session=None):
        """Явно выдать ачивку по событию (например, «дочитал книгу»).
        Идемпотентно. Возвращает публичное представление новой ачивки или None."""
        if code not in _BY_CODE:
            return None
        own_session = session is None
        session = session or get_connection()
        try:
            exists = session.query(UserAchievement).filter_by(
                user_id=user_id, code=code
            ).first()
            if exists:
                return None
            if not session.query(User).get(user_id):
                return None
            session.add(UserAchievement(user_id=user_id, code=code))
            if code == "first_book":
                user = session.query(User).get(user_id)
                if user:
                    user.has_read_book_achievement = True
            session.commit()
            return _public(_BY_CODE[code], earned=True)
        finally:
            if own_session:
                session.close()

    @staticmethod
    def get_user_achievements(user_id):
        """Весь каталог с пометкой earned/locked для страницы ачивок."""
        with get_connection() as session:
            earned = {
                ua.code: ua.created_at
                for ua in session.query(UserAchievement).filter_by(user_id=user_id).all()
            }
            result = []
            for ach in ACHIEVEMENTS:
                code = ach["code"]
                result.append(_public(
                    ach,
                    earned=code in earned,
                    created_at=earned.get(code),
                ))
            return result

    @staticmethod
    def get_earned_codes(user_id, session=None):
        own_session = session is None
        session = session or get_connection()
        try:
            return [
                ua.code
                for ua in session.query(UserAchievement).filter_by(user_id=user_id).all()
            ]
        finally:
            if own_session:
                session.close()

    # --- Обратная совместимость со старым вызовом из reader.html ------------
    @staticmethod
    def give_read_book_achievement(user_id: int):
        """Старый эндпоинт «дочитал книгу». Теперь прогоняет полную оценку
        и возвращает True, если выдана новая ачивка (для попапа)."""
        newly = AchievementService.evaluate(user_id)
        return len(newly) > 0
