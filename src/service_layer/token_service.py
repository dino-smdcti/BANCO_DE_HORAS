"""Server-side, single-use, revocable auth tokens.

The raw token value is only ever shown once inside the emailed link. Only its
SHA-256 hash is persisted, so a database leak does not expose usable tokens.
Issuing stores a row; peeking validates without side effects; consuming marks
the token used atomically with the operation it authorises, so a link cannot
be replayed.
"""
import hashlib
import secrets
from datetime import datetime, timedelta

from src.domain.model import AuthToken


def _hash(raw_token: str) -> str:
        return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def issue_token(uow, user_id: int, kind: str, ttl_seconds: int) -> str:
        """Persist a new single-use token and return the raw value for the email link."""
        raw = secrets.token_urlsafe(32)
        uow.tokens.add_token(AuthToken(
                user_id=user_id,
                token_hash=_hash(raw),
                kind=kind,
                expires_at=datetime.now() + timedelta(seconds=ttl_seconds),
        ))
        uow.commit()
        return raw


def peek_token(uow, raw_token: str, kind: str):
        """Validate a token without consuming it. Returns the owning user_id or None."""
        token = uow.tokens.get_token_by_hash(_hash(raw_token), kind)
        if token is None or token.used or datetime.now() > token.expires_at:
                return None
        return token.user_id


def consume_token(uow, raw_token: str, kind: str):
        """Mark a valid token as used and return the owning user_id, or None.

        Does not commit; the caller commits together with the effect the token
        authorises so the burn and the operation are atomic.
        """
        token = uow.tokens.get_token_by_hash(_hash(raw_token), kind)
        if token is None or token.used or datetime.now() > token.expires_at:
                return None
        token.used = True
        return token.user_id


def revoke_user_tokens(uow, user_id: int, kind: str):
        """Mark every outstanding (unused) token of a kind used, e.g. on password change."""
        uow.tokens.revoke_user_tokens(user_id, kind)
        uow.commit()
