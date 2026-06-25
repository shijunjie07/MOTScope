from __future__ import annotations

import threading
import traceback
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable


@dataclass
class Job:
    """In-process background job state for local viewer tasks."""
    job_id: str
    title: str
    status: str = "queued"
    progress: int = 0
    message: str = "Queued"
    result: dict[str, Any] | None = None
    error: str | None = None
    traceback: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        """Return a JSON-ready job payload."""
        return {
            "job_id": self.job_id,
            "title": self.title,
            "status": self.status,
            "progress": self.progress,
            "message": self.message,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class JobManager:
    """Small in-memory job runner for long local rendering tasks."""

    def __init__(self):
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def start(self, title: str, work: Callable[[Callable[[int, str], None]], dict]) -> Job:
        """Start ``work`` in a background thread and return initial state."""
        job = Job(job_id=uuid.uuid4().hex, title=title)
        with self._lock:
            self._jobs[job.job_id] = job

        thread = threading.Thread(target=self._run, args=(job.job_id, work), daemon=True)
        thread.start()
        return job

    def get(self, job_id: str) -> Job | None:
        """Return a job by id."""
        with self._lock:
            return self._jobs.get(job_id)

    def update(self, job_id: str, progress: int, message: str) -> None:
        """Update job progress."""
        with self._lock:
            job = self._jobs[job_id]
            job.progress = max(0, min(100, int(progress)))
            job.message = message
            job.updated_at = datetime.now(timezone.utc).isoformat()

    def _run(self, job_id: str, work: Callable[[Callable[[int, str], None]], dict]) -> None:
        with self._lock:
            job = self._jobs[job_id]
            job.status = "running"
            job.message = "Starting"
            job.updated_at = datetime.now(timezone.utc).isoformat()

        def progress(percent: int, message: str) -> None:
            self.update(job_id, percent, message)

        try:
            result = work(progress)
        except Exception as exc:
            with self._lock:
                job = self._jobs[job_id]
                job.status = "failed"
                job.error = str(exc)
                job.traceback = traceback.format_exc()
                job.message = str(exc)
                job.updated_at = datetime.now(timezone.utc).isoformat()
            return

        with self._lock:
            job = self._jobs[job_id]
            job.status = "done"
            job.progress = 100
            job.message = "Complete"
            job.result = result
            job.updated_at = datetime.now(timezone.utc).isoformat()
