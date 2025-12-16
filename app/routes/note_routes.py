from flask import Blueprint, request, jsonify
from services.note_service import NoteService

note_bp = Blueprint("note_bp", __name__)

@note_bp.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = 'http://127.0.0.1:3000'
    response.headers['Access-Control-Allow-Credentials'] = 'true'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
    return response


@note_bp.route("/notes/<int:book_id>", methods=["GET"])
def get_notes(book_id):
    notes = NoteService.get_notes(book_id)

    return jsonify([
        {
            "id": b.id,
            "title": b.title,
            "position": b.position,
            "selected_text":b.selected_text,
            "cfi":b.cfi
        }
        for b in notes
    ])


@note_bp.route("/notes/<int:book_id>", methods=["POST"])
def create_note(book_id):
    data = request.json

    #book_id = data.get("book_id")
    title = data.get("title")
    position = data.get("position")
    selected_text = data.get("selected_text")
    cfi = data.get("cfi")
    print("\n\n\n",position,"\n\n\n",flush=True)
    #if not (book_id and title and position):
    #    return jsonify({"error": "Missing fields"}), 400
    bm = NoteService.create_note(book_id, title, position, selected_text, cfi)
    print("Создал заметку",flush=True)
    return jsonify({
        "id": bm.id,
        "title": bm.title,
        "position": bm.position,
        "selected_text":bm.selected_text,
        "cfi": bm.cfi
    }), 201

@note_bp.route("/notes/<int:note_id>", methods=["DELETE"])
def delete_note(note_id):
    NoteService.delete_note(note_id)
    return jsonify({"status": "ok"})
