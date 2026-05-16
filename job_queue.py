"""
Spec 007: Async Parse Job Queue and Durable Failure Handling

File-based job persistence with state machine, idempotency, retry logic, and subprocess cleanup.
"""

import json
import os
import time
import uuid
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional, Dict, Any

from parse_service import (
    ParseFailureError,
    ParseModelTimeoutError,
    ParseModelUnavailableError,
    parse_event_payload,
)

from .validator import validate_extraction_output
from .pipeline import judge_extraction
from .router import ProviderRouter

_judge_router = None

def _get_judge_router() -> ProviderRouter:
    """Return a ProviderRouter instance for the extraction_judge role."""
    global _judge_router
    if _judge_router is None:
        base_dir = os.path.dirname(os.path.dirname(__file__))
        config_path = os.path.join(base_dir, "models.yaml")
        _judge_router = ProviderRouter(config_path)
    return _judge_router


# Job state constants
RECEIVED = "RECEIVED"
PERSISTED_RAW = "PERSISTED_RAW"
QUEUED = "QUEUED"
PROCESSING = "PROCESSING"
SUCCESS = "SUCCESS"
FAILED_TIMEOUT = "FAILED_TIMEOUT"
FAILED_UNAVAILABLE = "FAILED_UNAVAILABLE"
FAILED_PARSE = "FAILED_PARSE"
DEAD_LETTER = "DEAD_LETTER"

RETRY_STATES = {FAILED_TIMEOUT, FAILED_UNAVAILABLE, FAILED_PARSE}
TERMINAL_STATES = {SUCCESS, DEAD_LETTER}


def _compute_retry_at(retries: int) -> float:
    initial_delay_ms = 500
    multiplier = 2.0
    max_delay_ms = 30000
    delay_ms = min(initial_delay_ms * (multiplier ** retries), max_delay_ms)
    return time.time() + (delay_ms / 1000.0)


@dataclass
class ParseJob:
    """Immutable job record"""
    job_id: str
    narrative: str
    date: str
    time: str
    status: str
    created_at: float
    updated_at: float = None
    idempotency_key: Optional[str] = None
    retries: int = 0
    max_retries: int = 3
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    next_retry_at: Optional[float] = None
    processing_started_at: Optional[float] = None
    
    def __post_init__(self):
        """Set updated_at to created_at if not provided"""
        if self.updated_at is None:
            self.updated_at = self.created_at


