from flask_socketio import SocketIO

# Создаем объект, но не инициализируем его приложением (app) пока что
socketio = SocketIO(cors_allowed_origins="http://127.0.0.1:3000", manage_session=True)