from flask import Blueprint, render_template, request, session, jsonify, redirect, url_for
from services.group_service import GroupService
from services.user_service import UserService

group_bp = Blueprint("group_bp", __name__)


@group_bp.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "http://127.0.0.1:3000"
    response.headers["Access-Control-Allow-Credentials"] = "true"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    return response


def _require_admin():
    """Возвращает (user_id, None) для админа, либо (None, ответ-ошибка)."""
    user_id = session.get("user_id")
    if not user_id:
        return None, (jsonify({"error": "Вы не авторизованы"}), 403)
    user = UserService.get_user_by_id(user_id)
    if not user or getattr(user, "role", None) != "admin":
        return None, (jsonify({"error": "Доступ запрещен. Только для администраторов."}), 403)
    return user_id, None


@group_bp.route("/manage_groups", methods=["GET"])
def manage_groups_page():
    user_id = session.get("user_id")
    user = UserService.get_user_by_id(user_id) if user_id else None
    if not user or getattr(user, "role", None) != "admin":
        return redirect(url_for("index"))
    return render_template("groups.html")


@group_bp.route("/api/groups", methods=["GET", "POST"])
def groups_collection():
    _, err = _require_admin()
    if err:
        return err

    if request.method == "GET":
        return jsonify({"groups": GroupService.list_groups()})

    data = request.get_json(silent=True) or {}
    group_id, error = GroupService.create_group(data.get("name"))
    if error:
        return jsonify({"error": error}), 400
    return jsonify({"success": True, "group_id": group_id}), 201


@group_bp.route("/api/groups/<int:group_id>", methods=["GET", "DELETE"])
def group_item(group_id):
    _, err = _require_admin()
    if err:
        return err

    if request.method == "DELETE":
        ok = GroupService.delete_group(group_id)
        if not ok:
            return jsonify({"error": "Группа не найдена"}), 404
        return jsonify({"success": True})

    detail = GroupService.get_group_detail(group_id)
    if detail is None:
        return jsonify({"error": "Группа не найдена"}), 404
    return jsonify(detail)


@group_bp.route("/api/groups/<int:group_id>/members", methods=["POST"])
def group_members(group_id):
    _, err = _require_admin()
    if err:
        return err
    data = request.get_json(silent=True) or {}
    user_ids = data.get("user_ids", [])
    if not isinstance(user_ids, list):
        return jsonify({"error": "user_ids должен быть списком"}), 400
    if not GroupService.set_members(group_id, [int(u) for u in user_ids]):
        return jsonify({"error": "Группа не найдена"}), 404
    return jsonify({"success": True})


@group_bp.route("/api/groups/<int:group_id>/books", methods=["POST"])
def group_books(group_id):
    _, err = _require_admin()
    if err:
        return err
    data = request.get_json(silent=True) or {}
    book_ids = data.get("book_ids", [])
    if not isinstance(book_ids, list):
        return jsonify({"error": "book_ids должен быть списком"}), 400
    if not GroupService.set_books(group_id, [int(b) for b in book_ids]):
        return jsonify({"error": "Группа не найдена"}), 404
    return jsonify({"success": True})
