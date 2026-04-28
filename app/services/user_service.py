import psycopg2.extras
from db import get_connection
from models.models import User, Friendship

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



class FriendService:
    @staticmethod
    def send_friend_request(user_id, friend_username):
        with get_connection() as session:
            friend = session.query(User).filter(User.username == friend_username).first()
            if not friend or friend.id == user_id:
                return False
            
            # Проверяем, нет ли уже такой связи
            exists = session.query(Friendship).filter(
                ((Friendship.user_id == user_id) & (Friendship.friend_id == friend.id)) |
                ((Friendship.user_id == friend.id) & (Friendship.friend_id == user_id))
            ).first()
            
            if not exists:
                new_request = Friendship(user_id=user_id, friend_id=friend.id, status="pending")
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