from flask import Blueprint, render_template, request, Response, redirect, url_for, session, abort, flash, jsonify
import os
from minio import Minio
from services.book_service import BookService
from services.achievement_service import AchievementService
from services.user_service import UserService
from minio.error import S3Error
from datetime import timedelta
from models.models import User, Book, BookRating, BookAccess
from db import get_connection
from services.elasticsearch_service import search_books, semantic_search, add_search_history, get_search_history
import sys
import json
from flask import after_this_request
from io import BytesIO
from werkzeug.datastructures import FileStorage

file_bp = Blueprint("file", __name__)

minio_client = Minio(
    os.getenv("MINIO_ENDPOINT", "minio:9000"),
    access_key=os.getenv("MINIO_ROOT_USER"),
    secret_key=os.getenv("MINIO_ROOT_PASSWORD"),
    secure=False
)

BUCKET_NAME = os.getenv("BUCKET_NAME", "librarybucket")

policy = f'''
{{
    "Version": "2012-10-17",
    "Statement": [
        {{
            "Effect": "Allow",
            "Principal": "*",
            "Action": ["s3:GetObject"],
            "Resource": ["arn:aws:s3:::{BUCKET_NAME}/*"]
        }}
    ]
}}
'''


def ensure_bucket_exists():
    try:
        if not minio_client.bucket_exists(BUCKET_NAME):
            minio_client.make_bucket(BUCKET_NAME)
            print(f"Бакет {BUCKET_NAME} создан")
        else:
            print(f"Бакет {BUCKET_NAME} уже существует")
    except Exception as e:
        print(f"Ошибка при создании бакета: {e}")


ensure_bucket_exists()
minio_client.set_bucket_policy(BUCKET_NAME, policy)


@file_bp.route("/upload_file", methods=["GET", "POST"])
def upload_file():
    uid = session.get("user_id")
    if not uid:
        return redirect(url_for("auth_bp.authorization"))

    perms = UserService.get_user_permissions(uid)
    if not perms["can_upload_files"]:
        abort(403, description="Загрузка книг запрещена настройками вашей группы.")

    if request.method == "GET":
        return render_template("upload_file.html")

    if request.method == "POST":
        files = []

        for f in request.files.getlist("file"):
            if f and f.filename:
                files.append({
                    "filename": f.filename,
                    "content": BytesIO(f.read()),
                    "content_type": f.content_type
                })
        genre = request.form.get("genre")

        if not files or files[0]["filename"] == "":
            return render_template("upload_file.html", message="Ошибка: файл не выбран")


        def generate():
            total = len(files)
            yield json.dumps({"type": "start", "total": total}) + "\n"

            success_count = 0
            error_messages = []

            for idx, file in enumerate(files, start=1):
                if not file or file["filename"] == "":
                    continue
                if not file["filename"].lower().endswith(".epub"):
                    error_messages.append(f"Файл '{file['filename']}' пропущен: допустим только формат EPUB")
                    yield json.dumps({
                        "type": "progress",
                        "current": idx,
                        "total": total,
                        "filename": file["filename"],
                        "status": "error",
                        "message": f"Файл '{file['filename']}' пропущен: допустим только формат EPUB"
                    }) + "\n"
                    continue

                try:
                    file["content"].seek(0)
                    wrapped_file = FileStorage(
                        stream=file["content"],
                        filename=file["filename"],
                        content_type=file["content_type"]
                    )
                    title = BookService.upload_book(wrapped_file, genre)
                    success_count += 1
                    yield json.dumps({
                        "type": "progress",
                        "current": idx,
                        "total": total,
                        "filename": file["filename"],
                        "status": "success",
                        "title": title,
                        "message": f"Книга '{title}' загружена"
                    }) + "\n"
                except Exception as e:
                    error_messages.append(f"Ошибка при загрузке '{file['filename']}': {e}")
                    yield json.dumps({
                        "type": "progress",
                        "current": idx,
                        "total": total,
                        "filename": file["filename"],
                        "status": "error",
                        "message": str(e)
                    }) + "\n"

            yield json.dumps({
                "type": "complete",
                "success_count": success_count,
                "error_count": len(error_messages),
                "errors": error_messages
            }) + "\n"

        return Response(generate(), mimetype='application/x-ndjson')

