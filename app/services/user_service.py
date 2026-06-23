import hashlib
import sys
import psycopg2.extras
from db import get_connection
from models.models import User, Friendship, ReadingProgress, Book, Group, GroupMember

class UserService:
    @staticmethod
    def find_by_email(email, password):
        with get_connection() as session:
            users = session.query(User).filter(User.email == email, User.password_hash == password).all()
            if (len(users) > 0):
                return users
            return None
    @staticmethod
    def find_password_by_email(email):
        with get_connection() as session:
            user = session.query(User).filter(User.email == email).first()
            if user:
                return user.password_hash
            return None
            

    @staticmethod
    def username_available(username):
        with get_connection() as session:
            users = session.query(User).filter(User.username == username).all()
            if users:
                return False
            return True

    @staticmethod
    def email_available(email):
        with get_connection() as session:
            users = session.query(User).filter(User.email == email).all()
            if users:
                return False
            return True

    @staticmethod
    def insert_user(username, email, password):
        with get_connection() as session:
            newUser = User(username, email, password)
            session.add(newUser)
            session.commit()

    @staticmethod
    def ensure_admin_account(username, email, password_plain):
        """Гарантирует наличие администратора с указанным email.

        Идемпотентно: если пользователь с таким email уже есть — повышает его
        до роли admin; иначе создаёт нового админа. Пароль хэшируется так же,
        как при обычной регистрации (sha256). Возвращает id админа или None.
        """
        if not email or not password_plain:
            return None

        password_hash = hashlib.sha256(password_plain.encode()).hexdigest()

        with get_connection() as session:
            user = session.query(User).filter(User.email == email).first()
            if user:
                if user.role != "admin":
                    user.role = "admin"
                    session.commit()
                    print(f"[admin] Пользователь {email} повышен до admin", file=sys.stderr)
                return user.id

            # username должен быть уникальным — если занят, добавляем суффикс по id позже
            if session.query(User).filter(User.username == username).first():
                username = f"{username}_admin"

            admin = User(username, email, password_hash)
            admin.role = "admin"
            session.add(admin)
            session.commit()
            print(f"[admin] Создан администратор {email}", file=sys.stderr)
            return admin.id
                
    @staticmethod
    def has_read_book_achievement(user_id):
        with get_connection() as session:
            user = session.query(User).get(user_id)
            return user.has_read_book_achievement if user else False
        
    @staticmethod
    def get_user_by_id(user_id):
        with get_connection() as session:
            user = session.query(User).get(user_id)
            return user
        
    @staticmethod
    def get_user_by_invite_token(token):
        with get_connection() as session:
            return session.query(User).filter(User.invite_token == token).first()

    @staticmethod
    def search_users(query, current_user_id, offset=0, limit=5):
        with get_connection() as session:
            return session.query(User).filter(
                User.username.ilike(f"%{query}%"),
                User.id != current_user_id
            ).order_by(User.username).offset(offset).limit(limit).all()

    @staticmethod
    def get_related_user_ids(user_id):
        with get_connection() as session:
            related = session.query(Friendship).filter(
                (Friendship.user_id == user_id) | (Friendship.friend_id == user_id)
            ).all()

            ids = set()
            for f in related:
                ids.add(f.user_id)
                ids.add(f.friend_id)

            if user_id in ids:
                ids.remove(user_id)

            return ids

    @staticmethod
    def get_user_permissions(user_id):
        with get_connection() as session:
            user = session.query(User).get(user_id)
            if not user:
                return {
                    "can_download_data": False, "can_import_data": False, "can_friends": False,
                    "can_upload_files": False, "can_manage_groups": False, "can_manage_books_access": False
                }

            if user.role == "admin":
                return {
                    "can_download_data": True, "can_import_data": True, "can_friends": True,
                    "can_upload_files": True, "can_manage_groups": True, "can_manage_books_access": True
                }

            groups = session.query(Group).join(GroupMember, GroupMember.group_id == Group.id).filter(
                GroupMember.user_id == user_id).all()

            deny_download = any(g.deny_download_data for g in groups)
            deny_import = any(g.deny_import_data for g in groups)
            deny_friend = any(g.deny_friends for g in groups)

            allow_upload = any(g.allow_upload_files for g in groups)
            allow_manage = any(g.allow_manage_groups for g in groups)
            allow_manage_books_access = any(g.allow_manage_books_access for g in groups)

            return {
                "can_download_data": not deny_download,
                "can_import_data": not deny_import,
                "can_friends": not deny_friend,
                "can_upload_files": allow_upload,
                "can_manage_groups": allow_manage,
                "can_manage_books_access": allow_manage_books_access
            }

