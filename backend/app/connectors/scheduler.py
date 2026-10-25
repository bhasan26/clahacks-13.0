"""
Lightweight Background Scheduler for Official Policy Source Monitoring.
Guards against duplicate threads during FastAPI dev reload or multi-worker execution.
"""

import threading
import time
from typing import Optional

_scheduler_thread: Optional[threading.Thread] = None
_stop_event = threading.Event()
_scheduler_lock = threading.Lock()


def _run_scheduler_loop(interval_seconds: int = 3600):
    from app.db.store import store
    from app.connectors.change_detector import check_source_for_changes

    while not _stop_event.is_set():
        try:
            sources = store.get_sources()
            for s in sources:
                if s.status != "disabled":
                    check_source_for_changes(s)
        except Exception as e:
            print(f"Policy source scheduler notice: {e}")

        # Sleep in small slices to respond promptly to stop_event
        for _ in range(int(interval_seconds)):
            if _stop_event.is_set():
                break
            time.sleep(1.0)


def start_source_scheduler(interval_seconds: int = 3600):
    """Starts background monitor thread safely without duplicates."""
    global _scheduler_thread
    with _scheduler_lock:
        if _scheduler_thread is not None and _scheduler_thread.is_alive():
            return  # Already running

        _stop_event.clear()
        _scheduler_thread = threading.Thread(
            target=_run_scheduler_loop,
            args=(interval_seconds,),
            daemon=True,
            name="CoverageGuardPolicyScheduler",
        )
        _scheduler_thread.start()


def stop_source_scheduler():
    """Stops the background monitor thread."""
    global _scheduler_thread
    with _scheduler_lock:
        _stop_event.set()
        if _scheduler_thread and _scheduler_thread.is_alive():
            _scheduler_thread.join(timeout=2.0)
        _scheduler_thread = None