class JobStore:
    """File-based job store with durable persistence"""
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        self.jobs_dir = os.path.join(data_dir, "jobs")
        Path(self.jobs_dir).mkdir(parents=True, exist_ok=True)
        
        # In-memory idempotency cache: idempotency_key -> job_id
        self.idempotency_cache = {}
        self._load_idempotency_cache()
    
    def _load_idempotency_cache(self):
        """Load idempotency cache from all job files on startup"""
        if not os.path.exists(self.jobs_dir):
            return
        
        for filename in os.listdir(self.jobs_dir):
            if filename.endswith(".json"):
                job_file = os.path.join(self.jobs_dir, filename)
                try:
                    with open(job_file) as f:
                        job_data = json.load(f)
                    
                    if job_data.get("idempotency_key"):
                        self.idempotency_cache[job_data["idempotency_key"]] = job_data["job_id"]
                except (json.JSONDecodeError, IOError):
                    pass
    
    def enqueue_parse(
        self,
        narrative: str,
        date: str,
        time_str: str,
        idempotency_key: Optional[str] = None
    ) -> str:
        """
        Create a new parse job or return existing job for same idempotency_key.
        
        Returns: job_id
        """
        # Check idempotency cache first
        if idempotency_key and idempotency_key in self.idempotency_cache:
            existing_job_id = self.idempotency_cache[idempotency_key]
            # Return the cached result if already completed
            existing_job = self.get_job_status(existing_job_id)
            if existing_job is None:
                # Job file was deleted; evict cache and fall through to create new
                del self.idempotency_cache[idempotency_key]
            elif existing_job.status in TERMINAL_STATES:
                return existing_job_id
            elif existing_job.status in RETRY_STATES:
                self.retry_job(existing_job_id)
                return existing_job_id
            else:
                # In-progress job
                return existing_job_id
        
        # Create new job
        job_id = str(uuid.uuid4())
        job = ParseJob(
            job_id=job_id,
            narrative=narrative,
            date=date,
            time=time_str,
            status=QUEUED,
            created_at=time.time(),
            idempotency_key=idempotency_key,
            retries=0,
            max_retries=3
        )
        
        # Persist to disk
        self._save_job(job)
        
        # Update idempotency cache
        if idempotency_key:
            self.idempotency_cache[idempotency_key] = job_id
        
        return job_id
    
    def get_job_status(self, job_id: str) -> Optional[ParseJob]:
        """Retrieve job status from disk"""
        job_file = os.path.join(self.jobs_dir, f"{job_id}.json")
        if not os.path.exists(job_file):
            return None
        
        try:
            with open(job_file) as f:
                job_data = json.load(f)
            return self._dict_to_job(job_data)
        except (json.JSONDecodeError, IOError):
            return None
    
    def dequeue_next(self) -> Optional[ParseJob]:
        """
        Get next QUEUED job that's ready to process.
        Updates job status to PROCESSING and saves to disk.
        """
        for filename in sorted(os.listdir(self.jobs_dir)):
            if not filename.endswith(".json"):
                continue
            
            job_file = os.path.join(self.jobs_dir, filename)
            try:
                with open(job_file) as f:
                    job_data = json.load(f)
                
                job = self._dict_to_job(job_data)
                
                # Find a QUEUED job
                if job.status == QUEUED:
                    # Transition to PROCESSING
                    job.status = PROCESSING
                    job.error = None
                    job.next_retry_at = None
                    job.result = None
                    job.processing_started_at = time.time()
                    self._save_job(job)
                    return job
            except (json.JSONDecodeError, IOError):
                continue
        
        return None
    
    def mark_success(self, job_id: str, result: Dict[str, Any]):
        """Mark job as successfully processed"""
        job = self.get_job_status(job_id)
        if not job:
            return
        
        job.status = SUCCESS
        job.result = result
        self._save_job(job)
    
    def mark_failed(
        self,
        job_id: str,
        error_type: str,
        error_message: str,
        schedule_retry: bool = False,
    ):
        """Mark job as failed with specific error type"""
        job = self.get_job_status(job_id)
        if not job:
            return

        if schedule_retry and job.retries >= job.max_retries:
            job.status = DEAD_LETTER
            job.next_retry_at = None
        else:
            job.status = error_type  # FAILED_TIMEOUT, FAILED_UNAVAILABLE, FAILED_PARSE
            job.next_retry_at = _compute_retry_at(job.retries) if schedule_retry else None
        job.error = error_message
        self._save_job(job)
    
    def retry_job(self, job_id: str):
        """
        Requeue a failed job if retries < max_retries.
        Compute exponential backoff.
        """
        job = self.get_job_status(job_id)
        if not job:
            return
        
        if job.status not in RETRY_STATES:
            return
        
        if job.retries >= job.max_retries:
            # Move to dead letter
            job.status = DEAD_LETTER
        else:
            # Transition back to QUEUED
            job.status = QUEUED
            job.retries += 1
            job.next_retry_at = None
        
        self._save_job(job)
    
    def retry_failed_jobs(self, max_age_seconds: int = 0, respect_schedule: bool = False):
        """
        Scan jobs directory and retry any FAILED_* jobs that are:
        - Older than max_age_seconds (0 = all ages, no age filter)
        - Have next_retry_at <= current time (or unset, or if max_age_seconds is 0)
        """
        current_time = time.time()
        
        for filename in os.listdir(self.jobs_dir):
            if not filename.endswith(".json"):
                continue
            
            job_file = os.path.join(self.jobs_dir, filename)
            try:
                with open(job_file) as f:
                    job_data = json.load(f)
                
                job = self._dict_to_job(job_data)
                
                if job.status not in RETRY_STATES:
                    continue
                
                # Check age constraint
                age = current_time - job.created_at
                if max_age_seconds > 0 and age < max_age_seconds:
                    continue
                
                # Check retry timing (skip if next_retry_at is in future, unless max_age_seconds is 0)
                if respect_schedule and job.next_retry_at and job.next_retry_at > current_time:
                    continue
                
                # Retry this job
                self.retry_job(job.job_id)
            except (json.JSONDecodeError, IOError):
                continue
    
    def startup_recovery(self, stale_threshold_seconds: int = 120):
        """
        On worker startup, find any PROCESSING jobs that are stale.
        Transition them back to QUEUED for reprocessing.
        
        A job is considered stale if it's in PROCESSING state and hasn't been
        updated for longer than stale_threshold_seconds.
        """
        current_time = time.time()
        
        for filename in os.listdir(self.jobs_dir):
            if not filename.endswith(".json"):
                continue
            
            job_file = os.path.join(self.jobs_dir, filename)
            try:
                with open(job_file) as f:
                    job_data = json.load(f)
                
                job = self._dict_to_job(job_data)
                
                if job.status != PROCESSING:
                    continue
                
                # Check if job is stale
                age_seconds = current_time - job.updated_at
                if age_seconds > stale_threshold_seconds:
                    # Recover: transition back to QUEUED
                    job.status = QUEUED
                    job.processing_started_at = None
                    self._save_job(job)
            except (json.JSONDecodeError, IOError):
                continue
    
    def get_dead_letter_jobs(self) -> list:
        """Retrieve all DEAD_LETTER jobs as dicts"""
        dead_letter = []
        
        for filename in os.listdir(self.jobs_dir):
            if not filename.endswith(".json"):
                continue
            
            job_file = os.path.join(self.jobs_dir, filename)
            try:
                with open(job_file) as f:
                    job_data = json.load(f)
                
                if job_data.get("status") == DEAD_LETTER:
                    dead_letter.append(job_data)
            except (json.JSONDecodeError, IOError):
                continue
        
        return dead_letter
    
    def _save_job(self, job: ParseJob):
        """Persist job to disk as JSON"""
        # Always update the updated_at timestamp when saving
        job.updated_at = time.time()
        job_file = os.path.join(self.jobs_dir, f"{job.job_id}.json")
        job_dict = asdict(job)
        
        with open(job_file, "w") as f:
            json.dump(job_dict, f, indent=2)
    
    def _dict_to_job(self, job_dict: Dict[str, Any]) -> ParseJob:
        """Convert dict back to ParseJob"""
        now = time.time()
        return ParseJob(
            job_id=job_dict.get("job_id"),
            narrative=job_dict.get("narrative"),
            date=job_dict.get("date"),
            time=job_dict.get("time"),
            status=job_dict.get("status", QUEUED),
            created_at=job_dict.get("created_at", now),
            updated_at=job_dict.get("updated_at", now),
            idempotency_key=job_dict.get("idempotency_key"),
            retries=job_dict.get("retries", 0),
            max_retries=job_dict.get("max_retries", 3),
            result=job_dict.get("result"),
            error=job_dict.get("error"),
            next_retry_at=job_dict.get("next_retry_at"),
            processing_started_at=job_dict.get("processing_started_at")
        )


