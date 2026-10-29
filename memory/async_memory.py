"""Asynchronous Memory Generation and Background Consolidation.

Executes expensive memory operations (diff generation, database writes, embedding
indexing, and historical rollups) as asynchronous background tasks, preventing
latency spikes or UI blocking in the live agent execution loop.
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Any
from memory.session_state import SessionStateRepository
from schemas.college import CollegeMatchRecommendation


class AsyncMemoryManager:
    """Orchestrates non-blocking background consolidation of agent memories and states."""

    def __init__(self, repository: SessionStateRepository | None = None):
        """Initializes memory manager with dedicated thread pool."""
        self.repository = repository or SessionStateRepository()
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="async-memory-worker")

    async def schedule_background_snapshot_consolidation(
        self,
        run_id: str,
        student_id: str,
        recommendations: list[CollegeMatchRecommendation],
    ) -> asyncio.Task:
        """Asynchronously dispatches snapshot persistence and diff analysis to background worker.

        This guarantees that the student receives their results immediately without waiting
        for SQL commits, weekly diff computations, or audit log persistence.

        Args:
            run_id: Unique execution identifier.
            student_id: Student applicant identifier.
            recommendations: Finalized list of 10 college recommendations.

        Returns:
            Running asyncio.Task handle.
        """
        loop = asyncio.get_running_loop()

        def _blocking_consolidation():
            # 1. Record snapshot to SQLite datastore
            self.repository.record_run_snapshot(
                run_id=run_id,
                student_id=student_id,
                recommendations=recommendations,
                status="COMPLETED",
            )
            # 2. Compute weekly diffs for audit trail
            diffs = self.repository.detect_weekly_changes(student_id, recommendations)
            return {"run_id": run_id, "diffs_detected": len(diffs), "summary": diffs}

        # Run in thread pool without blocking event loop
        task = loop.run_in_executor(self._executor, _blocking_consolidation)
        return asyncio.create_task(task)

    def shutdown(self) -> None:
        """Gracefully terminates background thread pool."""
        self._executor.shutdown(wait=False)
