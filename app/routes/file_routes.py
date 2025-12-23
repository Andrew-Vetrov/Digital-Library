from flask import Blueprint, render_template, request, Response, redirect, url_for, session, abort, flash, jsonify
import os
from minio import Minio
from services.book_service import BookService
from minio.error import S3Error
from datetime import timedelta
from models.models import Book
from db import get_connection
from services.elasticsearch_service import search_books, semantic_search, add_search_history, get_search_history
import sys
import json
from flask import after_this_request

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
    if request.method == "GET":
        return render_template("upload_file.html")

    if request.method == "POST":
        file = request.files.get("file")
        genre = request.form.get("genre")

        if not file or file.filename == "":
            return render_template("upload_file.html", message="Ошибка: файл не выбран")

        if not file.filename.endswith(".epub"):
            return render_template("upload_file.html", message="Ошибка: допустим только формат EPUB")

        try:
            title = BookService.upload_book(file, genre)
            return render_template("upload_file.html", message=f"Книга '{title}' успешно загружена!")
        except Exception as e:
            return render_template("upload_file.html", message=f"Ошибка при загрузке: {e}")


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

    BookService.delete_book(book_id)
    flash("Книга успешно удалена!", "success")
    return redirect(url_for("file.list_files"))


@file_bp.route("/files", methods=["GET"])
def list_files():
    PUBLIC_ENDPOINT = os.getenv("MINIO_PUBLIC_ENDPOINT", "http://localhost:9000")

    query = request.args.get("q")
    semantic = request.args.get("semantic") == "on"

    user_id = session.get("user_id")
    if user_id and query and query.strip():
        add_search_history(user_id, query.strip())

    if query and query.strip():
        if semantic:
            es_results = semantic_search(query.strip())
        else:
            es_results = search_books(query.strip())

        book_ids = []
        for r in es_results:
            book_ids.append(r["id"])

        books = BookService.find_books(book_ids)

        return render_template("files.html", books=books, genres=[], request=request)

    author = request.args.get("author")
    publisher = request.args.get("publisher")
    genre = request.args.get("genre")

    try:
        books = BookService.find_books()

        if author:
            books = [b for b in books if author.lower() in b.author.lower()]

        if publisher:
            books = [b for b in books if b.publisher and publisher.lower() in b.publisher.lower()]

        if genre:
            books = [b for b in books if b.genre == genre]

        for book in books:
            if getattr(book, "cover_key", None):
                book.cover_url = f"{PUBLIC_ENDPOINT}/{BUCKET_NAME}/{book.cover_key}"
            else:
                book.cover_url = None

        all_books = BookService.find_books()
        genres = sorted({b.genre for b in all_books if b.genre})

        return render_template("files.html", books=books, genres=genres, request=request)

    except Exception as e:
        return render_template("upload_file.html", message=f"Ошибка: {e}")

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
            book = BookService.find_book_by_id(book_id)
            loc = book.last_position
            cfi = book.cfi
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
            BookService.set_reading_position(book_id, loc, cfi)
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
