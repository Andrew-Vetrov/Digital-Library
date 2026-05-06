from flask import Blueprint, request, session, jsonify, redirect, url_for, flash, render_template
from services.user_service import UserService, FriendService
from models.models import User, Bookmark, Note
from db import get_connection

friends_bp = Blueprint('friends', __name__)

# 1. Добавление по имени пользователя (через форму)
@friends_bp.route('/friends/add', methods=['POST'])
def add_friend():
    current_user_id = session.get("user_id")
    if not current_user_id:
        return jsonify({"error": "Unauthorized"}), 401
    
    data = request.get_json()
    friend_username = data.get('username')
    
    if not friend_username:
        return jsonify({"error": "Username is required"}), 400
        
    # Вызываем сервис, который мы написали ранее
    success = FriendService.send_friend_request(current_user_id, friend_username)
    
    if success:
        return jsonify({"message": "Заявка отправлена!"}), 200
    else:
        return jsonify({"error": "Пользователь не найден или уже в друзьях"}), 400

# 2. Принятие приглашения по ссылке
@friends_bp.route('/invite/<token>')
def accept_invite(token):
    current_user_id = session.get("user_id")
    
    # Если юзер не залогинен, запоминаем куда он хотел попасть и шлем на логин
    if not current_user_id:
        return redirect(url_for('authorization', next=request.path))

    # Находим того, кто владеет этим токеном
    inviter = UserService.get_user_by_invite_token(token)
    
    if not inviter:
        flash("Невалидная ссылка приглашения")
        return redirect(url_for('index'))

    if inviter.id == current_user_id:
        flash("Нельзя добавить самого себя")
        return redirect(url_for('index'))

    # Создаем прямую дружбу (accepted)
    success = FriendService.create_direct_friendship(inviter.id, current_user_id)
    
    if success:
        flash(f"Вы теперь друзья с {inviter.username}!")
    else:
        flash("Вы уже друзья")
        
    return redirect(url_for('index')) # Или на страницу профиля


@friends_bp.route('/friends/requests', methods=['GET'])
def list_requests():
    uid = session.get("user_id")
    if not uid: return jsonify([]), 401
    
    senders = FriendService.get_pending_requests(uid)
    # Формируем простой список имен и ID
    return jsonify([{"id": s.id, "username": s.username} for s in senders])

@friends_bp.route('/friends/respond', methods=['POST'])
def respond_request():
    uid = session.get("user_id")
    data = request.get_json()
    
    sender_id = data.get('sender_id')
    action = data.get('action') # 'accepted' или 'declined'
    
    if FriendService.update_request_status(uid, sender_id, action):
        return jsonify({"message": "Успешно"}), 200
    return jsonify({"error": "Запрос не найден"}), 404


@friends_bp.route('/friends')
def friends_page():
    uid = session.get("user_id")
    if not uid:
        return redirect(url_for('authorization'))
    
    current_user = UserService.get_user_by_id(uid)
    friends = FriendService.get_all_friends(uid)
    
    # Получаем входящие и исходящие заявки сразу
    incoming_requests = FriendService.get_pending_requests(uid)
    sent_requests = FriendService.get_sent_requests(uid)
    
    return render_template("friends.html", 
                           friends=friends, 
                           current_user=current_user,
                           incoming_requests=incoming_requests,
                           sent_requests=sent_requests)

@friends_bp.route('/friends/remove', methods=['POST'])
def remove_friend():
    uid = session.get("user_id")
    data = request.get_json()
    friend_id = data.get('friend_id')
    
    if FriendService.remove_friendship(uid, friend_id):
        return jsonify({"success": True}), 200
    return jsonify({"error": "Связь не найдена"}), 404


@friends_bp.route('/api/books/<int:book_id>/social-activity')
def get_book_social_activity(book_id):
    my_id = session.get("user_id")
    if not my_id:
        return jsonify([]), 401

    # 1. Получаем список ID всех друзей
    friends = FriendService.get_all_friends(my_id)
    friend_ids = [f.id for f in friends]

    if not friend_ids:
        return jsonify([])

    with get_connection() as session_db:
        # 2. Собираем закладки друзей для этой книги
        bookmarks = session_db.query(Bookmark, User.username).join(
        User, Bookmark.user_id == User.id
        ).filter(
            Bookmark.book_id == book_id,
            Bookmark.user_id.in_(friend_ids)
        ).all()

        # 3. Собираем заметки друзей для этой книги
        notes = session_db.query(Note, User.username).join(
        User, Note.user_id == User.id
        ).filter(
            Note.book_id == book_id,
            Note.user_id.in_(friend_ids)
        ).all()

        # Формируем единый список активностей
        activity = []
        for b, uname in bookmarks:
            activity.append({
                "type": "bookmark",
                "username": uname,
                "title": b.title,
                "position": b.position, # Относительная позиция 0-1
                "cfi": b.cfi
            })
        
        for n, uname in notes:
            activity.append({
                "type": "note",
                "username": uname,
                "text": n.selected_text,
                "comment": n.comment,
                "position": n.position,
                "cfi": n.cfi
            })

        return jsonify(activity)


@friends_bp.route('/api/users/search')
def search_users_api():
    uid = session.get("user_id")
    query = request.args.get('q', '').strip()
    page = int(request.args.get('page', 0))
    limit = 5

    if not uid or len(query) < 1:
        return jsonify([])

    related_ids = UserService.get_related_user_ids(uid)

    offset = page * limit
    users = UserService.search_users(query, uid, offset=offset, limit=limit)

    return jsonify([{
        "id": u.id,
        "username": u.username,
        "already_linked": u.id in related_ids
    } for u in users])

@friends_bp.route('/friends/add_by_id', methods=['POST'])
def add_friend_by_id():
    current_user_id = session.get("user_id")
    if not current_user_id:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json()
    friend_id = data.get('friend_id')

    if FriendService.send_friend_request_by_id(current_user_id, friend_id):
        return jsonify({"message": "Заявка отправлена!"}), 200
    return jsonify({"error": "Не удалось отправить заявку"}), 400