"""Task queue worker.

Consumes tasks from Redis Streams and executes them via TaskRuntime.
Run as a standalone process alongside the API server.
"""

import asyncio
import logging
import os
import signal
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from agent_platform.database import AsyncSessionFactory, get_redis
from agent_platform.services.task_queue import TaskQueue
from agent_platform.services.task_runtime import TaskRuntime

logger = logging.getLogger(__name__)

# Configuration
CONSUMER_NAME = f"worker-{uuid.uuid4().hex[:8]}"
BATCH_SIZE = int(os.getenv("WORKER_BATCH_SIZE", "1"))
BLOCK_MS = int(os.getenv("WORKER_BLOCK_MS", "5000"))
STREAM_NAME = os.getenv("WORKER_STREAM", "agent_platform:tasks")
GROUP_NAME = os.getenv("WORKER_GROUP", "task-workers")


class TaskWorker:
    """Worker that consumes and executes tasks from the Redis queue."""

    def __init__(self, consumer_name: str = CONSUMER_NAME):
        self.consumer_name = consumer_name
        self._running = False

    async def start(self) -> None:
        """Start the worker loop."""
        self._running = True
        logger.info("TaskWorker %s starting", self.consumer_name)

        redis = await get_redis()

        # Ensure consumer group exists
        try:
            await redis.xgroup_create(
                STREAM_NAME, GROUP_NAME, id="0", mkstream=True,
            )
            logger.info("Created consumer group %s", GROUP_NAME)
        except Exception:
            # Group already exists
            pass

        while self._running:
            try:
                await self._poll_once(redis)
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Worker loop error, retrying in 2s")
                await asyncio.sleep(2)

        logger.info("TaskWorker %s stopped", self.consumer_name)

    async def stop(self) -> None:
        """Signal the worker to stop after the current iteration."""
        self._running = False

    async def _poll_once(self, redis) -> None:
        """Read one batch from the stream and process each message."""
        async with AsyncSessionFactory() as db:
            queue = TaskQueue(
                redis=redis,
                db=db,
                stream_name=STREAM_NAME,
                group_name=GROUP_NAME,
            )

            messages = await queue.read(
                consumer=self.consumer_name,
                count=BATCH_SIZE,
                block=BLOCK_MS,
            )

            for msg in messages:
                message_id = msg["message_id"]
                fields = msg["fields"]
                task_id = fields.get("task_id")

                if not task_id:
                    logger.warning("Message %s missing task_id, acking", message_id)
                    await queue.ack(message_id)
                    continue

                logger.info("Processing task %s (msg %s)", task_id, message_id)

                try:
                    await self._execute_task(db, task_id)
                except Exception:
                    logger.exception("Task %s execution failed", task_id)
                finally:
                    await queue.ack(message_id)
                    logger.info("Acked message %s for task %s", message_id, task_id)

    async def _execute_task(self, db: AsyncSession, task_id: str) -> None:
        """Execute a single task via TaskRuntime and drain events."""
        runtime = TaskRuntime(db=db)

        async for event in runtime.execute_task(task_id):
            if event.type == "error":
                logger.error("Task %s error: %s", task_id, event.error)
            elif event.type == "done":
                logger.info("Task %s completed", task_id)
            # Events are streamed; here we just drain them.
            # A future enhancement could publish events to Redis Pub/Sub
            # for SSE clients to pick up in real-time.


async def main() -> None:
    """Entry point for running the worker."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )

    worker = TaskWorker()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(worker.stop()))

    await worker.start()


if __name__ == "__main__":
    asyncio.run(main())
