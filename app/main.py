from flask import Flask, render_template, session, jsonify, request
from routes.auth_routes import auth_bp
from routes.file_routes import file_bp
from routes.favourite_routes import favourite_bp
from routes.bookmark_routes import bookmark_bp
from routes.note_routes import note_bp
from routes.achievement_routes import achievement_bp
from routes.friend_routes import friends_bp
from routes.serializer_routes import serialize_bp
from routes.group_routes import group_bp
from services.favourites_service import FavoriteService
from services.book_service import BookService
from services.user_service import UserService
from services.achievement_service import AchievementService
from db import init_db, get_connection
from config import Config
from services.elasticsearch_service import create_index
from services.presence_events import init_presence_events
from flask_socketio import SocketIO

app = Flask(__name__)
app.secret_key = Config().SECRET_KEY


app.register_blueprint(auth_bp)
app.register_blueprint(file_bp)
app.register_blueprint(favourite_bp)
app.register_blueprint(bookmark_bp)
app.register_blueprint(note_bp)
app.register_blueprint(achievement_bp)
app.register_blueprint(friends_bp)
app.register_blueprint(serialize_bp)
app.register_blueprint(group_bp)
socketio = SocketIO(app)
init_presence_events(socketio)


@app.route("/manage_roles", methods=["GET", "POST"])
def manage_roles():
    user_id = session.get("user_id")
    user = UserService.get_user_by_id(user_id) if user_id else None
    if not user or getattr(user, 'role', None) != 'admin':
        return jsonify({"error": "Доступ запрещен"}), 403

    if request.method == "GET":
        with get_connection() as db_session:
            users_raw = db_session.query(user.__class__).all()

            all_users = [{"id": u.id, "username": u.username, "role": getattr(u, 'role', 'user')} for u in users_raw]
            return jsonify({"all_users": all_users})

    if request.method == "POST":
        data = request.json or {}
        target_user_id = data.get("user_id")
        new_role = data.get("role")

        if not target_user_id or new_role not in ['admin', 'user']:
            return jsonify({"error": "Неверные параметры"}), 400

        if int(target_user_id) == int(user_id):
            return jsonify({"error": "Вы не можете изменить роль самому себе"}), 400

        with get_connection() as db_session:
            target_user = db_session.query(user.__class__).get(target_user_id)
            if not target_user:
                return jsonify({"error": "Пользователь не найден"}), 404

            target_user.role = new_role
            db_session.commit()
            return jsonify({"success": True})

@app.route("/", methods=["GET", "POST"])
def index():
    d = {
        "authorized": 0,
        "username": None,
        "books": [],
        "favorites": [],
        "has_read_book_achievement": False,
        "current_user": None
    }
    if "authorized" in session:
        user_id = session.get("user_id")
        user = UserService.get_user_by_id(user_id)

        d["authorized"] = 1
        d["current_user"] = user

        d["username"] = user.username if user else None

        raw_favorites = FavoriteService.get_favorites(user_id) or []
        raw_recent = BookService.get_recent_books(user_id) or []

        is_admin = user and getattr(user, 'role', None) == 'admin'

        if not is_admin:
            allowed_book_ids = set(BookService.get_allowed_book_ids(user_id) or [])

            d["favorites"] = [b for b in raw_favorites if
                              getattr(b, 'is_visible_to_all', False) or b.id in allowed_book_ids]
            d["recent_books"] = [b for b in raw_recent if
                                 getattr(b, 'is_visible_to_all', False) or b.id in allowed_book_ids]
        else:
            d["favorites"] = raw_favorites
            d["recent_books"] = raw_recent

        d["has_read_book_achievement"] = UserService.has_read_book_achievement(user_id)
        d["achievements"] = AchievementService.get_user_achievements(user_id)

    return render_template("index.html", **d)

if __name__ == "__main__":
    init_db()
    # Автосоздание стартового админа из .env (ADMIN_EMAIL / ADMIN_PASSWORD).
    # Удобно при частом пересоздании базы — админ появляется сам.
    _cfg = Config()
    UserService.ensure_admin_account(_cfg.ADMIN_USERNAME, _cfg.ADMIN_EMAIL, _cfg.ADMIN_PASSWORD)
    create_index()
    socketio.run(app, host="0.0.0.0", debug=True,  port=3000, allow_unsafe_werkzeug=True)
