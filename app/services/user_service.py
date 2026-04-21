import psycopg2.extras
from db import get_connection
from models.models import User

class UserService:
    @staticmethod
    def find_by_email(email, password):
        with get_connection() as session:
            users = session.query(User).filter(User.email == email, User.password_hash == password).all()
            if (len(users) > 0):
                return users
            return None
    @staticmethod
    def find_password_by_email(email):
        with get_connection() as session:
            user = session.query(User).filter(User.email == email).first()
            if user:
                return user.password_hash
            return None
            

    @staticmethod
    def username_available(username):
        with get_connection() as session:
            users = session.query(User).filter(User.username == username).all()
            if users:
                return False
            return True

    @staticmethod
    def email_available(email):
        with get_connection() as session:
            users = session.query(User).filter(User.email == email).all()
            if users:
                return False
            return True

    @staticmethod
    def insert_user(username, email, password):
        with get_connection() as session:
            newUser = User(username, email, password)
            session.add(newUser)
            session.commit()
                
    @staticmethod
    def has_read_book_achievement(user_id):
        with get_connection() as session:
            user = session.query(User).get(user_id)
            return user.has_read_book_achievement if user else False
        
    @staticmethod
    def get_user_by_id(user_id):
        with get_connection() as session:
            user = session.query(User).get(user_id)
            return user
