"""Agent factory for creating LangGraph agents with HITL support."""

import os
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.tools import StructuredTool
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.prebuilt import create_react_agent
from langgraph.types import Command

from agent_platform.agent.tools.hitl import HITLToolManager, HITLWrappedTool
from agent_platform.config import get_settings
from agent_platform.services.hitl_rules import HITLRulesEngine
from agent_platform.services.skill_registry import SkillRegistry, get_skill_registry

if TYPE_CHECKING:
    from agent_platform.models.session import Session
    from agent_platform.models.user import User

settings = get_settings()


def get_basic_tools() -> list[StructuredTool]:
    """Get basic tool set for agent.

    DEPRECATED: Use get_tools_for_session() instead for skill-based tool loading.

    Returns:
        List of structured tools
    """
    # Use SkillRegistry to load builtin tools for backward compatibility
    registry = get_skill_registry()
    tools = []

    # Load file_ops tools
    try:
        file_ops_tools = registry.get_skill_tools("file_ops", auto_grant=True)
        tools.extend(file_ops_tools)
    except Exception:
        pass

    # Load bash tools
    try:
        bash_tools = registry.get_skill_tools("bash", auto_grant=True)
        tools.extend(bash_tools)
    except Exception:
        pass

    return tools


async def get_tools_for_session(
    session: "Session",
    user: Optional["User"] = None,
    db: Optional[Any] = None,
) -> list[StructuredTool]:
    """Get tools for a session using the Skill Registry.

    This is the recommended way to get tools for a session.
    It properly handles skill permissions and backward compatibility.

    Args:
        session: Session to get tools for
        user: User associated with the session
        db: Database session for skill lookups

    Returns:
        List of structured tools
    """
    registry = get_skill_registry(db=db)
    return await registry.get_tools_for_session(session, user)


def get_basic_tools_with_hitl(
    session_id: Optional[str] = None,
    task_id: Optional[str] = None,
    thread_id: Optional[str] = None,
    custom_rules: Optional[list[dict]] = None,
    tools: Optional[list[StructuredTool]] = None,
) -> list[HITLWrappedTool]:
    """Get tool set with HITL wrapping.

    Args:
        session_id: Optional session ID for tracking
        task_id: Optional task ID for tracking
        thread_id: Optional LangGraph thread ID
        custom_rules: Optional custom HITL rules
        tools: Optional list of tools to wrap (defaults to basic tools)

    Returns:
        List of HITL-wrapped tools
    """
    rules_engine = HITLRulesEngine(custom_rules=custom_rules)
    manager = HITLToolManager(
        rules_engine=rules_engine,
        session_id=session_id,
        task_id=task_id,
        thread_id=thread_id,
    )

    # Use provided tools or fall back to basic tools
    tools_to_wrap = tools if tools is not None else get_basic_tools()

    # Wrap all tools
    wrapped_tools = []
    for tool in tools_to_wrap:
        wrapped = manager.wrap_tool(
            tool.func if hasattr(tool, "func") else tool.coroutine,
            tool_name=tool.name,
        )
        wrapped_tools.append(wrapped)

    return wrapped_tools


async def create_checkpointer() -> AsyncPostgresSaver:
    """Create PostgreSQL checkpointer for conversation persistence.

    Returns:
        AsyncPostgresSaver instance
    """
    # Parse database URL for asyncpg
    db_url = str(settings.DATABASE_URL)

    # Create checkpointer
    checkpointer = AsyncPostgresSaver.from_conn_string(db_url)

    # Setup schema (creates checkpoint tables)
    await checkpointer.asetup()

    return checkpointer


async def create_agent(
    model_name: str = "claude-sonnet-4-6",
    system_prompt: str | None = None,
    tools: list[StructuredTool] | None = None,
    thread_id: str | None = None,
    enable_hitl: bool = False,
    session_id: Optional[str] = None,
    task_id: Optional[str] = None,
    custom_hitl_rules: Optional[list[dict]] = None,
    session: Optional["Session"] = None,
    user: Optional["User"] = None,
    db: Optional[Any] = None,
) -> tuple[Any, AsyncPostgresSaver]:
    """Create a LangGraph agent with PostgreSQL persistence and optional HITL.

    Args:
        model_name: Claude model name
        system_prompt: Optional system prompt
        tools: Optional custom tools (defaults to skill-based tools)
        thread_id: Optional thread ID for persistence
        enable_hitl: Whether to enable Human-in-the-Loop approval
        session_id: Optional session ID for HITL tracking
        task_id: Optional task ID for HITL tracking
        custom_hitl_rules: Optional custom HITL rules
        session: Optional Session object for skill-based tool loading
        user: Optional User object for permission checks
        db: Optional database session

    Returns:
        Tuple of (agent, checkpointer)
    """
    # Get API key from environment
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable not set")

    # Create model
    model = ChatAnthropic(
        model=model_name,
        api_key=api_key,
        temperature=0.7,
        max_tokens=4096,
    )

    # Get tools
    if tools is not None:
        # Use explicitly provided tools
        agent_tools = tools
    elif session is not None:
        # Use skill-based tool loading for the session
        agent_tools = await get_tools_for_session(session, user, db)
    else:
        # Secure default: no implicit local subprocess or filesystem tools.
        agent_tools = []

    # Apply HITL wrapping if enabled
    if enable_hitl:
        wrapped_tools = get_basic_tools_with_hitl(
            session_id=session_id,
            task_id=task_id,
            thread_id=thread_id,
            custom_rules=custom_hitl_rules,
            tools=agent_tools,
        )
        # Convert to structured tools for LangGraph
        agent_tools = [tool.to_structured_tool() for tool in wrapped_tools]

    # Create checkpointer
    checkpointer = await create_checkpointer()

    # Default system prompt
    if not system_prompt:
        has_tools = len(agent_tools) > 0
        if has_tools:
            system_prompt = (
                "You are a helpful AI assistant with access to the tools explicitly "
                "granted for this session. Use tools when needed to help the user "
                "accomplish their tasks."
            )
        else:
            system_prompt = (
                "You are a helpful AI assistant. "
                "You do not have access to any external tools."
            )
        if enable_hitl:
            system_prompt += (
                " Some operations may require human approval before execution. "
                "You will be notified when approval is pending."
            )

    # Create agent with checkpointing
    agent = create_react_agent(
        model=model,
        tools=agent_tools,
        checkpointer=checkpointer,
        prompt=system_prompt,
    )

    return agent, checkpointer