@file_bp.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = 'http://127.0.0.1:3000'
    response.headers['Access-Control-Allow-Credentials'] = 'true'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
    return response


@file_bp.route("/delete/<int:book_id>", methods=["POST"])
def delete_book(book_id):
    user_authorized = session.get("authorized", 0)
    
    if not user_authorized:
        abort(403, "Вы не авторизованы")

    uid = session.get("user_id")
    
    with get_connection() as db_session:
        perms = UserService.get_user_permissions(uid)
        if not perms["can_manage_books_access"]:
            abort(403, description="Доступ запрещен. Только для администраторов.")

    BookService.delete_book(book_id)
    flash("Книга успешно удалена!", "success")
    return redirect(url_for("file.list_files"))


@file_bp.route("/files", methods=["GET"])
def list_files():
    PUBLIC_ENDPOINT = os.getenv("MINIO_PUBLIC_ENDPOINT", "http://localhost:9000")

    query = request.args.get("q")
    semantic = request.args.get("semantic") == "on"
    sort_by = request.args.get('sort', 'title')
    order = request.args.get('order', 'asc')

    user_id = session.get("user_id")

    user_ratings = {}

    is_admin = False
    allowed_book_ids = set()

    if user_id:
        with get_connection() as db_session:
            ratings = db_session.query(BookRating).filter_by(user_id=user_id).all()
            user_ratings = {r.book_id: r.score for r in ratings}

            perms = UserService.get_user_permissions(user_id)
            if perms["can_upload_files"]:
                is_admin = True
            else:
                allowed_book_ids = set(BookService.get_allowed_book_ids(user_id))

    if user_id and query and query.strip():
        add_search_history(user_id, query.strip())

    if query and query.strip():
        if semantic:
            es_results = semantic_search(query.strip())
        else:
            es_results = search_books(query.strip())

        book_ids = [r["id"] for r in es_results]
        books = BookService.find_books(book_ids)
    else:
        books = BookService.find_books()

    if not is_admin:
        books = [b for b in books if b.is_visible_to_all or b.id in allowed_book_ids]

    author = request.args.get("author")
    publisher = request.args.get("publisher")
    genre = request.args.get("genre")

    if author:
        books = [b for b in books if b.author and author.lower() in b.author.lower()]
    if publisher:
        books = [b for b in books if b.publisher and publisher.lower() in b.publisher.lower()]
    if genre:
        books = [b for b in books if b.genre == genre]

    reverse_order = (order == 'desc')

    if sort_by == 'rating':
        books.sort(key=lambda b: getattr(b, 'average_rating', 0.0) or 0.0, reverse=reverse_order)
    else:
        books.sort(key=lambda b: (b.title or "").lower(), reverse=reverse_order)

    try:
        for book in books:
            book.user_score = user_ratings.get(book.id)

            if getattr(book, "cover_key", None):
                book.cover_url = f"{PUBLIC_ENDPOINT}/{BUCKET_NAME}/{book.cover_key}"
            else:
                book.cover_url = None

        genres = sorted({b.genre for b in books if b.genre})

        return render_template("files.html",
                               books=books,
                               genres=genres,
                               request=request,
                               current_sort=sort_by,
                               current_order=order,
                               is_admin=is_admin)

    except Exception as e:
        return render_template("upload_file.html", message=f"Ошибка: {e}")


@file_bp.route("/rate/<int:book_id>", methods=["POST"])
def rate_book(book_id):
    user_id = session.get("user_id")
    if not session.get("authorized") or not user_id:
        return jsonify({"error": "Unauthorized"}), 403

    data = request.get_json()
    if not data or 'score' not in data:
        return jsonify({"error": "Missing score"}), 400

    try:
        score = int(data['score'])
        success = BookService.set_book_rating(user_id, book_id, score)

        if success:
            AchievementService.evaluate(user_id)
            book = BookService.find_book_by_id(book_id)
            return jsonify({
                "success": True,
                "new_rating": book.average_rating or 0.0,
                "user_score": score
            })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({"success": False}), 400


@file_bp.route("/search_history", methods=["GET"])
def query_list():
    user_id = session.get("user_id")
    if not user_id:
        abort(403, "Вы не авторизованы")

    history = get_search_history(user_id)

    return render_template(
        "search_history.html",
        history=history
    )


