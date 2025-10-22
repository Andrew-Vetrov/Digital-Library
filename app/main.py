import os
from flask import Flask,render_template,request,session,redirect,url_for
from random import randint
import hashlib

app = Flask(__name__)

@app.route("/",methods = ["GET","POST"])
def index():
    if request.method == "POST":
        return render_template("index.html")
    elif request.method == "GET":
        d = {"authorized":0,
            "username":None
            }
        if "authorized" in session:
            username = session["authorized"]
            d["authorized"] = 1
            d["username"] = username
        return render_template("index.html",**d)

@app.route("/authorization",methods = ["GET","POST"])
def auth():
    if request.method == "GET":
        return render_template("authorization.html")
    elif request.method == "POST":
        data = dict(request.form)

        sha256 = hashlib.sha256()
        sha256.update(data["email"].encode('utf-8'))
        email = sha256.hexdigest()

        sha256 = hashlib.sha256()
        sha256.update(data["password"].encode('utf-8'))
        userpassword = sha256.hexdigest()

        result = db.check_user_for_authorization((email,userpassword))
        print(result)
        d = {
            "result_of_authorization":1
        }
        if result:
            session["authorized"] = result[0]["username"]
        else:
            result_password = db.select_userpassword_using_email((email,))
            if result_password and result_password != userpassword:
                d["result_of_authorization"] = 2 #пароль неправильный
            else:
                d["result_of_authorization"] = 3 #email неправильный
        return render_template("authorization.html",**d)

@app.route("/registration",methods = ["GET","POST"])
def registration():
    if request.method == "GET":
        return render_template("registration.html")
    elif request.method == "POST":
        data = dict(request.form)
        username = data["username"]

        sha256 = hashlib.sha256()
        sha256.update(data["email"].encode('utf-8'))
        email = sha256.hexdigest()

        sha256 = hashlib.sha256()
        sha256.update(data["password"].encode('utf-8'))
        userpassword = sha256.hexdigest()

        print(type(username),type(email),type(userpassword))
        result1 = db.check_user_registration_name((username,))
        result2 = db.check_user_registration_email((email,))
        print(result1,result2)
        error_dict = {
            "wrong_username":0,
            "wrong_email":0
        }
        if result1 and result2:
            db.insert_user((username,email,userpassword))
            session["authorized"] = username
        if not result1:
            error_dict["wrong_username"] = 1
        if not result2:
            error_dict["wrong_email"] = 1
        return render_template("registration.html",**error_dict)

if __name__=="__main__":
    app.run(host = "127.0.0.1", port=3000)