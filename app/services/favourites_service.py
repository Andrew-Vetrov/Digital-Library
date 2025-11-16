from db import get_connection
from models.models import User, Book, Favourite


class FavoriteService:

    @staticmethod
    def get_favorites(user_id):
        with get_connection() as session:
            favourites = (
                session.query(Favourite)
                .filter(Favourite.user_id == user_id)
                .all()
            )

            return [f.book for f in favourites]

    @staticmethod
    def is_favourite(user_id, book_id):
        """Проверяем, есть ли книга в избранном"""
        with get_connection() as session:
            fav = (
                session.query(Favourite)
                .filter(
                    Favourite.user_id == user_id,
                    Favourite.book_id == book_id
                )
                .first()
            )
            return fav is not None

    @staticmethod
    def add_favorite(user_id, book_id):
        """Добавление книги в избранное"""
        with get_connection() as session:
            # Проверяем, существует ли пользователь и книга
            user = session.query(User).get(user_id)
            book = session.query(Book).get(book_id)

            if not user or not book:
                return False

            # Проверяем, нет ли уже записи
            existing = (
                session.query(Favourite)
                .filter(
                    Favourite.user_id == user_id,
                    Favourite.book_id == book_id
                )
                .first()
            )

            if existing:
                return True  # уже в избранных — ок

            # Добавляем
            fav = Favourite(user_id=user_id, book_id=book_id)
            session.add(fav)
            session.commit()
            return True

    @staticmethod
    def remove_favorite(user_id, book_id):
        """Удаление книги из избранных"""
        with get_connection() as session:
            fav = (
                session.query(Favourite)
                .filter(
                    Favourite.user_id == user_id,
                    Favourite.book_id == book_id
                )
                .first()
            )
            print("\n\n\n",fav,"\n\n\n",flush=True)
            if not fav:
                return False

            session.delete(fav)
            session.commit()
            return True
