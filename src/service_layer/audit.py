from src.service_layer.unit_of_work import AbstractUnitOfWork


def log_action(uow: AbstractUnitOfWork, user_id: int, action: str, target_id=None, details=None):
        """Record an audit action without committing.

        Persistence (of both the operation and this audit row) happens in a single
        transaction at the caller's `with uow:` exit, so the audit entry is atomic
        with the change it describes.
        """
        uow.record_action(user_id, action, target_id=target_id, details=details)
