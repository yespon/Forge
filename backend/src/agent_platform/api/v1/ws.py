"""WebSocket endpoint for real-time bi-directional session communication.

Provides:
  - ws://…/api/v1/sessions/{session_id}/ws?token=<jwt>
  - Server → client: content chunks, tool calls, HITL interrupts, task events
  - Client → server: chat messages, HITL decisions, pings
"""

import json
import logging
from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from sqlalchemy import select

from agent_platform.auth.jwt import decode_token
from agent_platform.database import AsyncSessionFactory
from agent_platform.models.session import Session, SessionStatus
from agent_platform.models.task import TaskType
from agent_platform.models.user import User
from agent_platform.services.task_runtime import TaskRuntime

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])


@router.websocket("/sessions/{session_id}/ws")
async def session_websocket(
    websocket: WebSocket,
    session_id: UUID,
    token: str = Query(...),
) -> None:
    """Full-duplex WebSocket for a session.

    Authentication via ``?token=<jwt>`` query parameter.
    """
    # --- authenticate ---
    try:
        payload = decode_token(token)
        user_id = payload.get("sub")
        if not user_id:
            await websocket.close(code=4001, reason="Invalid token")
            return
    except Exception:
        await websocket.close(code=4001, reason="Invalid token")
        return

    await websocket.accept()

    async with AsyncSessionFactory() as db:
        # --- validate session ownership ---
        result = await db.execute(
            select(Session).where(
                Session.id == session_id,
                Session.user_id == user_id,
            )
        )
        session = result.scalar_one_or_none()
        if not session:
            await websocket.send_json({"type": "error", "error": "Session not found"})
            await websocket.close(code=4004)
            return

        user_result = await db.execute(select(User).where(User.id == user_id))
        user = user_result.scalar_one_or_none()
        if not user:
            await websocket.close(code=4001)
            return

        await websocket.send_json({"type": "connected", "session_id": str(session_id)})

        # --- message loop ---
        try:
            while True:
                raw = await websocket.receive_text()
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    await websocket.send_json({"type": "error", "error": "Invalid JSON"})
                    continue

                msg_type = msg.get("type")

                if msg_type == "ping":
                    await websocket.send_json({"type": "pong"})

                elif msg_type == "chat":
                    content = (msg.get("content") or "").strip()
                    if not content:
                        await websocket.send_json({"type": "error", "error": "Empty message"})
                        continue

                    # Resume session if paused
                    if session.status == SessionStatus.PAUSED:
                        session.status = SessionStatus.ACTIVE
                    session.touch()
                    await db.commit()

                    # Execute via TaskRuntime, streaming events back over WS
                    runtime = TaskRuntime(db=db)
                    task = await runtime.create_task(
                        session_id=session.id,
                        user_id=user.id,
                        prompt=content,
                        task_type=TaskType.SYNC,
                        org_id=user.org_id,
                        enable_hitl=True,
                    )

                    await websocket.send_json({
                        "type": "task_started",
                        "task_id": str(task.id),
                    })

                    async for event in runtime.execute_task(task.id):
                        await websocket.send_json({
                            "type": event.type,
                            "content": event.content,
                            "tool_name": event.tool_name,
                            "tool_input": event.tool_input,
                            "tool_output": event.tool_output,
                            "error": event.error,
                        })

                    await websocket.send_json({"type": "done", "task_id": str(task.id)})

                else:
                    await websocket.send_json({"type": "error", "error": f"Unknown type: {msg_type}"})

        except WebSocketDisconnect:
            logger.info("WebSocket disconnected for session %s", session_id)
