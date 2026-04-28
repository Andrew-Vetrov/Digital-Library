from flask import Flask, render_template, session
from routes.auth_routes import auth_bp
from routes.file_routes import file_bp
from routes.favourite_routes import favourite_bp
from routes.bookmark_routes import bookmark_bp
from routes.note_routes import note_bp
from routes.achievement_routes import achievement_bp
from routes.friend_routes import friends_bp
from services.favourites_service import FavoriteService
from services.book_service import BookService
from services.user_service import UserService
from db import init_db
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
socketio = SocketIO(app)
init_presence_events(socketio)

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
        # Получаем объект пользователя из базы
        user = UserService.get_user_by_id(user_id)
        d["authorized"] = 1
        d["current_user"] = user
        d["username"] = session["authorized"]
        d["favorites"] = FavoriteService.get_favorites(session.get("user_id"))
        d["recent_books"] = BookService.get_recent_books(session.get("user_id"))
        d["has_read_book_achievement"] = UserService.has_read_book_achievement(session.get("user_id"))
        

    return render_template("index.html", **d)


if __name__ == "__main__":
    init_db()
    create_index()
    socketio.run(app, host="0.0.0.0", debug=True,  port=3000, allow_unsafe_werkzeug=True)
