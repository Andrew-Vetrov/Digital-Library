from flask import Blueprint, jsonify, session, render_template, redirect, url_for
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

    # Событие «дочитал книгу» гарантированно выдаёт ачивку за первую книгу,
    # затем пересчитываем остальные (счётчики книг/заметок/оценок и т.д.).
    newly = []
    first = AchievementService.award(user_id, "first_book")
    if first:
        newly.append(first)
    newly.extend(AchievementService.evaluate(user_id))

    return jsonify({
        "success": True,
        "show_achievement": len(newly) > 0,
        "new_achievements": newly,
    })


@achievement_bp.route("/achievements", methods=["GET"])
def achievements_page():
    if not session.get("user_id"):
        return redirect(url_for("auth.authorization"))
    return render_template("achievements.html")


@achievement_bp.route("/api/achievements", methods=["GET"])
def achievements_json():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401
    return jsonify({"achievements": AchievementService.get_user_achievements(user_id)})
