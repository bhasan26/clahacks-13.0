"""Opt-in monitoring in one application worker, with a process lock for reloads."""
import fcntl
import os
import threading
from pathlib import Path
from typing import Optional

_scheduler_thread: Optional[threading.Thread] = None
_stop_event = threading.Event()
_scheduler_lock = threading.Lock()
_process_lock = None
_scheduler_owns_lock = False


def acquire_worker_lock():
    global _process_lock
    if _process_lock is not None:
        return
    path = Path(os.environ.get("COVERAGEGUARD_WORKER_LOCK", str(Path(__file__).resolve().parents[2] / "data" / "worker.lock")))
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a")
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        handle.close()
        raise RuntimeError("CoverageGuard requires one API worker. Another worker owns the local state and monitoring lock.") from None
    _process_lock = handle


def release_worker_lock():
    global _process_lock
    if _process_lock is not None:
        fcntl.flock(_process_lock, fcntl.LOCK_UN)
        _process_lock.close()
        _process_lock = None


def _run_scheduler_loop(interval_seconds):
    from app.db.store import store
    from app.connectors.change_detector import check_source_for_changes
    while not _stop_event.is_set():
        for source in store.get_sources():
            if _stop_event.is_set():
                break
            if source.status != "disabled":
                try:
                    check_source_for_changes(source)
                except Exception:
                    # Details and provider content must not leak to logs.
                    import logging
                    logging.getLogger(__name__).warning("Policy check failed; retry scheduled.")
        _stop_event.wait(interval_seconds)


def start_source_scheduler(interval_seconds: int = 3600):
    global _scheduler_thread, _scheduler_owns_lock
    with _scheduler_lock:
        if _scheduler_thread is not None and _scheduler_thread.is_alive():
            return
        if interval_seconds < 1:
            raise ValueError("Scheduler interval must be positive.")
        _scheduler_owns_lock = _process_lock is None
        acquire_worker_lock()
        _stop_event.clear()
        _scheduler_thread = threading.Thread(target=_run_scheduler_loop, args=(interval_seconds,), daemon=True,
                                             name="CoverageGuardPolicyScheduler")
        _scheduler_thread.start()


def stop_source_scheduler():
    global _scheduler_thread, _scheduler_owns_lock
    with _scheduler_lock:
        _stop_event.set()
        if _scheduler_thread and _scheduler_thread.is_alive():
            _scheduler_thread.join(timeout=60.0)
            if _scheduler_thread.is_alive():
                raise RuntimeError("Source check is still stopping; worker lock remains held.")
        _scheduler_thread = None
        if _scheduler_owns_lock:
            release_worker_lock()
            _scheduler_owns_lock = False
