from flask import Blueprint, render_template, request, session, redirect, url_for
import hashlib
from services.user_service import UserService
import sys
auth_bp = Blueprint("auth", __name__)

@auth_bp.route("/authorization", methods=["GET", "POST"])
def authorization():
    if request.method == "GET":
        return render_template("authorization.html")

    data = dict(request.form)

    email = data["email"]
    password = hashlib.sha256(data["password"].encode()).hexdigest()

    result = UserService.find_by_email(email, password)
    d = {"result_of_authorization": 1}

    print(result, file=sys.stderr)
    
    if result:
        session["authorized"] = result[0].username
    else:
        result_password = UserService.find_password_by_email(email)
        if result_password and result_password != password:
            d["result_of_authorization"] = 2  # неправильный пароль
        else:
            d["result_of_authorization"] = 3  # неправильный email

    return render_template("authorization.html", **d)


@auth_bp.route("/registration", methods=["GET", "POST"])
def registration():
    if request.method == "GET":
        return render_template("registration.html")

    data = dict(request.form)
    username = data["username"]
    email = data["email"]
    password = hashlib.sha256(data["password"].encode()).hexdigest()

    username_ok = UserService.username_available(username)
    email_ok = UserService.email_available(email)

    error_dict = {"wrong_username": 0, "wrong_email": 0}

    if username_ok and email_ok:
        UserService.insert_user(username, email, password)
        session["authorized"] = username
    if not username_ok:
        error_dict["wrong_username"] = 1
    if not email_ok:
        error_dict["wrong_email"] = 1

    return render_template("registration.html", **error_dict)

@auth_bp.route("/sign_out")
def sign_out():
    try:
        del session["authorized"]
    except Exception as ex:
        print(ex)
    return redirect(url_for("index"))