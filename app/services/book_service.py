import os
from minio import Minio
from utils.epub_parser import EPUBParser
from models.models import Book, ReadingHistory
from datetime import datetime
from db import get_connection
from services.elasticsearch_service import index_book

class BookService:
    _SENTINEL = object()

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
    def get_reading_position(book_id):
        res = BookService.find_book_by_id(book_id)
        print("\n\nLOC = " + res)

        return res.last_position
    
    @staticmethod
    def set_reading_position(book_id, new_position):
        with get_connection() as session:
            q = session.query(Book).filter(Book.id == book_id).first()
            session.query(Book).filter(Book.id == book_id).update(
                {Book.last_position: new_position}, synchronize_session=False)
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
                progress = session.query(Book).filter(Book.id == book_id).first().last_position
                history.progress = progress
            else:
                # Создаем новую запись
                progress = session.query(Book).filter(Book.id == book_id).first().last_position
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
                books_with_progress.append(book)
            
            return books_with_progress