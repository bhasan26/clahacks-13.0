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
    from datetime import timedelta
    from app.db.store import store
    from app.domain.models import utc_now
    from app.connectors.registry import ensure_sources
    from app.connectors.sync_engine import sync_policies
    while not _stop_event.is_set():
        ensure_sources(store)
        configured={x.strip() for x in os.environ.get('COVERAGEGUARD_SCHEDULER_SOURCES','').split(',') if x.strip()}
        for source in list(store.sync_sources.values()):
            if configured and source.source_id not in configured:continue
            if _stop_event.is_set(): break
            due=source.next_sync_at or (source.last_attempt_at+timedelta(seconds=interval_seconds) if source.last_attempt_at else utc_now())
            source.next_sync_at=due
            if due<=utc_now():
                try:sync_policies(source.source_id)
                except Exception:
                    import logging
                    logging.getLogger(__name__).warning("Policy sync failed; retry scheduled without provider details.")
        _stop_event.wait(min(interval_seconds,60))


def start_source_scheduler(interval_seconds: int = 86400):
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
