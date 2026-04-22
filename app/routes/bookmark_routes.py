from flask import Blueprint, request, jsonify, session
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
    bookmarks = BookmarkService.get_bookmarks(book_id, session["user_id"])

    return jsonify([
        {
            "id": b.id,
            "title": b.title,
            "position": b.position,
            "cfi": b.cfi
        }
        for b in bookmarks
    ])


@bookmark_bp.route("/bookmarks/<int:book_id>", methods=["POST"])
def create_bookmark(book_id):
    data = request.json

    #book_id = data.get("book_id")
    title = data.get("title")
    position = data.get("position")
    cfi = data.get("cfi")
    print("\n\n\n",position,"\n\n\n",flush=True)
    #if not (book_id and title and position):
    #    return jsonify({"error": "Missing fields"}), 400
    bm = BookmarkService.create_bookmark(book_id, title, position, cfi, session["user_id"])
    print("Создал закладку",flush=True)
    return jsonify({
        "id": "",
        "title": "",
        "position": "",
        "cfi": ""
    }), 201

@bookmark_bp.route("/bookmarks/<int:bookmark_id>", methods=["DELETE"])
def delete_bookmark(bookmark_id):
    BookmarkService.delete_bookmark(bookmark_id)
    return jsonify({"status": "ok"})


@bookmark_bp.route("/bookmarks/<int:bookmark_id>", methods=["PUT"])
def update_bookmark(bookmark_id):
    data = request.json
    
    title = data.get("title")
    
    
    if title is None:
        return jsonify({"error": "No fields to update"}), 400
    
    updated_bookmark = BookmarkService.update_bookmark(bookmark_id, title)
    
    if not updated_bookmark:
        return jsonify({"error": "Bookmark not found"}), 404
    
    return jsonify({
        "id": updated_bookmark.id,
        "title": updated_bookmark.title,
        "position": updated_bookmark.position,
    })