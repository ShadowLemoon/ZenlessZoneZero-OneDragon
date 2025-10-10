from __future__ import annotations

from concurrent.futures import Future
from contextlib import contextmanager
from typing import Protocol

from one_dragon.utils.log_utils import log


def handle_future_result(future: Future):
    try:
        future.result()
    except Exception:
        log.error('异步执行失败', exc_info=True)


class _LockProtocol(Protocol):
    def acquire(self, blocking: bool = True) -> bool: ...

    def release(self) -> None: ...


@contextmanager
def try_acquire(lock: _LockProtocol, blocking: bool = True):
    """Context manager that attempts to acquire *lock* and releases on exit.

    :param lock: A threading lock-like object providing ``acquire`` and ``release``.
    :param blocking: Whether to block while acquiring the lock.
    :returns: ``True`` when the lock was acquired, otherwise ``False``.
    """

    acquired = lock.acquire(blocking=blocking)
    try:
        yield acquired
    finally:
        if acquired:
            lock.release()
