from flask import session, request
from flask_socketio import emit, join_room, leave_room
from services.user_service import UserService, FriendService
from sys import stderr
from extensions import socketio


rooms_state = {}

def emit_filtered_presence(socketio, book_id):
    """Рассылает каждому в комнате только ЕГО друзей"""
    if book_id not in rooms_state:
        return

    # Перебираем всех, кто сейчас в этой комнате
    for recipient_sid, recipient_info in rooms_state[book_id].items():
        recipient_uid = recipient_info.get('user_id')
        
        # Получаем список ID друзей для этого конкретного получателя
        friend_ids = FriendService.get_friends_ids(recipient_uid)
        
        # Формируем список тех, кого этот получатель имеет право видеть
        # (Друзья + он сам)
        filtered_data = {
            sid: data for sid, data in rooms_state[book_id].items()
            if data.get('user_id') in friend_ids or sid == recipient_sid
        }
        
        # Отправляем персонально на SID получателя
        socketio.emit('presence_update', filtered_data, to=recipient_sid)


def init_presence_events(socketio):
    @socketio.on('join_book')
    def handle_join(data):
        book_id = str(data.get('book_id'))
        username = session.get("authorized")
        user_id = session.get("user_id")

        if not username and user_id:
            user = UserService.get_user_by_id(user_id)
            if user: username = user.username
        
        username = username or "Anon"
        if not book_id: return

        join_room(book_id)
        
        if book_id not in rooms_state:
            rooms_state[book_id] = {}
        
        rooms_state[book_id][request.sid] = {
            'username': username,
            'user_id': user_id, # Обязательно храним ID для фильтрации
            'cfi': data.get('cfi'),
            'fraction': data.get('fraction', 0)
        }
        
        # Вместо общего emit вызываем фильтрованную рассылку
        emit_filtered_presence(socketio, book_id)

    @socketio.on('update_position')
    def handle_update(data):
        book_id = str(data.get('book_id'))
        if book_id in rooms_state and request.sid in rooms_state[book_id]:
            rooms_state[book_id][request.sid].update({
                'cfi': data.get('cfi'),
                'fraction': data.get('fraction', 0)
            })
            # Опять фильтруем и рассылаем
            emit_filtered_presence(socketio, book_id)

    @socketio.on('disconnect')
    def handle_disconnect():
        for book_id, users in rooms_state.items():
            if request.sid in users:
                del users[request.sid]
                emit_filtered_presence(socketio, book_id)
                break