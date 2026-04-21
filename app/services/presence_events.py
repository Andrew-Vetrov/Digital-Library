from flask import session, request
from flask_socketio import emit, join_room, leave_room
from services.user_service import UserService
from sys import stderr
from extensions import socketio


rooms_state = {}

def init_presence_events(socketio):
    @socketio.on('join_book')
    def handle_join(data):
        book_id = str(data.get('book_id'))
        username = session.get("authorized")
        user_id = session.get("user_id")

        print("session = ", session, file=stderr)
        if not username and user_id:
            user = UserService.get_user_by_id(user_id) # Убедись, что такой метод есть в UserService
            if user:
                username = user.username
        
        if not username:
            username = "Anon"

        if not book_id:
            return

        print(username, file=stderr)
        join_room(book_id)
        
        if book_id not in rooms_state:
            rooms_state[book_id] = {}
        
        rooms_state[book_id][request.sid] = {
            'username': username,
            'user_id': user_id,
            'cfi': data.get('cfi'),
            'fraction': data.get('fraction', 0)
        }
        
        emit('presence_update', rooms_state[book_id], to=book_id)

    @socketio.on('update_position')
    def handle_update(data):
        book_id = str(data.get('book_id'))
        if book_id in rooms_state and request.sid in rooms_state[book_id]:
            rooms_state[book_id][request.sid].update({
                'cfi': data.get('cfi'),
                'fraction': data.get('fraction', 0)
            })
            # Рассылаем только изменения позиций
            emit('presence_update', rooms_state[book_id], to=book_id)

    @socketio.on('disconnect')
    def handle_disconnect():
        for book_id, users in rooms_state.items():
            if request.sid in users:
                del users[request.sid]
                emit('presence_update', users, to=book_id)
                break