# Global JobStore instance
_store = None

# Completion callbacks: called after SUCCESS or DEAD_LETTER with (job, raw_id)
# raw_id is extracted from idempotency_key "stage_a:<raw_id>" if present.
_on_success_callback = None
_on_failure_callback = None


def register_completion_callbacks(on_success=None, on_failure=None):
    """Register callbacks invoked after job reaches SUCCESS or DEAD_LETTER."""
    global _on_success_callback, _on_failure_callback
    _on_success_callback = on_success
    _on_failure_callback = on_failure


def _extract_raw_id(job: ParseJob):
    """Extract raw_id from stage-specific idempotency keys."""
    key = job.idempotency_key or ""
    if key.startswith("stage_a:"):
        return key[len("stage_a:"):]
    if key.startswith("stage_a_replay:"):
        parts = key.split(":")
        if len(parts) >= 2:
            return parts[1]
    return None


def get_store(data_dir: str = None) -> JobStore:
    """Get or create the global JobStore"""
    global _store
    
    # Allow override via environment variable
    if data_dir is None:
        import os as os_module
        data_dir = os_module.environ.get("JOB_QUEUE_DATA_DIR", "data")
    
    # Recreate if data_dir changed (for testing)
    if _store is None or _store.data_dir != data_dir:
        _store = JobStore(data_dir)
    
    return _store


