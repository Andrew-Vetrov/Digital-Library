from flask import Blueprint, render_template, request, session, current_app
import hashlib
from services.user_service import UserService
import sys
import os

file_bp = Blueprint("file", __name__)

@file_bp.route("/upload_file", methods=["GET", "POST"])
def upload_file():
    if request.method == "GET":

        return render_template("upload_file.html")
    if request.method == "POST":

        print(request.files, file = sys.stderr)
        file = request.files['file']
        UPLOAD_FOLDER = current_app.instance_path[:-9:]+f'/data/'
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
        file.save(UPLOAD_FOLDER+file.filename)
        return render_template("upload_file.html", message = "Файл " + file.filename + " успешно загружен, ежжи")



