"""DB-backed rate limiting for authentication endpoints.

Each attempt is recorded as a row in ``rate_limit_entries`` keyed by a bucket
(e.g. ``"login:<ip>"``). The limiter counts entries in the bucket within a
sliding window and reports whether the attempt should be allowed. Because the
counting is done against the database, the limit:
- persists across serverless cold starts (Vercel),
- is shared across instances (no per-process memory),
- and can be tuned via config constants.
"""
from datetime import datetime, timedelta

from src.domain.model import RateLimitEntry
from src.service_layer.unit_of_work import AbstractUnitOfWork
from src.config import (
        RATE_LIMIT_MAX_ATTEMPTS,
        RATE_LIMIT_PRUNE_BATCH,
        RATE_LIMIT_WINDOW_SECONDS,
)

_BUCKET_SEPARATOR = "|"


def _bucket(kind: str, scope: str = "") -> str:
        """Build a stable bucket key, e.g. ``login|192.168.0.1``."""
        if scope:
                return f"{kind}{_BUCKET_SEPARATOR}{scope}"
        return kind


def _window_start(now: datetime) -> datetime:
        return now - timedelta(seconds=RATE_LIMIT_WINDOW_SECONDS)


def is_allowed(uow: AbstractUnitOfWork, kind: str, scope: str = "", now: datetime = None) -> bool:
        """Record one attempt and report whether it is within the limit.

        Counting is done *after* inserting so that a burst of requests is
        accounted for immediately. A transient DB failure must never lock a
        legitimate user out, so it degrades to allowing the attempt.
        """
        now = now or datetime.now()
        bucket = _bucket(kind, scope)
        window_start = _window_start(now)
        try:
                with uow:
                        uow.rate_limit.add_rate_limit_entry(RateLimitEntry(bucket=bucket, created_at=now))
                        uow.rate_limit.prune_rate_limit_entries(window_start, RATE_LIMIT_PRUNE_BATCH)
                        count = uow.rate_limit.count_rate_limit_entries(bucket, window_start)
        except Exception:
                return True
        return count <= RATE_LIMIT_MAX_ATTEMPTS
