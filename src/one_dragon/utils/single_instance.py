from __future__ import annotations

import contextlib
import msvcrt
import os
from pathlib import Path
from typing import IO

from one_dragon.utils import os_utils


class SingleInstanceError(RuntimeError):
    """Raised when another process already holds the single-instance lock."""


class SingleInstanceLock:
    """基于文件锁的单实例控制，仅支持 Windows。"""

    def __init__(self, lock_name: str, lock_dir: Path | None = None) -> None:
        if lock_dir is None:
            lock_dir = Path(os_utils.get_path_under_work_dir(".runtime", "locks"))
        else:
            lock_dir = Path(lock_dir)
        lock_dir.mkdir(parents=True, exist_ok=True)
        self._lock_path = lock_dir / lock_name
        self._file: IO[str] | None = None

    def acquire(self, blocking: bool = False) -> None:
        """Try to acquire the lock.

        :param blocking: Whether to wait for the lock. Defaults to non-blocking.
        :raises SingleInstanceError: If the lock is already held by another process.
        """
        if self._file is not None:
            return

        self._file = open(self._lock_path, "a+")  # noqa: SIM115 - lock requires persistent handle
        self._prepare_lock_file()

        try:
            self._lock_file(blocking)
        except SingleInstanceError:
            self._release_on_failure()
            raise

    def release(self) -> None:
        """Release the lock if currently held."""
        if self._file is None:
            return

        try:
            self._unlock_file()
        finally:
            try:
                self._file.close()
            finally:
                self._file = None
                with contextlib.suppress(OSError):
                    self._lock_path.unlink()

    def __enter__(self) -> SingleInstanceLock:
        self.acquire()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.release()

    def _prepare_lock_file(self) -> None:
        assert self._file is not None
        self._file.seek(0, os.SEEK_END)
        if self._file.tell() == 0:
            self._file.write("0")
            self._file.flush()
        self._file.seek(0)

    def _lock_file(self, blocking: bool) -> None:
        assert self._file is not None
        fileno = self._file.fileno()

        mode = msvcrt.LK_LOCK if blocking else msvcrt.LK_NBLCK
        try:
            msvcrt.locking(fileno, mode, 1)
        except OSError as exc:  # pragma: no cover - depends on runtime state
            raise SingleInstanceError("lock is already held") from exc

    def _unlock_file(self) -> None:
        assert self._file is not None
        fileno = self._file.fileno()

        with contextlib.suppress(OSError):  # pragma: no cover - depends on runtime state
            msvcrt.locking(fileno, msvcrt.LK_UNLCK, 1)

    def _release_on_failure(self) -> None:
        if self._file is None:
            return
        try:
            self._file.close()
        finally:
            self._file = None
