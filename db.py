import psycopg2
import psycopg2.extras

# Настройки подключения
DB_CONFIG = {
    "dbname": "flask_auth",
    "user": "postgres",       # поменяй на своего пользователя
    "password": "postgres",   # и пароль
    "host": "localhost",
    "port": 5432
}

def get_connection():
    return psycopg2.connect(**DB_CONFIG)

# --- Функции работы с пользователями ---

def check_user_for_authorization(params):
    """Проверка, что пользователь с email и паролем существует."""
    query = "SELECT username FROM users WHERE email_hash=%s AND password_hash=%s"
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(query, params)
            res = cur.fetchall()
            return res  # [{'username': 'bob'}] или []

def select_userpassword_using_email(params):
    """Получить пароль по email."""
    query = "SELECT password_hash FROM users WHERE email_hash=%s"
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            res = cur.fetchone()
            return res[0] if res else None

def check_user_registration_name(params):
    """Проверить, свободно ли имя пользователя."""
    query = "SELECT 1 FROM users WHERE username=%s"
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            return not cur.fetchone()  # True, если свободно

def check_user_registration_email(params):
    """Проверить, свободен ли email."""
    query = "SELECT 1 FROM users WHERE email_hash=%s"
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            return not cur.fetchone()

def insert_user(params):
    """Вставить нового пользователя."""
    query = "INSERT INTO users (username, email_hash, password_hash) VALUES (%s, %s, %s)"
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
        conn.commit()
