from flask import Blueprint, render_template, request, session, current_app, jsonify
import hashlib
from services.user_service import UserService
import sys
import os
from minio import Minio
from minio.error import S3Error



minio_client = Minio(
    "minio:9000",
    access_key=os.getenv("MINIO_ROOT_USER"),
    secret_key=os.getenv("MINIO_ROOT_PASSWORD"),
    secure=False
)

file_bp = Blueprint("file", __name__)

@file_bp.route("/upload_file", methods=["GET", "POST"])
def upload_file():
    if request.method == "GET":

        return render_template("upload_file.html")
    if request.method == "POST":
        try:
            if 'file' not in request.files:
                return render_template("upload_file.html", message = "Ошибка при загрузке файла")
            
            file = request.files['file']
            
            if file.filename == '':
                return render_template("upload_file.html", message = "Ошибка при загрузке файла")
            
            file.seek(0, os.SEEK_END)
            file_size = file.tell()
            file.seek(0)
            
            
            
            bucket_name = "librarybucket"
            if not minio_client.bucket_exists(bucket_name):
                minio_client.make_bucket(bucket_name)
            
            minio_client.put_object(
                bucket_name,
                file.filename,
                file,
                length=file_size
            )
            
            return render_template("upload_file.html", message = "Файл " + file.filename + " успешно загрузился")

        except Exception as e:
            return f"Error uploading file: {e}"