# Module-level API (wraps JobStore for convenience)


def enqueue_parse(
    narrative: str,
    date: str,
    time_str: str,
    idempotency_key: Optional[str] = None,
    data_dir: str = None
) -> str:
    """Enqueue a parse job. Returns job_id."""
    if data_dir is None:
        import os as os_module
        data_dir = os_module.environ.get("JOB_QUEUE_DATA_DIR", "data")
    
    # Always get fresh store for current data_dir
    global _store
    if _store is None or _store.data_dir != data_dir:
        _store = JobStore(data_dir)
    
    return _store.enqueue_parse(narrative, date, time_str, idempotency_key)


def get_job_status(job_id: str, data_dir: str = None) -> Optional[ParseJob]:
    """Get job status by ID"""
    if data_dir is None:
        import os as os_module
        data_dir = os_module.environ.get("JOB_QUEUE_DATA_DIR", "data")
    
    global _store
    if _store is None or _store.data_dir != data_dir:
        _store = JobStore(data_dir)
    
    return _store.get_job_status(job_id)


def dequeue_next(data_dir: str = None) -> Optional[ParseJob]:
    """Dequeue next QUEUED job. Marks as PROCESSING."""
    if data_dir is None:
        import os as os_module
        data_dir = os_module.environ.get("JOB_QUEUE_DATA_DIR", "data")
    
    global _store
    if _store is None or _store.data_dir != data_dir:
        _store = JobStore(data_dir)
    
    return _store.dequeue_next()


def mark_success(job_id: str, result: Dict[str, Any], data_dir: str = None):
    """Mark job as successfully processed"""
    if data_dir is None:
        import os as os_module
        data_dir = os_module.environ.get("JOB_QUEUE_DATA_DIR", "data")
    
    global _store
    if _store is None or _store.data_dir != data_dir:
        _store = JobStore(data_dir)
    
    _store.mark_success(job_id, result)


def mark_failed(
    job_id: str,
    error_type: str,
    error_message: str,
    data_dir: str = None,
    schedule_retry: bool = False,
):
    """Mark job as failed with specific error type"""
    if data_dir is None:
        import os as os_module
        data_dir = os_module.environ.get("JOB_QUEUE_DATA_DIR", "data")
    
    global _store
    if _store is None or _store.data_dir != data_dir:
        _store = JobStore(data_dir)
    
    _store.mark_failed(job_id, error_type, error_message, schedule_retry=schedule_retry)


def retry_failed_jobs(max_age_seconds: int = 0, data_dir: str = None, respect_schedule: bool = False):
    """Requeue any retry-eligible failed jobs"""
    if data_dir is None:
        import os as os_module
        data_dir = os_module.environ.get("JOB_QUEUE_DATA_DIR", "data")
    
    global _store
    if _store is None or _store.data_dir != data_dir:
        _store = JobStore(data_dir)
    
    _store.retry_failed_jobs(max_age_seconds, respect_schedule=respect_schedule)


def startup_recovery(stale_threshold_seconds: int = 300, data_dir: str = None):
    """Recover any incomplete PROCESSING jobs on worker startup"""
    if data_dir is None:
        import os as os_module
        data_dir = os_module.environ.get("JOB_QUEUE_DATA_DIR", "data")
    
    global _store
    if _store is None or _store.data_dir != data_dir:
        _store = JobStore(data_dir)
    
    _store.startup_recovery(stale_threshold_seconds)


