from datetime import datetime
from src.domain.model import Notification
from src.service_layer.unit_of_work import AbstractUnitOfWork


def add_notification(uow: AbstractUnitOfWork, user_id: int, message: str, email_sender=None):
        """Queue a notification and optionally email it when the user opted in."""
        uow.session.add(Notification(user_id=user_id, message=message, created_at=datetime.now()))
        user = uow.users.get_user_by_id(user_id)
        if user and user.email_notifications_enabled and email_sender:
                email_sender(user.email, "Nova Notificação - Banco de Horas", f"<p>{message}</p>")


def mark_notifications_as_read(uow: AbstractUnitOfWork, user_id: int):
        with uow:
                _mark_read(uow, user_id)


def _mark_read(uow, user_id):
        """Mark all of a user's notifications as read when they visit their dashboard.

        Notifications are preserved (not deleted) and only flagged as read, so the
        user's unread count reflects genuinely unvisited entries.
        """
        user = uow.users.get_user_by_id(user_id)
        if not user:
                return
        for notification in user.notifications:
                notification.is_read = True
