"""Cron-based task scheduler.

Polls the database for tasks with cron expressions and enqueues
them into the Redis Streams task queue when their next run is due.
"""

import asyncio
import logging
import signal
from datetime import datetime, timezone

from croniter import croniter
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from agent_platform.database import AsyncSessionFactory, get_redis
from agent_platform.models.task import Task, TaskStatus, TaskType
from agent_platform.services.task_queue import TaskQueue

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 30


class TaskScheduler:
    """Polls scheduled/recurring tasks and enqueues them when due."""

    def __init__(self) -> None:
        self._running = False

    async def start(self) -> None:
        self._running = True
        logger.info("TaskScheduler starting (poll every %ds)", POLL_INTERVAL_SECONDS)

        while self._running:
            try:
                await self._tick()
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Scheduler tick error, retrying")
            await asyncio.sleep(POLL_INTERVAL_SECONDS)

        logger.info("TaskScheduler stopped")

    async def stop(self) -> None:
        self._running = False

    # ------------------------------------------------------------------

    async def _tick(self) -> None:
        """One scheduler cycle: find due tasks and enqueue them."""
        now = datetime.now(timezone.utc)

        async with AsyncSessionFactory() as db:
            tasks = await self._find_due_tasks(db, now)
            if not tasks:
                return

            redis = await get_redis()
            queue = TaskQueue(redis=redis, db=db)

            for task in tasks:
                await self._handle_task(task, queue, db, now)

    async def _find_due_tasks(self, db: AsyncSession, now: datetime) -> list[Task]:
        """Return scheduled/recurring tasks that are due to run."""
        result = await db.execute(
            select(Task).where(
                and_(
                    Task.type.in_([TaskType.SCHEDULED, TaskType.RECURRING]),
                    Task.status == TaskStatus.PENDING,
                )
            )
        )
        candidates = list(result.scalars().all())

        due: list[Task] = []
        for task in candidates:
            schedule = (task.extra_metadata or {}).get("schedule", {})
            if not schedule.get("enabled", True):
                continue
            cron_expr = schedule.get("cron")
            if not cron_expr:
                continue
            tz_name = schedule.get("timezone", "UTC")
            try:
                cron = croniter(cron_expr, now)
                prev_fire = cron.get_prev(datetime)
                # If last fire time is within this poll window the task is due
                if (now - prev_fire).total_seconds() < POLL_INTERVAL_SECONDS:
                    due.append(task)
            except Exception:
                logger.warning("Invalid cron expression for task %s: %s", task.id, cron_expr)
        return due

    async def _handle_task(
        self, task: Task, queue: TaskQueue, db: AsyncSession, now: datetime
    ) -> None:
        if task.type == TaskType.SCHEDULED:
            # One-shot: enqueue then mark queued (status change prevents re-fire)
            await queue.enqueue(task)
            logger.info("Scheduled task %s enqueued", task.id)
        else:
            # Recurring: clone a new ASYNC child task and enqueue it
            child = Task(
                user_id=task.user_id,
                org_id=task.org_id,
                session_id=task.session_id,
                type=TaskType.ASYNC,
                status=TaskStatus.PENDING,
                prompt=task.prompt,
                priority=task.priority,
                parent_task_id=task.id,
                extra_metadata={"source": "scheduler", "parent_cron": str(task.id)},
            )
            db.add(child)
            await db.flush()
            await queue.enqueue(child)
            # Update next_run hint
            schedule = dict(task.extra_metadata or {}).get("schedule", {})
            try:
                cron = croniter(schedule["cron"], now)
                schedule["next_run_at"] = cron.get_next(datetime).isoformat()
            except Exception:
                pass
            updated = dict(task.extra_metadata or {})
            updated["schedule"] = schedule
            task.extra_metadata = updated
            await db.commit()
            logger.info("Recurring task %s fired child %s", task.id, child.id)


async def main() -> None:
    """Entry point: ``python -m agent_platform.workers.scheduler``."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )

    scheduler = TaskScheduler()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(scheduler.stop()))

    await scheduler.start()


if __name__ == "__main__":
    asyncio.run(main())
