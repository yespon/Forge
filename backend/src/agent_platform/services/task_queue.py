"""Redis Streams style task queue service."""

import json
from typing import Any

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from agent_platform.models.task import Task


class TaskQueue:
    """Small wrapper around Redis Streams for task scheduling."""

    def __init__(
        self,
        redis: Redis,
        db: AsyncSession,
        stream_name: str = "agent_platform:tasks",
        group_name: str = "task-workers",
    ):
        self.redis = redis
        self.db = db
        self.stream_name = stream_name
        self.group_name = group_name

    async def enqueue(self, task: Task) -> str:
        """Add a task to the stream and persist the Redis message id."""
        message_id = await self.redis.xadd(
            self.stream_name,
            {
                "task_id": str(task.id),
                "user_id": str(task.user_id),
                "org_id": str(task.org_id),
                "session_id": str(task.session_id),
                "type": str(task.type),
                "priority": str(task.priority),
                "payload": json.dumps({"prompt": task.prompt}),
            },
            maxlen=10000,
            approximate=True,
        )
        if isinstance(message_id, bytes):
            message_id = message_id.decode()

        task.redis_message_id = str(message_id)
        task.mark_queued()
        await self.db.commit()
        return str(message_id)

    async def read(self, consumer: str, count: int = 1, block: int = 1000) -> list[dict[str, Any]]:
        """Read queued task messages for a worker consumer."""
        response = await self.redis.xreadgroup(
            self.group_name,
            consumer,
            {self.stream_name: ">"},
            count=count,
            block=block,
        )
        messages: list[dict[str, Any]] = []
        for _stream, entries in response:
            for message_id, fields in entries:
                messages.append(
                    {
                        "message_id": self._decode(message_id),
                        "fields": {
                            self._decode(key): self._decode(value)
                            for key, value in fields.items()
                        },
                    }
                )
        return messages

    async def ack(self, message_id: str) -> bool:
        """Acknowledge a processed stream message."""
        return bool(await self.redis.xack(self.stream_name, self.group_name, message_id))

    @staticmethod
    def _decode(value: Any) -> Any:
        if isinstance(value, bytes):
            return value.decode()
        return value