def get_dead_letter_jobs(data_dir: str = None) -> list:
    """Retrieve all DEAD_LETTER jobs"""
    if data_dir is None:
        import os as os_module
        data_dir = os_module.environ.get("JOB_QUEUE_DATA_DIR", "data")
    
    global _store
    if _store is None or _store.data_dir != data_dir:
        _store = JobStore(data_dir)
    
    return _store.get_dead_letter_jobs()


def list_dead_letter_queue(data_dir: str = None) -> list:
    """Retrieve all DEAD_LETTER jobs (alias for get_dead_letter_jobs)"""
    return get_dead_letter_jobs(data_dir)


def process_job(job: ParseJob, providers: list | None = None, data_dir: str = None) -> bool:
    """
    Process a single job by invoking providers in sequence.
    On success, mark_success. On failure, mark_failed.
    
    This is called by the worker loop and delegates to parse_service/router.
    Returns: True if success, False if failed.
    """
    if data_dir is None:
        import os as os_module
        data_dir = os_module.environ.get("JOB_QUEUE_DATA_DIR", "data")

    try:
        result = parse_event_payload(job.narrative, job.date, job.time)
        is_valid, errors = validate_extraction_output(result)
        if not is_valid:
            raise ParseFailureError(errors)
        # LLM judge: review extraction before committing
        try:
            judge_router = _get_judge_router()
            verdict, corrected = judge_extraction(
                judge_router, job.narrative, result, job.narrative
            )
            original_actors = list(result.get("actor_names", []))
            result["judge_pass"] = verdict.get("pass", True)
            result["judge_flags"] = verdict.get("flags", [])
            if corrected is not None:
                result["actor_names"] = corrected
                result["judge_correction_applied"] = True
                result["judge_actor_diff"] = {
                    "original_extractor_actors": original_actors,
                    "added_by_judge": [n for n in corrected if n not in original_actors],
                    "removed_by_judge": [n for n in original_actors if n not in corrected],
                }
            else:
                result["judge_correction_applied"] = False
                result["judge_actor_diff"] = None
        except Exception:
            result.setdefault("judge_pass", True)
            result.setdefault("judge_flags", [])
            result.setdefault("judge_correction_applied", False)
            result.setdefault("judge_actor_diff", None)
        mark_success(job.job_id, result, data_dir=data_dir)
        completed_job = get_job_status(job.job_id, data_dir=data_dir)
        if _on_success_callback and completed_job:
            raw_id = _extract_raw_id(completed_job)
            if raw_id:
                try:
                    _on_success_callback(completed_job, raw_id)
                except Exception:
                    pass
        return True
    except ParseModelTimeoutError as exc:
        mark_failed(
            job.job_id,
            FAILED_TIMEOUT,
            str(exc),
            data_dir=data_dir,
            schedule_retry=True,
        )
    except ParseModelUnavailableError as exc:
        mark_failed(
            job.job_id,
            FAILED_UNAVAILABLE,
            str(exc),
            data_dir=data_dir,
            schedule_retry=True,
        )
    except ParseFailureError as exc:
        mark_failed(
            job.job_id,
            FAILED_PARSE,
            str(exc),
            data_dir=data_dir,
            schedule_retry=True,
        )
    except Exception as exc:
        # Keep the worker loop alive even when an unforeseen provider error escapes.
        mark_failed(
            job.job_id,
            FAILED_PARSE,
            f"Unexpected parse failure: {exc}",
            data_dir=data_dir,
            schedule_retry=True,
        )
    # Check if job reached DEAD_LETTER after this failure
    failed_job = get_job_status(job.job_id, data_dir=data_dir)
    if failed_job and failed_job.status == DEAD_LETTER and _on_failure_callback:
        raw_id = _extract_raw_id(failed_job)
        if raw_id:
            try:
                _on_failure_callback(failed_job, raw_id)
            except Exception:
                pass
    return False
