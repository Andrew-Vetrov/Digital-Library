from flask import Blueprint, request, jsonify
from services.bookmark_service import BookmarkService

bookmark_bp = Blueprint("bookmark_bp", __name__)

@bookmark_bp.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = 'http://127.0.0.1:3000'
    response.headers['Access-Control-Allow-Credentials'] = 'true'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
    return response


@bookmark_bp.route("/bookmarks/<int:book_id>", methods=["GET"])
def get_bookmarks(book_id):
    bookmarks = BookmarkService.get_bookmarks(book_id)

    return jsonify([
        {
            "id": b.id,
            "title": b.title,
            "position": b.position
        }
        for b in bookmarks
    ])


@bookmark_bp.route("/bookmarks/<int:book_id>", methods=["POST"])
def create_bookmark(book_id):
    data = request.json

    book_id = data.get("book_id")
    title = data.get("title")
    position = data.get("position")

    #if not (book_id and title and position):
    #    return jsonify({"error": "Missing fields"}), 400
    print("Создал закладку")
    bm = BookmarkService.create_bookmark(book_id, title, position)
    print("Создал закладку")
    return jsonify({
        "id": bm.id,
        "title": bm.title,
        "position": bm.position
    }), 201

@bookmark_bp.route("/bookmarks/<int:bookmark_id>", methods=["DELETE"])
def delete_bookmark(bookmark_id):
    BookmarkService.delete_bookmark(bookmark_id)
    return jsonify({"status": "ok"})
