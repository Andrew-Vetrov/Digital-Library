import psycopg2.extras
from db import get_connection
from db import User

class UserService:
    @staticmethod
    def find_by_credentials(email, password):
        query = "SELECT username FROM users WHERE email_hash=%s AND password_hash=%s"
        with get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                cur.execute(query, (email, password))
                return cur.fetchall()

    @staticmethod
    def find_password_by_email(email):
        query = "SELECT password_hash FROM users WHERE email_hash=%s"
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (email,))
                res = cur.fetchone()
                return res[0] if res else None

    @staticmethod
    def username_available(username):
        query = "SELECT 1 FROM users WHERE username=%s"
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (username,))
                return not cur.fetchone()

    @staticmethod
    def email_available(email):
        query = "SELECT 1 FROM users WHERE email_hash=%s"
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (email,))
                return not cur.fetchone()

    @staticmethod
    def insert_user(username, email, password):
        query = "INSERT INTO users (username, email_hash, password_hash) VALUES (%s, %s, %s)"
        with get_connection() as session:
            newUser = User(username, email, password)
            session.add(newUser)
            session.commit()
                
