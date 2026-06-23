# services/group_service.py
from db import get_connection
from models.models import Group, GroupMember, GroupBookAccess, User, Book


class GroupService:
    """Управление группами пользователей и их доступом к книгам (для админов)."""

    @staticmethod
    def list_groups():
        with get_connection() as session:
            groups = session.query(Group).order_by(Group.name).all()
            result = []
            for g in groups:
                result.append({
                    "id": g.id,
                    "name": g.name,
                    "member_count": len(g.members),
                    "book_count": len(g.book_access),
                    "deny_download_data": getattr(g, "deny_download_data", False),
                    "deny_import_data": getattr(g, "deny_import_data", False),
                    "deny_friends": getattr(g, "deny_friends", False),
                    "allow_upload_files": getattr(g, "allow_upload_files", False),
                    "allow_manage_groups": getattr(g, "allow_manage_groups", False),
                })
            return result

    @staticmethod
    def create_group(name):
        name = (name or "").strip()
        if not name:
            return None, "Название группы не может быть пустым"
        with get_connection() as session:
            existing = session.query(Group).filter(Group.name == name).first()
            if existing:
                return None, "Группа с таким названием уже существует"
            group = Group(name=name)
            session.add(group)
            session.commit()
            return group.id, None

    @staticmethod
    def delete_group(group_id):
        with get_connection() as session:
            group = session.query(Group).get(group_id)
            if not group:
                return False
            session.delete(group)
            session.commit()
            return True

    @staticmethod
    def get_group_detail(group_id):
        """Полная карточка группы: участники, книги и списки для выбора."""
        with get_connection() as session:
            group = session.query(Group).get(group_id)
            if not group:
                return None

            member_ids = {m.user_id for m in group.members}
            book_ids = {ba.book_id for ba in group.book_access}

            all_users = session.query(User).order_by(User.username).all()
            all_books = session.query(Book).order_by(Book.title).all()

            return {
                "id": group.id,
                "name": group.name,
                "deny_download_data": getattr(group, "deny_download_data", False),
                "deny_import_data": getattr(group, "deny_import_data", False),
                "deny_friends": getattr(group, "deny_friends", False),
                "allow_upload_files": getattr(group, "allow_upload_files", False),
                "allow_manage_groups": getattr(group, "allow_manage_groups", False),
                "member_ids": list(member_ids),
                "book_ids": list(book_ids),
                "all_users": [
                    {"id": u.id, "username": u.username, "is_member": u.id in member_ids}
                    for u in all_users
                ],
                "all_books": [
                    {"id": b.id, "title": b.title, "has_access": b.id in book_ids}
                    for b in all_books
                ],
            }

    @staticmethod
    def set_members(group_id, user_ids):
        """Полностью заменить состав участников группы."""
        with get_connection() as session:
            group = session.query(Group).get(group_id)
            if not group:
                return False
            session.query(GroupMember).filter_by(group_id=group_id).delete()
            for uid in set(user_ids or []):
                if session.query(User).get(uid):
                    session.add(GroupMember(group_id=group_id, user_id=uid))
            session.commit()
            return True

    @staticmethod
    def set_books(group_id, book_ids):
        """Полностью заменить набор книг, доступных группе."""
        with get_connection() as session:
            group = session.query(Group).get(group_id)
            if not group:
                return False
            session.query(GroupBookAccess).filter_by(group_id=group_id).delete()
            for bid in set(book_ids or []):
                if session.query(Book).get(bid):
                    session.add(GroupBookAccess(group_id=group_id, book_id=bid))
            session.commit()
            return True
