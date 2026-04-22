from db import get_connection
from flask import jsonify
from models.models import User, Book, Favourite, Bookmark, Note

class NoteService:
    @staticmethod
    def create_note(book_id, title, position, selected_text, cfi, comment, user_id):
        with get_connection() as session:
            bm = Note(book_id=book_id, title=title, position=position, selected_text=selected_text, cfi=cfi, comment=comment, user_id=user_id)
            bm.position=position
            session.add(bm)
            session.commit()
            session.refresh(bm)
            return bm
        
    @staticmethod
    def get_notes(book_id, user_id):
        with get_connection() as session:
            return (
                session.query(Note)
                .filter_by(book_id=book_id,
                           user_id=user_id)
                .order_by(Note.id.asc())
                .all()
            )
    
    @staticmethod
    def get_note_by_id(note_id):
        with get_connection() as session:
            return session.query(Note).filter_by(id=note_id).first()
    
    @staticmethod
    def update_note(note_id, title=None, comment=None):
        with get_connection() as session:
            note = session.query(Note).filter_by(id=note_id).first()
            if not note:
                return None
            
            if title is not None:
                note.title = title
            if comment is not None:
                note.comment = comment
            
            
            
            session.commit()
            session.refresh(note)
            return note
        
    @staticmethod
    def delete_note(id):
        with get_connection() as session:
            session.query(Note).filter_by(id=id).delete()
            session.commit()

