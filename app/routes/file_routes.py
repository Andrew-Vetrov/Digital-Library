from flask import Blueprint, render_template, request, Response
import os
from minio import Minio
from flask import Blueprint, redirect, url_for, session, abort, flash
from services.book_service import BookService
from minio.error import S3Error
from datetime import timedelta
from models.models import Book
from db import get_connection
import sys
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

# Вызываем при инициализации
ensure_bucket_exists()

minio_client.set_bucket_policy(BUCKET_NAME, policy)

cors_config = """"
{
    "CORSRules": [
        {
            "AllowedHeaders": ["*"],
            "AllowedMethods": ["GET", "HEAD"],
            "AllowedOrigins": ["*"],
            "ExposeHeaders": ["ETag"],
            "MaxAgeSeconds": 3000
        }
    ]
}
"""

@file_bp.route("/upload_file", methods=["GET", "POST"])
def upload_file():
    print("Просто что-то", flush=True)
    if request.method == "GET":
        print("Файл прилетел get", flush=True)
        return render_template("upload_file.html")

    if request.method == "POST":
        print("Файл прилетел post", flush=True)
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

@file_bp.route("/delete/<int:book_id>", methods=["POST"])
def delete_book(book_id):
    user_authorized = session.get("authorized", 0) # это задел на более менее какое-то упраление книгами, 
                                     # ща кто-угодно может удалять, но это изи фиксится
    if not user_authorized:
        abort(403, "Вы не авторизованы")

    # 🧠 Проверяем, что это админ
    if not user_authorized:
        abort(403, "Доступ запрещён")

    BookService.delete_book(book_id)
    flash("Книга успешно удалена!", "success")
    return redirect(url_for("file.list_files"))

@file_bp.route("/files", methods=["GET"])
def list_files():
    PUBLIC_ENDPOINT = os.getenv("MINIO_PUBLIC_ENDPOINT", "http://localhost:9000")
    try:
        books = BookService.find_books()
        for book in books:
            if book.cover_key:
                book.cover_url = f"{PUBLIC_ENDPOINT}/{BUCKET_NAME}/{book.cover_key}"
            else:
                book.cover_url = None

        return render_template("files.html", books=books)
    except Exception as e:
        return render_template("upload_file.html", message=f"Ошибка при загрузке списка книг: {e}")
    
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
        return render_template("reader.html", book_url=external_url, id=id)

    except S3Error as e:
        return f"Ошибка при открытии книги: {e}"
    
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
