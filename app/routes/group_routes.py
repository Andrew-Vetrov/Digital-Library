from flask import Blueprint, render_template, request, session, jsonify, redirect, url_for
from services.group_service import GroupService
from services.user_service import UserService
from db import get_connection
from models.models import GroupMember, Group

group_bp = Blueprint("group_bp", __name__)


@group_bp.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "http://127.0.0.1:3000"
    response.headers["Access-Control-Allow-Credentials"] = "true"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    return response


def _require_group_management(group_id=None):
    """Проверяет права на управление группами.
    Если указан group_id, менеджер из группы не может редактировать саму эту группу.
    """
    user_id = session.get("user_id")
    if not user_id:
        return None, (jsonify({"error": "Вы не авторизованы"}), 401)

    user = UserService.get_user_by_id(user_id)
    if not user:
        return None, (jsonify({"error": "Пользователь не найден"}), 403)

    if user.role == "admin":
        return user_id, None

    perms = UserService.get_user_permissions(user_id)
    if not perms["can_manage_groups"]:
        return None, (jsonify({"error": "Доступ запрещен. Недостаточно прав управления группами."}), 403)

    if group_id is not None:
        with get_connection() as db_session:
            is_member = db_session.query(GroupMember).filter_by(group_id=group_id, user_id=user_id).first()
            if is_member:
                return None, (
                    jsonify({"error": "Вы не можете изменять настройки группы, участником которой являетесь"}), 403)

    return user_id, None


@group_bp.route("/manage_groups", methods=["GET"])
def manage_groups_page():
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("index"))

    perms = UserService.get_user_permissions(user_id)
    if not perms["can_manage_groups"]:
        return redirect(url_for("index"))

    return render_template("groups.html")


@group_bp.route("/api/groups", methods=["GET", "POST"])
def groups_collection():
    _, err = _require_group_management()
    if err: return err

    if request.method == "GET":
        return jsonify({"groups": GroupService.list_groups()})

    data = request.get_json(silent=True) or {}
    group_id, error = GroupService.create_group(data.get("name"))
    if error:
        return jsonify({"error": error}), 400
    return jsonify({"success": True, "group_id": group_id}), 201


@group_bp.route("/api/groups/<int:group_id>", methods=["GET", "DELETE"])
def group_item(group_id):
    _, err = _require_group_management(group_id if request.method == "DELETE" else None)
    if err: return err

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
    _, err = _require_group_management(group_id)
    if err: return err

    data = request.get_json(silent=True) or {}
    user_ids = data.get("user_ids", [])
    if not isinstance(user_ids, list):
        return jsonify({"error": "user_ids должен быть списком"}), 400
    if not GroupService.set_members(group_id, [int(u) for u in user_ids]):
        return jsonify({"error": "Группа не найдена"}), 404
    return jsonify({"success": True})


@group_bp.route("/api/groups/<int:group_id>/books", methods=["POST"])
def group_books(group_id):
    _, err = _require_group_management(group_id)
    if err: return err

    data = request.get_json(silent=True) or {}
    book_ids = data.get("book_ids", [])
    if not isinstance(book_ids, list):
        return jsonify({"error": "book_ids должен быть списком"}), 400
    if not GroupService.set_books(group_id, [int(b) for b in book_ids]):
        return jsonify({"error": "Группа не найдена"}), 404
    return jsonify({"success": True})


@group_bp.route("/api/groups/<int:group_id>/permissions", methods=["POST"])
def group_permissions(group_id):
    _, err = _require_group_management(group_id)
    if err: return err

    data = request.get_json(silent=True) or {}

    with get_connection() as db_session:
        group = db_session.query(Group).get(group_id)
        if not group:
            return jsonify({"error": "Группа не найдена"}), 404

        group.deny_download_data = bool(data.get("deny_download_data"))
        group.deny_import_data = bool(data.get("deny_import_data"))
        group.deny_friends = bool(data.get("deny_friends"))
        group.allow_upload_files = bool(data.get("allow_upload_files"))
        group.allow_manage_groups = bool(data.get("allow_manage_groups"))
        group.allow_manage_books_access = bool(data.get("allow_manage_books_access"))

        db_session.commit()
    return jsonify({"success": True})