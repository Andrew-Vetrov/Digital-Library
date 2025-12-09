from flask import Blueprint, redirect, session
from services.favourites_service import FavoriteService

favourite_bp = Blueprint("favourite", __name__)


@favourite_bp.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = 'http://127.0.0.1:3000'
    response.headers['Access-Control-Allow-Credentials'] = 'true'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
    return response

@favourite_bp.post("/favorite/<int:book_id>")
def add_favorite(book_id):
    if not session.get("user_id"):
        return redirect("/authorization")

    user_id = session["user_id"]

    FavoriteService.add_favorite(user_id, book_id)

    return redirect("/files")


@favourite_bp.post("/unfavorite/<int:book_id>")
def remove_favorite(book_id):
    if not session.get("authorized"):
        return redirect("/authorization")

    user_id = session["user_id"]
    print("\n\n\nУдаляю книгу\n\n\n")
    FavoriteService.remove_favorite(user_id, book_id)

    return redirect("/")
