import psycopg2.extras
from db import get_connection
from db import User

class UserService:
    @staticmethod
    def find_by_email(email, password):
        query = "SELECT username FROM users WHERE email_hash=%s AND password_hash=%s"
        with get_connection() as session:
            users = session.query(User).filter(User.email == email, User.password_hash == password).all()
            if (len(users) > 0):
                return users
            return None
    @staticmethod
    def find_password_by_email(email):
        query = "SELECT password_hash FROM users WHERE email_hash=%s"
        with get_connection() as session:
            user = session.query(User).filter(User.email == email).first()
            if user:
                return user.password_hash
            return None
            

    @staticmethod
    def username_available(username):
        query = "SELECT 1 FROM users WHERE username=%s"
        with get_connection() as session:
            users = session.query(User).filter(User.username == username).all()
            if users:
                return False
            return True

    @staticmethod
    def email_available(email):
        query = "SELECT 1 FROM users WHERE email_hash=%s"
        with get_connection() as session:
            users = session.query(User).filter(User.email == email).all()
            if users:
                return False
            return True

    @staticmethod
    def insert_user(username, email, password):
        query = "INSERT INTO users (username, email_hash, password_hash) VALUES (%s, %s, %s)"
        with get_connection() as session:
            newUser = User(username, email, password)
            session.add(newUser)
            session.commit()
                