async def stream_agent_response(
    agent: Any,
    message: str,
    thread_id: str,
    resume_from_interrupt: bool = False,
    interrupt_response: Optional[dict] = None,
) -> Any:
    """Stream agent response for a message.

    Args:
        agent: LangGraph agent
        message: User message
        thread_id: Thread ID for persistence
        resume_from_interrupt: Whether to resume from an interrupt
        interrupt_response: Response to provide when resuming from interrupt

    Yields:
        Streaming response chunks
    """
    # Configuration with thread_id for checkpointing
    config = {"configurable": {"thread_id": thread_id}}

    if resume_from_interrupt and interrupt_response:
        # Resume from interrupt with human response
        async for chunk in agent.astream(
            Command(resume=interrupt_response),
            config,
            stream_mode="messages",
        ):
            if isinstance(chunk, tuple) and len(chunk) == 2:
                msg, metadata = chunk
                if isinstance(msg, AIMessage) and msg.content:
                    yield {
                        "type": "content",
                        "content": msg.content,
                    }
            elif isinstance(chunk, AIMessage) and chunk.content:
                yield {
                    "type": "content",
                    "content": chunk.content,
                }
            elif isinstance(chunk, dict) and chunk.get("type") == "hitl_interrupt":
                # Yield interrupt information
                yield {
                    "type": "interrupt",
                    "interrupt": chunk,
                }
    else:
        # Normal streaming
        async for chunk in agent.astream(
            {"messages": [HumanMessage(content=message)]},
            config,
            stream_mode="messages",
        ):
            if isinstance(chunk, tuple) and len(chunk) == 2:
                msg, metadata = chunk
                if isinstance(msg, AIMessage) and msg.content:
                    yield {
                        "type": "content",
                        "content": msg.content,
                    }
            elif isinstance(chunk, AIMessage) and chunk.content:
                yield {
                    "type": "content",
                    "content": chunk.content,
                }
            elif isinstance(chunk, dict) and chunk.get("type") == "hitl_interrupt":
                # Yield interrupt information
                yield {
                    "type": "interrupt",
                    "interrupt": chunk,
                }


async def stream_agent_response_with_hitl(
    agent: Any,
    message: str,
    thread_id: str,
) -> Any:
    """Stream agent response with HITL handling.

    This function handles the full HITL flow including:
    - Detecting when an interrupt occurs
    - Yielding interrupt information for the client
    - Resuming execution after human approval

    Args:
        agent: LangGraph agent with HITL enabled
        message: User message
        thread_id: Thread ID for persistence

    Yields:
        Streaming response chunks or interrupt information
    """
    config = {"configurable": {"thread_id": thread_id}}

    async for chunk in agent.astream(
        {"messages": [HumanMessage(content=message)]},
        config,
        stream_mode="updates",
    ):
        # Check for interrupt in the chunk
        if isinstance(chunk, dict):
            # Check for HITL interrupt
            if "__interrupt__" in chunk:
                interrupt_data = chunk["__interrupt__"]
                yield {
                    "type": "hitl_required",
                    "interrupt": interrupt_data,
                    "message": "Human approval required for tool execution",
                }
                return  # Stop streaming, wait for human input

            # Check for tool execution results
            for node_name, node_data in chunk.items():
                if isinstance(node_data, dict) and "messages" in node_data:
                    for msg in node_data["messages"]:
                        if isinstance(msg, AIMessage) and msg.content:
                            yield {
                                "type": "content",
                                "content": msg.content,
                            }


def create_hitl_resume_command(
    decision: str,
    reason: Optional[str] = None,
    user_id: Optional[str] = None,
) -> Command:
    """Create a command to resume execution after HITL approval.

    Args:
        decision: The decision ("approved" or "rejected")
        reason: Optional reason for the decision
        user_id: ID of the user who made the decision

    Returns:
        Command to resume execution
    """
    return Command(resume={
        "decision": decision,
        "reason": reason,
        "user_id": user_id,
        "timestamp": datetime.utcnow().isoformat() if 'datetime' in dir() else None,
    })


# Global checkpointer cache (to avoid reconnecting)
_checkpointer: AsyncPostgresSaver | None = None


async def get_checkpointer() -> AsyncPostgresSaver:
    """Get or create global checkpointer.

    Returns:
        AsyncPostgresSaver instance
    """
    global _checkpointer

    if _checkpointer is None:
        _checkpointer = await create_checkpointer()

    return _checkpointer
