from flask import Blueprint, render_template, request
import os
from minio import Minio
from services.book_service import BookService  # 👈 подключаем сервис
from minio.error import S3Error
from datetime import timedelta

file_bp = Blueprint("file", __name__)

minio_client = Minio(
    os.getenv("MINIO_ENDPOINT", "minio:9000"),
    access_key=os.getenv("MINIO_ROOT_USER"),
    secret_key=os.getenv("MINIO_ROOT_PASSWORD"),
    secure=False
)

BUCKET_NAME = os.getenv("MINIO_BUCKET", "librarybucket")

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


@file_bp.route("/files", methods=["POST", "GET"])
def list_files():
    try:
        if not minio_client.bucket_exists(BUCKET_NAME):
            return render_template("upload_file.html", message="Бакет пуст или не существует")

        objects = minio_client.list_objects(BUCKET_NAME, recursive=True)
        files = [obj.object_name for obj in objects if not obj.object_name.startswith("covers/")]

        return render_template("files.html", files=files)

    except S3Error as e:
        return render_template("upload_file.html", message=f"Ошибка MinIO: {e}")

@file_bp.route("/reader/<filename>")
def read_book(filename):
    try:
        url = minio_client.get_presigned_url(
            "GET",
            BUCKET_NAME,
            filename,
            expires=timedelta(hours=1)
        )
        return render_template("reader.html", book_url=url, filename=filename)

    except S3Error as e:
        return f"Ошибка при открытии книги: {e}"