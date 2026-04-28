from flask import Blueprint, request, session, jsonify, redirect, url_for, flash, render_template
from services.user_service import UserService, FriendService

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