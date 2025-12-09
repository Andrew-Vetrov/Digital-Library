from db import get_connection
from models.models import User, Book, Favourite, Bookmark

class BookmarkService:
    @staticmethod
    def create_bookmark(book_id, title, position):
        with get_connection() as session:
            bm = Bookmark(book_id=book_id, title=title, position=position)
            bm.book_id = book_id
            session.add(bm)
            session.commit()
            return bm
    @staticmethod
    def get_bookmarks(book_id):
        with get_connection() as session:
            return (
                session.query(Bookmark)
                .filter_by(book_id=book_id)
                .order_by(Bookmark.id.asc())
                .all()
            )
    
    @staticmethod
    def delete_bookmark(id):
        with get_connection() as session:
            session.query(Bookmark).filter_by(id=id).delete()
            session.commit()

