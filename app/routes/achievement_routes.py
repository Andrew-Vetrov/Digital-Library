from flask import Blueprint, jsonify, session
from services.achievement_service import AchievementService

achievement_bp = Blueprint("achievement", __name__)

@achievement_bp.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = 'http://127.0.0.1:3000'
    response.headers['Access-Control-Allow-Credentials'] = 'true'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
    return response

@achievement_bp.route("/achievement/book_read", methods=["POST"])
def book_read_achievement():
    user_id = session.get("user_id")

    if not user_id:
        return jsonify({
            "error": "unauthorized"
        }), 401

    show_popup = AchievementService.give_read_book_achievement(user_id)

    return jsonify({
        "success": True,
        "show_achievement": show_popup
    })