@file_bp.route("/reader/<int:id>", methods=["GET"])
def read_book(id):
    try:
        print(id, file=sys.stderr)
        book = BookService.find_book_by_id(id)

        obj_name = book.minio_key
        print(obj_name, file=sys.stderr)

        MINIO_DOMAIN = os.getenv("MINIO_DOMAIN")
        external_url = f"{MINIO_DOMAIN}/{BUCKET_NAME}/{obj_name}"
        print("URL = ", external_url, file=sys.stderr)
        return render_template("reader.html", book_url=external_url, book_id=id)

    except S3Error as e:
        return f"Ошибка при открытии книги: {e}"


@file_bp.route("/reading_progress/<int:book_id>", methods=["GET", "POST"])
def reading_position(book_id):
    if request.method == 'GET':
        try:
            #ReadingHistory
            #book = BookService.find_book_by_id(book_id)
            #loc = book.last_position
            #cfi = book.cfi
            progress = BookService.get_reading_position(book_id=book_id,
                                                        user_id=session["user_id"])
            loc = progress.last_position
            cfi = progress.cfi
            return jsonify({
                'loc': loc,
                'cfi': cfi
            })
        except Exception as e:
            print(e)
            return jsonify({
                'error': str(e),
                'loc': None
            }), 500

    elif request.method == 'POST':
        data = request.get_json()

        if not data or 'loc' not in data:
            return jsonify({'error': 'Missing loc'}), 400

        try:
            loc = data['loc']
            cfi = data['cfi']
            BookService.set_reading_position(book_id, session["user_id"], loc, cfi)
            BookService.update_reading_history(session.get("user_id"), book_id)
            return jsonify({
                'success': True,
                'loc': loc,
                'book_id': book_id,
                "cfi": cfi
            })

        except ValueError:
            return jsonify({'error': 'loc must be a number'}), 400
        except Exception as e:
            print(str(e))
            return jsonify({'error': str(e)}), 500


@file_bp.route("/cover/<int:book_id>")
def serve_cover(book_id):
    from io import BytesIO
    from flask import send_file

    with get_connection() as session:
        book = session.query(Book).get(book_id)
        if not book or not book.cover_key:
            return "Нет обложки", 404
    data = minio_client.get_object("librarybucket", book.cover_key).read()
    return send_file(BytesIO(data), mimetype="image/jpeg")


@file_bp.route("/manage_access/<int:book_id>", methods=["GET", "POST"])
def manage_access(book_id):
    uid = session.get("user_id")
    if not uid:
        return jsonify({"error": "Вы не авторизованы"}), 403

    perms = UserService.get_user_permissions(uid)
    if not perms["can_manage_books_access"]:
        return jsonify({"error": "Управление правами доступа ограничено настройками вашей группы"}), 403

    with get_connection() as db_session:
        book = db_session.query(Book).filter_by(id=book_id).first()
        if not book:
            return jsonify({"error": "Книга не найдена"}), 404

        if request.method == "GET":
            access_records = db_session.query(BookAccess).filter_by(book_id=book_id).all()
            allowed_user_ids = [record.user_id for record in access_records]

            all_users = db_session.query(User).order_by(User.username).all()
            users_list = [{"id": u.id, "username": u.username} for u in all_users]

            return jsonify({
                "book_id": book.id,
                "title": book.title,
                "is_visible_to_all": book.is_visible_to_all,
                "allowed_user_ids": allowed_user_ids,
                "all_users": users_list
            })

        elif request.method == "POST":
            data = request.get_json()
            if not data:
                return jsonify({"error": "Отсутствуют данные запроса"}), 400

            is_visible_to_all = data.get("is_visible_to_all", False)
            user_ids = data.get("user_ids", [])

            book.is_visible_to_all = is_visible_to_all

            db_session.query(BookAccess).filter_by(book_id=book_id).delete()

            if not is_visible_to_all:
                for u_id in user_ids:
                    user_exists = db_session.query(User).filter_by(id=u_id).first()
                    if user_exists:
                        new_access = BookAccess(book_id=book_id, user_id=u_id)
                        db_session.add(new_access)

            db_session.commit()
            return jsonify({
                "success": True,
                "message": "Права доступа к книге успешно обновлены!"
            })
