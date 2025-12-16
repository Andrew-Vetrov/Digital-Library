from db import get_connection
from flask import jsonify
from models.models import User, Book, Favourite, Bookmark, Note

class NoteService:
    @staticmethod
    def create_note(book_id, title, position, selected_text, cfi):
        with get_connection() as session:
            bm = Note(book_id=book_id, title=title, position=position, selected_text=selected_text, cfi=cfi)
            bm.position=position
            session.add(bm)
            session.commit()
            session.refresh(bm)
            return bm
        
    @staticmethod
    def get_notes(book_id):
        with get_connection() as session:
            return (
                session.query(Note)
                .filter_by(book_id=book_id)
                .order_by(Note.id.asc())
                .all()
            )
    
    @staticmethod
    def delete_note(id):
        with get_connection() as session:
            session.query(Note).filter_by(id=id).delete()
            session.commit()

