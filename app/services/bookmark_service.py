from db import get_connection
from flask import jsonify
from models.models import User, Book, Favourite, Bookmark

class BookmarkService:
    @staticmethod
    def create_bookmark(book_id, title, position, cfi, user_id):
        with get_connection() as session:
            bm = Bookmark(book_id=book_id, title=title, position=position, cfi=cfi, user_id=user_id)
            bm.position=position
            session.add(bm)
            session.commit()
            return
    @staticmethod
    def get_bookmarks(book_id, user_id):
        with get_connection() as session:
            return (
                session.query(Bookmark)
                .filter_by(book_id=book_id,
                           user_id=user_id)
                .order_by(Bookmark.id.asc())
                .all()
            )
    
    @staticmethod
    def update_bookmark(bookmark_id, title=None):
        with get_connection() as session:
            bookmark = session.query(Bookmark).filter_by(id=bookmark_id).first()
            if not bookmark:
                return None
            
            if title is not None:
                bookmark.title = title
                        
            session.commit()
            session.refresh(bookmark)
            return bookmark
        
    @staticmethod
    def delete_bookmark(id):
        with get_connection() as session:
            session.query(Bookmark).filter_by(id=id).delete()
            session.commit()

