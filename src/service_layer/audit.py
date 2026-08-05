from src.service_layer.unit_of_work import AbstractUnitOfWork


def log_action(uow: AbstractUnitOfWork, user_id: int, action: str, target_id=None, details=None):
        """Persist pending changes, record an audit action, and commit once."""
        uow.session.flush()
        uow.record_action(user_id, action, target_id=target_id, details=details)
        uow.commit()
