from flask import Flask, render_template, session
from routes.auth_routes import auth_bp
from routes.file_routes import file_bp
from routes.favourite_routes import favourite_bp
from services.favourites_service import FavoriteService
from db import init_db
from config import Config
from search_index import create_index

app = Flask(__name__)
app.secret_key = Config().SECRET_KEY

app.register_blueprint(auth_bp)
app.register_blueprint(file_bp)
app.register_blueprint(favourite_bp)

@app.route("/", methods=["GET", "POST"])
def index():
    d = {
        "authorized": 0,
        "username": None,
        "books": [],
        "favorites": []
    }
    if "authorized" in session:
        d["authorized"] = 1
        d["username"] = session["authorized"]
        d["favorites"] = FavoriteService.get_favorites(session.get("user_id"))

    return render_template("index.html", **d)


if __name__ == "__main__":
    init_db()
    create_index()
    app.run(host="0.0.0.0", port=3000, debug=True)
