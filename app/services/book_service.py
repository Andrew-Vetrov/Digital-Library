import os
from minio import Minio
from utils.epub_parser import EPUBParser
from models.models import (
    Book, ReadingHistory, BookRating, ReadingProgress, BookAccess,
    User, GroupMember, GroupBookAccess,
)
from datetime import datetime
from db import get_connection
from services.elasticsearch_service import index_book

class BookService:
    @staticmethod
    def upload_book(file_storage, genre=None):
        temp_path = f"/tmp/{file_storage.filename}"
        file_storage.save(temp_path)

        parser = EPUBParser(temp_path)
        # тут надо аккуратно глянуть, потому что сейчас у нас весь текст в метадате
        metadata = parser.extract_metadata()
        book_text = parser._extract_text()
        print("Genre\n",metadata["genre"])


        minio = Minio(
            os.getenv("MINIO_ENDPOINT", "minio:9000"),
            access_key=os.getenv("MINIO_ROOT_USER"),
            secret_key=os.getenv("MINIO_ROOT_PASSWORD"),
            secure=False
        )
        bucket = os.getenv("BUCKET_NAME", "books")
        if not minio.bucket_exists(bucket):
            minio.make_bucket(bucket)

        minio_key = file_storage.filename
        minio.fput_object(bucket, minio_key, temp_path)

        cover_key = None
        if metadata["cover_image"]:
            cover_path = f"/tmp/{file_storage.filename}_cover.jpg"
            with open(cover_path, "wb") as f:
                import base64
                f.write(base64.b64decode(metadata["cover_image"]))
            cover_key = f"covers/{file_storage.filename}.jpg"
            minio.fput_object(bucket, cover_key, cover_path)

        with get_connection() as session:
            print("\n\n\nBook start saving")
            book = Book(
                metadata["title"], metadata["author"], metadata["language"],
                genre, minio_key, cover_key
            )
            session.add(book)
            session.commit()
            print("Book saved OK\n\n\n")

            index_book(
                book_id=book.id,
                title=metadata["title"],
                author=metadata["author"],
                content=book_text
            )
    
            return metadata["title"]

    @staticmethod
    def delete_book(book_id):
        from flask import abort

        minio = Minio(
            os.getenv("MINIO_ENDPOINT", "minio:9000"),
            access_key=os.getenv("MINIO_ROOT_USER"),
            secret_key=os.getenv("MINIO_ROOT_PASSWORD"),
            secure=False
        )

        bucket = os.getenv("BUCKET_NAME", "books")

        with get_connection() as session:
            book = session.query(Book).get(book_id)
            if not book:
                abort(404, "Книга не найдена")
            try:
                if book.minio_key:
                    minio.remove_object(bucket, book.minio_key)
                if book.cover_key:
                    minio.remove_object(bucket, book.cover_key)
            except Exception as e:
                print("Ошибка удаления из MinIO:", e)

            session.delete(book)
            session.commit()

            return True

    @staticmethod
    def find_books(*args):
        with get_connection() as session:
            books = session.query(Book).all() if len(args) == 0 else session.query(Book).filter(Book.id.in_(args[0])).all()

            bucket = os.getenv("BUCKET_NAME", "books")
            public_url = os.getenv("MINIO_PUBLIC_ENDPOINT", "http://localhost:9000")

            for b in books:
                if b.cover_key:
                    b.cover_url = f"{public_url}/{bucket}/{b.cover_key}"
                else:
                    b.cover_url = "https://via.placeholder.com/160x220?text=No+Cover"

            return books

    @staticmethod
    def find_book_by_id(book_id):
        with get_connection() as session:
            q = session.query(Book).filter(Book.id == book_id).first()
            return q
        
    @staticmethod
    def get_reading_position(book_id, user_id):
        with get_connection() as session:
            progress = session.query(ReadingProgress).filter(
                    ReadingProgress.user_id == user_id,
                    ReadingProgress.book_id == book_id
                ).first()

        return progress
    
    @staticmethod
    def set_reading_position(book_id, user_id, new_position, cfi):
        with get_connection() as session:

            progress = (
                session.query(ReadingProgress)
                .filter(
                    ReadingProgress.book_id == book_id,
                    ReadingProgress.user_id == user_id
                )
                .first()
            )

            if progress:
                progress.last_position = new_position
                progress.cfi = cfi
            else:
                progress = ReadingProgress(
                    user_id=user_id,
                    book_id=book_id,
                    cfi=cfi,
                    last_position=new_position
                )

                session.add(progress)

            session.commit()
            return True
        
    @staticmethod
    def update_reading_history(user_id, book_id):
        """Обновить историю чтения пользователя"""
        with get_connection() as session:
            # Находим существующую запись
            history = session.query(ReadingHistory).filter(
                ReadingHistory.user_id == user_id,
                ReadingHistory.book_id == book_id
            ).first()
            
            # Рассчитываем прогресс, если известно общее количество символов
            
            
            if history:
                # Обновляем существующую запись
                history.last_read_at = datetime.utcnow()
                progress = session.query(ReadingProgress).filter(ReadingProgress.book_id == book_id,
                                                                 ReadingProgress.user_id == user_id).first().last_position
                history.progress = progress
            else:
                # Создаем новую запись
                progress = (
                session.query(ReadingProgress)
                    .filter(
                        ReadingProgress.book_id == book_id,
                        ReadingProgress.user_id == user_id
                    )
                    .first()
                )
                if not progress:
                    progress = ReadingProgress(
                        user_id=user_id,
                        book_id=book_id,
                        cfi=0,
                        last_position=0
                    )

                    session.add(progress)
                progress = session.query(ReadingProgress).filter(ReadingProgress.book_id == book_id,
                                                                 ReadingProgress.user_id == user_id).first().last_position
                history = ReadingHistory(
                    user_id=user_id,
                    book_id=book_id,
                    progress=progress
                )
                session.add(history)
            
            session.commit()
            return history
    
    @staticmethod
    def get_recent_books(user_id, limit=5):
        """Получить последние прочитанные книги пользователя"""
        with get_connection() as session:
            recent = session.query(ReadingHistory).join(Book).filter(
                ReadingHistory.user_id == user_id
            ).order_by(
                ReadingHistory.last_read_at.desc()
            ).limit(limit).all()
            
            books_with_progress = []
            for history in recent:
                book = history.book
                book.last_position = history.progress
                print(book.last_position, flush=True)
                books_with_progress.append(book)
            
            return books_with_progress

    @staticmethod
    def set_book_rating(user_id, book_id, score):
        with get_connection() as session:
            if not (1 <= score <= 5):
                return False

            rating = session.query(BookRating).filter_by(user_id=user_id, book_id=book_id).first()

            if rating:
                rating.score = score
            else:
                rating = BookRating(user_id=user_id, book_id=book_id, score=score)
                session.add(rating)

            session.commit()

            all_ratings = session.query(BookRating).filter_by(book_id=book_id).all()

            if all_ratings:
                avg = sum(r.score for r in all_ratings) / len(all_ratings)

                book = session.query(Book).get(book_id)
                if book:
                    book.average_rating = round(avg, 2)
                    session.commit()
                    return True

            return False

    @staticmethod
    def get_allowed_book_ids(user_id):
        """ID книг, к которым у пользователя есть явный доступ —
        напрямую (BookAccess) либо через группу (GroupBookAccess).
        Не включает книги с is_visible_to_all (вызывающий код проверяет его отдельно)."""
        with get_connection() as session:
            direct = session.query(BookAccess.book_id).filter(
                BookAccess.user_id == user_id
            ).all()

            via_group = (
                session.query(GroupBookAccess.book_id)
                .join(GroupMember, GroupMember.group_id == GroupBookAccess.group_id)
                .filter(GroupMember.user_id == user_id)
                .all()
            )

            return list({r[0] for r in direct} | {r[0] for r in via_group})

    @staticmethod
    def get_accessible_book_ids(user_id, session=None):
        """Полный набор ID книг, доступных пользователю для чтения.

        Возвращает None, если пользователь — администратор (доступны все книги).
        Иначе — set из публичных книг (is_visible_to_all) и явно выданных
        (напрямую или через группу). Используется для фильтрации сериализации.

        Можно передать существующую SQLAlchemy-сессию, чтобы не открывать новую.
        """
        own_session = session is None
        session = session or get_connection()
        try:
            user = session.query(User).get(user_id)
            if user and getattr(user, "role", None) == "admin":
                return None  # доступ ко всему

            public = session.query(Book.id).filter(Book.is_visible_to_all.is_(True)).all()

            direct = session.query(BookAccess.book_id).filter(
                BookAccess.user_id == user_id
            ).all()

            via_group = (
                session.query(GroupBookAccess.book_id)
                .join(GroupMember, GroupMember.group_id == GroupBookAccess.group_id)
                .filter(GroupMember.user_id == user_id)
                .all()
            )

            return (
                {r[0] for r in public}
                | {r[0] for r in direct}
                | {r[0] for r in via_group}
            )
        finally:
            if own_session:
                session.close()

    @staticmethod
    def user_can_access_book(user_id, book_id, session=None):
        accessible = BookService.get_accessible_book_ids(user_id, session=session)
        return accessible is None or book_id in accessible