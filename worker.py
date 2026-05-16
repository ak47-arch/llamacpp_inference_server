"""Background worker loop for async parse jobs."""

import threading
import time
from typing import Optional

from .job_queue import dequeue_next, process_job, retry_failed_jobs, startup_recovery


_worker_thread: Optional[threading.Thread] = None
_worker_stop_event: Optional[threading.Event] = None


def run_worker_cycle(data_dir: str = None) -> bool:
    """Process due retries and handle one queued job."""
    retry_failed_jobs(data_dir=data_dir, respect_schedule=True)
    job = dequeue_next(data_dir=data_dir)
    if job is None:
        return False
    return process_job(job, data_dir=data_dir)


def worker_loop(poll_interval_seconds: float = 0.1, data_dir: str = None, stop_event: threading.Event = None):
    """Continuously process queued jobs until stopped."""
    startup_recovery(data_dir=data_dir)
    _cycle = 0
    while stop_event is None or not stop_event.is_set():
        _cycle += 1
        # Periodically reclaim any jobs stuck in PROCESSING (e.g. after a silent exception
        # killed a previous cycle before mark_success/mark_failed could be called).
        if _cycle % 300 == 0:
            startup_recovery(data_dir=data_dir)
        try:
            processed = run_worker_cycle(data_dir=data_dir)
        except Exception:
            # Prevent an unexpected error in dequeue/retry logic from killing the thread.
            processed = False
        if processed:
            continue
        if stop_event is None:
            time.sleep(poll_interval_seconds)
        else:
            stop_event.wait(poll_interval_seconds)


def start_background_worker(data_dir: str = None, poll_interval_seconds: float = 0.1):
    """Start a single daemon worker thread if one is not already running."""
    global _worker_thread, _worker_stop_event
    if _worker_thread is not None and _worker_thread.is_alive():
        return _worker_thread

    _worker_stop_event = threading.Event()
    _worker_thread = threading.Thread(
        target=worker_loop,
        kwargs={
            "poll_interval_seconds": poll_interval_seconds,
            "data_dir": data_dir,
            "stop_event": _worker_stop_event,
        },
        daemon=True,
        name="parse-job-worker",
    )
    _worker_thread.start()
    return _worker_thread


def stop_background_worker(timeout_seconds: float = 2.0):
    """Signal the daemon worker to stop."""
    global _worker_thread, _worker_stop_event
    if _worker_stop_event is None:
        return
    _worker_stop_event.set()
    if _worker_thread is not None:
        _worker_thread.join(timeout_seconds)
    _worker_thread = None
    _worker_stop_event = None