class FriendService:
    @staticmethod
    def send_friend_request_by_id(user_id, friend_id):
        with get_connection() as session:
            if user_id == friend_id:
                return False

            exists = session.query(Friendship).filter(
                ((Friendship.user_id == user_id) & (Friendship.friend_id == friend_id)) |
                ((Friendship.user_id == friend_id) & (Friendship.friend_id == user_id))
            ).first()

            if not exists:
                new_request = Friendship(user_id=user_id, friend_id=friend_id, status="pending")
                session.add(new_request)
                session.commit()
                return True
            return False

    @staticmethod
    def get_friends_ids(user_id):
        with get_connection() as session:
            # Получаем ID всех, кто в статусе 'accepted'
            friends = session.query(Friendship).filter(
                ((Friendship.user_id == user_id) | (Friendship.friend_id == user_id)),
                Friendship.status == "accepted"
            ).all()
            
            ids = []
            for f in friends:
                ids.append(f.friend_id if f.user_id == user_id else f.user_id)
            return ids
        
    @staticmethod
    def create_direct_friendship(user_id_1, user_id_2):
        with get_connection() as session:
            # Проверяем наличие связи
            exists = session.query(Friendship).filter(
                ((Friendship.user_id == user_id_1) & (Friendship.friend_id == user_id_2)) |
                ((Friendship.user_id == user_id_2) & (Friendship.friend_id == user_id_1))
            ).first()
            
            if not exists:
                # Сразу создаем подтвержденную дружбу
                new_friendship = Friendship(
                    user_id=user_id_1, 
                    friend_id=user_id_2, 
                    status="accepted"
                )
                session.add(new_friendship)
                session.commit()
                return True
            return False
    
    @staticmethod
    def get_pending_requests(user_id):
        with get_connection() as session:
            # Ищем заявки, где наш юзер — получатель (friend_id)
            requests = session.query(Friendship).filter(
                Friendship.friend_id == user_id,
                Friendship.status == 'pending'
            ).all()
            # Возвращаем список отправителей (объекты User)
            return [r.user for r in requests]
        
        
    @staticmethod
    def get_sent_requests(user_id):
        with get_connection() as session:
            requests = session.query(Friendship).filter(
                Friendship.user_id == user_id,
                Friendship.status == 'pending'
            ).all()
            # Возвращаем список тех, кому мы отправили запрос
            return [r.friend for r in requests]

    @staticmethod
    def update_request_status(user_id, sender_id, new_status):
        with get_connection() as session:
            request = session.query(Friendship).filter(
                Friendship.user_id == sender_id,
                Friendship.friend_id == user_id,
                Friendship.status == 'pending'
            ).first()
            
            if request:
                if new_status == 'accepted':
                    request.status = 'accepted'
                else:
                    session.delete(request) # Если отклонил — просто удаляем запись
                session.commit()
                return True
            return False
    
        
    @staticmethod
    def remove_friendship(user_id, friend_id):
        with get_connection() as session:
            # Ищем связь в обе стороны
            friendship = session.query(Friendship).filter(
                ((Friendship.user_id == user_id) & (Friendship.friend_id == friend_id)) |
                ((Friendship.user_id == friend_id) & (Friendship.friend_id == user_id))
            ).first()
            
            if friendship:
                session.delete(friendship)
                session.commit()
                return True
            return False

    @staticmethod
    def get_all_friends(user_id):
        with get_connection() as session:
            # Получаем подтвержденных друзей
            friendships = session.query(Friendship).filter(
                ((Friendship.user_id == user_id) | (Friendship.friend_id == user_id)),
                Friendship.status == 'accepted'
            ).all()
            
            friends = []
            for f in friendships:
                target_id = f.friend_id if f.user_id == user_id else f.user_id
                user = session.query(User).get(target_id)
                if user:
                    friends.append(user)
            return friends
        
    @staticmethod
    def get_reading_progress(user_id):
        with get_connection() as session:
            results = session.query(ReadingProgress, Book)\
            .join(Book, ReadingProgress.book_id == Book.id)\
            .filter(ReadingProgress.user_id == user_id)\
            .all()
        
        progress_list = []
        for progress, book in results:
            progress_list.append({
                "book_id": book.id,
                "book_title": book.title,
                "book_author": book.author,
                "cfi": progress.cfi,
                "last_position": progress.last_position # Ожидаем float от 0.0 до 1.0
            })
        return progress_list