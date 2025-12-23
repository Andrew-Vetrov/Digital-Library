# services/achievement_service.py
from db import get_connection
from models.models import User


class AchievementService:

    @staticmethod
    def give_read_book_achievement(user_id: int):
        with get_connection() as session:
            user = session.query(User).get(user_id)
            if not user:
                return False

            if user.has_read_book_achievement:
                return False  # ❌ уже была ачивка

            user.has_read_book_achievement = True
            session.commit()

            return True  # ✅ новая ачивка
