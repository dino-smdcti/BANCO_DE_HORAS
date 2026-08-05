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
                _clear_notifications(uow, user_id)


def _clear_notifications(uow, user_id):
        """Delete the notifications once the user has visited their dashboard."""
        user = uow.users.get_user_by_id(user_id)
        if not user:
                return
        for notification in user.notifications:
                uow.session.delete(notification)
        uow.commit()
