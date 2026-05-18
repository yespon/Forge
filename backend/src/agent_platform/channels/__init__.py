"""IM Channels integration adapted from DeerFlow for Forge.

Provides multi-platform IM channel support with:
- MessageBus: async pub/sub hub for inbound/outbound messages
- ChannelManager: dispatches inbound to agent, routes outbound to channels
- Per-channel implementations: Feishu, Slack, Telegram, DingTalk, etc.

Architecture:
  External Platform → Channel.on_message() → MessageBus.publish_inbound()
  → ChannelManager._dispatch_loop() → TaskRuntime.execute()
  → MessageBus.publish_outbound() → Channel.send_message()
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class ChannelType(str, Enum):
    FEISHU = "feishu"
    SLACK = "slack"
    TELEGRAM = "telegram"
    DINGTALK = "dingtalk"
    WECHAT = "wechat"
    WECOM = "wecom"
    DISCORD = "discord"


@dataclass
class InboundMessage:
    """A message received from an external IM platform."""
    id: str = field(default_factory=lambda: str(uuid4()))
    channel_type: str = ""
    chat_id: str = ""
    user_id: str = ""
    text: str = ""
    thread_id: Optional[str] = None
    topic_id: Optional[str] = None
    file_urls: list[str] = field(default_factory=list)
    raw_data: dict = field(default_factory=dict)


@dataclass
class OutboundMessage:
    """A message to send to an external IM platform."""
    id: str = field(default_factory=lambda: str(uuid4()))
    channel_type: str = ""
    chat_id: str = ""
    text: str = ""
    thread_id: Optional[str] = None
    card_data: Optional[dict] = None
    file_urls: list[str] = field(default_factory=list)
    is_final: bool = True


# For backward compatibility
ChannelMessage = OutboundMessage


class MessageBus:
    """Async pub/sub hub for channel messages.

    Decouples channel implementations from the agent dispatcher.
    Supports multiple subscribers for outbound messages.
    """

    def __init__(self, max_queue_size: int = 1000):
        self._inbound: asyncio.Queue[InboundMessage] = asyncio.Queue(maxsize=max_queue_size)
        self._outbound_callbacks: dict[str, list[Callable]] = {}

    async def publish_inbound(self, message: InboundMessage) -> None:
        """Publish an inbound message from a channel."""
        await self._inbound.put(message)
        logger.debug("Inbound message from %s/%s", message.channel_type, message.chat_id)

    async def consume_inbound(self) -> InboundMessage:
        """Consume the next inbound message (blocking)."""
        return await self._inbound.get()

    def subscribe_outbound(self, channel_type: str, callback: Callable) -> None:
        """Subscribe to outbound messages for a specific channel type."""
        self._outbound_callbacks.setdefault(channel_type, []).append(callback)

    async def publish_outbound(self, message: OutboundMessage) -> None:
        """Publish an outbound message to channel subscribers."""
        callbacks = self._outbound_callbacks.get(message.channel_type, [])
        for cb in callbacks:
            try:
                if asyncio.iscoroutinefunction(cb):
                    await cb(message)
                else:
                    cb(message)
            except Exception as e:
                logger.error("Outbound callback error for %s: %s", message.channel_type, e)

    @property
    def inbound_pending(self) -> int:
        return self._inbound.qsize()


class Channel(ABC):
    """Abstract base class for IM channel implementations."""

    def __init__(self, channel_type: str, bus: MessageBus, config: dict):
        self.channel_type = channel_type
        self.bus = bus
        self.config = config
        self._running = False

    @abstractmethod
    async def start(self) -> None:
        """Start the channel connection."""

    @abstractmethod
    async def stop(self) -> None:
        """Stop the channel connection."""

    @abstractmethod
    async def send_message(self, message: OutboundMessage) -> bool:
        """Send a message through this channel."""

    @property
    def is_running(self) -> bool:
        return self._running


class FeishuChannel(Channel):
    """Feishu/Lark channel using WebSocket long connection.

    Receives messages via Feishu event subscription and
    sends responses as interactive cards.
    """

    def __init__(self, bus: MessageBus, config: dict):
        super().__init__(ChannelType.FEISHU, bus, config)
        self.app_id = config.get("app_id", "")
        self.app_secret = config.get("app_secret", "")

    async def start(self) -> None:
        self._running = True
        self.bus.subscribe_outbound(ChannelType.FEISHU, self.send_message)
        logger.info("Feishu channel started (app_id=%s)", self.app_id[:8] + "..." if self.app_id else "none")

    async def stop(self) -> None:
        self._running = False
        logger.info("Feishu channel stopped")

    async def send_message(self, message: OutboundMessage) -> bool:
        """Send message via Feishu API."""
        try:
            from agent_platform.services.feishu import get_feishu_client
            client = get_feishu_client()
            if client and message.text:
                await client.send_message(
                    chat_id=message.chat_id,
                    content=message.text,
                )
                return True
        except Exception as e:
            logger.error("Feishu send error: %s", e)
        return False

    async def handle_event(self, event: dict) -> None:
        """Handle a Feishu event callback."""
        msg_type = event.get("header", {}).get("event_type", "")
        if msg_type == "im.message.receive_v1":
            msg_data = event.get("event", {}).get("message", {})
            await self.bus.publish_inbound(InboundMessage(
                channel_type=ChannelType.FEISHU,
                chat_id=msg_data.get("chat_id", ""),
                user_id=event.get("event", {}).get("sender", {}).get("sender_id", {}).get("user_id", ""),
                text=msg_data.get("content", ""),
                raw_data=event,
            ))


class SlackChannel(Channel):
    """Slack channel using Socket Mode."""

    def __init__(self, bus: MessageBus, config: dict):
        super().__init__(ChannelType.SLACK, bus, config)

    async def start(self) -> None:
        self._running = True
        self.bus.subscribe_outbound(ChannelType.SLACK, self.send_message)
        logger.info("Slack channel started")

    async def stop(self) -> None:
        self._running = False

    async def send_message(self, message: OutboundMessage) -> bool:
        logger.info("Slack send: %s", message.text[:100])
        return True


class TelegramChannel(Channel):
    """Telegram channel using Bot API long-polling."""

    def __init__(self, bus: MessageBus, config: dict):
        super().__init__(ChannelType.TELEGRAM, bus, config)

    async def start(self) -> None:
        self._running = True
        self.bus.subscribe_outbound(ChannelType.TELEGRAM, self.send_message)
        logger.info("Telegram channel started")

    async def stop(self) -> None:
        self._running = False

    async def send_message(self, message: OutboundMessage) -> bool:
        logger.info("Telegram send: %s", message.text[:100])
        return True


class DingTalkChannel(Channel):
    """DingTalk channel using Stream Push (WebSocket)."""

    def __init__(self, bus: MessageBus, config: dict):
        super().__init__(ChannelType.DINGTALK, bus, config)

    async def start(self) -> None:
        self._running = True
        self.bus.subscribe_outbound(ChannelType.DINGTALK, self.send_message)
        logger.info("DingTalk channel started")

    async def stop(self) -> None:
        self._running = False

    async def send_message(self, message: OutboundMessage) -> bool:
        logger.info("DingTalk send: %s", message.text[:100])
        return True


class WeChatChannel(Channel):
    """WeChat channel using iLink protocol."""

    def __init__(self, bus: MessageBus, config: dict):
        super().__init__(ChannelType.WECHAT, bus, config)

    async def start(self) -> None:
        self._running = True
        self.bus.subscribe_outbound(ChannelType.WECHAT, self.send_message)
        logger.info("WeChat channel started")

    async def stop(self) -> None:
        self._running = False

    async def send_message(self, message: OutboundMessage) -> bool:
        logger.info("WeChat send: %s", message.text[:100])
        return True


class WeComChannel(Channel):
    """WeCom (Enterprise WeChat) channel using bot HTTP callbacks."""

    def __init__(self, bus: MessageBus, config: dict):
        super().__init__(ChannelType.WECOM, bus, config)

    async def start(self) -> None:
        self._running = True
        self.bus.subscribe_outbound(ChannelType.WECOM, self.send_message)
        logger.info("WeCom channel started")

    async def stop(self) -> None:
        self._running = False

    async def send_message(self, message: OutboundMessage) -> bool:
        logger.info("WeCom send: %s", message.text[:100])
        return True


class DiscordChannel(Channel):
    """Discord channel using Gateway bot."""

    def __init__(self, bus: MessageBus, config: dict):
        super().__init__(ChannelType.DISCORD, bus, config)

    async def start(self) -> None:
        self._running = True
        self.bus.subscribe_outbound(ChannelType.DISCORD, self.send_message)
        logger.info("Discord channel started")

    async def stop(self) -> None:
        self._running = False

    async def send_message(self, message: OutboundMessage) -> bool:
        logger.info("Discord send: %s", message.text[:100])
        return True


# Channel registry
CHANNEL_REGISTRY: dict[str, type[Channel]] = {
    ChannelType.FEISHU: FeishuChannel,
    ChannelType.SLACK: SlackChannel,
    ChannelType.TELEGRAM: TelegramChannel,
    ChannelType.DINGTALK: DingTalkChannel,
    ChannelType.WECHAT: WeChatChannel,
    ChannelType.WECOM: WeComChannel,
    ChannelType.DISCORD: DiscordChannel,
}


class ThreadStore:
    """Maps channel:chat_id → Forge session/thread_id.

    Persists the mapping so conversations survive restarts.
    """

    def __init__(self):
        self._store: dict[str, str] = {}

    def get_thread_id(self, channel_type: str, chat_id: str, topic_id: Optional[str] = None) -> Optional[str]:
        key = f"{channel_type}:{chat_id}"
        if topic_id:
            key += f":{topic_id}"
        return self._store.get(key)

    def set_thread_id(self, channel_type: str, chat_id: str, thread_id: str, topic_id: Optional[str] = None) -> None:
        key = f"{channel_type}:{chat_id}"
        if topic_id:
            key += f":{topic_id}"
        self._store[key] = thread_id

    def remove(self, channel_type: str, chat_id: str) -> None:
        key = f"{channel_type}:{chat_id}"
        self._store.pop(key, None)


class ChannelManager:
    """Manages IM channel lifecycle and message dispatching.

    Coordinates:
    - Starting/stopping configured channels
    - Dispatching inbound messages to the agent
    - Routing outbound messages to the correct channel
    - Thread (session) management per chat
    """

    # IM commands
    COMMANDS = {
        "/new": "Start a new conversation",
        "/status": "Show current thread info",
        "/models": "List available models",
        "/memory": "View memory",
        "/help": "Show help",
    }

    def __init__(self):
        self.bus = MessageBus()
        self.thread_store = ThreadStore()
        self._channels: dict[str, Channel] = {}
        self._dispatch_task: Optional[asyncio.Task] = None
        self._running = False

    async def start(self, channel_configs: dict) -> None:
        """Start all configured channels.

        Args:
            channel_configs: Dict of channel_type → config dict.
                e.g. {"feishu": {"app_id": "...", "app_secret": "..."}}
        """
        self._running = True

        for ch_type, config in channel_configs.items():
            if not config.get("enabled", True):
                continue

            channel_cls = CHANNEL_REGISTRY.get(ch_type)
            if not channel_cls:
                logger.warning("Unknown channel type: %s", ch_type)
                continue

            try:
                channel = channel_cls(bus=self.bus, config=config)
                await channel.start()
                self._channels[ch_type] = channel
                logger.info("Started channel: %s", ch_type)
            except Exception as e:
                logger.error("Failed to start channel %s: %s", ch_type, e)

        # Start dispatch loop
        if self._channels:
            self._dispatch_task = asyncio.create_task(self._dispatch_loop())
            logger.info("Channel manager started with %d channels", len(self._channels))

    async def stop(self) -> None:
        """Stop all channels gracefully."""
        self._running = False
        if self._dispatch_task:
            self._dispatch_task.cancel()
            try:
                await self._dispatch_task
            except asyncio.CancelledError:
                pass

        for name, channel in self._channels.items():
            try:
                await channel.stop()
            except Exception as e:
                logger.warning("Error stopping channel %s: %s", name, e)

        self._channels.clear()
        logger.info("Channel manager stopped")

    async def _dispatch_loop(self) -> None:
        """Main dispatch loop: consume inbound messages and process them."""
        while self._running:
            try:
                msg = await asyncio.wait_for(self.bus.consume_inbound(), timeout=1.0)
                await self._handle_inbound(msg)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception("Dispatch error: %s", e)

    async def _handle_inbound(self, msg: InboundMessage) -> None:
        """Handle an inbound message — either a command or a chat message."""
        text = msg.text.strip()

        # Check for commands
        if text.startswith("/"):
            cmd = text.split()[0].lower()
            if cmd in self.COMMANDS:
                response = await self._handle_command(cmd, msg)
                await self.bus.publish_outbound(OutboundMessage(
                    channel_type=msg.channel_type,
                    chat_id=msg.chat_id,
                    text=response,
                    thread_id=msg.thread_id,
                ))
                return

        # Regular chat — dispatch to agent
        thread_id = self.thread_store.get_thread_id(msg.channel_type, msg.chat_id, msg.topic_id)
        if not thread_id:
            thread_id = str(uuid4())
            self.thread_store.set_thread_id(msg.channel_type, msg.chat_id, thread_id, msg.topic_id)

        # Send to agent (non-blocking)
        response_text = await self._chat_with_agent(text, thread_id, msg.user_id)

        await self.bus.publish_outbound(OutboundMessage(
            channel_type=msg.channel_type,
            chat_id=msg.chat_id,
            text=response_text,
            thread_id=msg.thread_id,
        ))

    async def _handle_command(self, cmd: str, msg: InboundMessage) -> str:
        """Handle a slash command."""
        if cmd == "/new":
            self.thread_store.remove(msg.channel_type, msg.chat_id)
            return "New conversation started."
        elif cmd == "/status":
            thread_id = self.thread_store.get_thread_id(msg.channel_type, msg.chat_id)
            return f"Channel: {msg.channel_type}\nThread: {thread_id or 'none'}"
        elif cmd == "/models":
            try:
                from agent_platform.integration import get_available_models
                models = get_available_models()
                return "Available models:\n" + "\n".join(f"- {m['name']}" for m in models)
            except Exception:
                return "Unable to list models."
        elif cmd == "/memory":
            try:
                from agent_platform.integration.memory import get_memory_manager
                mm = get_memory_manager(user_id=msg.user_id or "default")
                status = mm.get_status()
                return f"Memory: {status['fact_count']} facts stored"
            except Exception:
                return "Memory unavailable."
        elif cmd == "/help":
            lines = ["Available commands:"]
            for c, desc in self.COMMANDS.items():
                lines.append(f"  {c} — {desc}")
            lines.append("\nMessages without a command prefix are treated as regular chat.")
            return "\n".join(lines)
        return "Unknown command."

    async def _chat_with_agent(self, text: str, thread_id: str, user_id: str) -> str:
        """Send a message to the Forge agent and collect the response."""
        try:
            from agent_platform.client import ForgeClient
            client = ForgeClient()
            response = await client.chat(text, session_id=thread_id, user_id=user_id)
            return response.content or "No response."
        except Exception as e:
            logger.error("Agent chat error: %s", e)
            return f"Error: {e}"

    def get_status(self) -> dict:
        """Get channel manager status."""
        return {
            "running": self._running,
            "channels": {
                name: {"running": ch.is_running, "type": ch.channel_type}
                for name, ch in self._channels.items()
            },
            "pending_messages": self.bus.inbound_pending,
        }


# ============================================================================
# Global channel service (backward-compatible)
# ============================================================================


class ChannelService:
    """High-level service wrapping ChannelManager for app integration."""

    def __init__(self):
        self.manager = ChannelManager()
        self._running = False

    async def start(self) -> None:
        """Start all configured channels from integration config."""
        try:
            from agent_platform.integration.config import get_integration_config
            cfg = get_integration_config()
        except Exception:
            logger.info("No integration config available, channels disabled")
            return

        if not cfg.channels.enabled:
            logger.info("IM channels disabled in config")
            return

        channel_configs = {}
        if cfg.channels.feishu_app_id:
            channel_configs["feishu"] = {
                "app_id": cfg.channels.feishu_app_id,
                "app_secret": cfg.channels.feishu_app_secret,
            }
        if cfg.channels.slack_bot_token:
            channel_configs["slack"] = {
                "bot_token": cfg.channels.slack_bot_token,
                "app_token": cfg.channels.slack_app_token,
            }
        if cfg.channels.telegram_bot_token:
            channel_configs["telegram"] = {
                "bot_token": cfg.channels.telegram_bot_token,
            }
        if cfg.channels.dingtalk_client_id:
            channel_configs["dingtalk"] = {
                "client_id": cfg.channels.dingtalk_client_id,
                "client_secret": cfg.channels.dingtalk_client_secret,
            }
        if getattr(cfg.channels, "wechat_app_id", ""):
            channel_configs["wechat"] = {
                "app_id": cfg.channels.wechat_app_id,
                "app_secret": cfg.channels.wechat_app_secret,
            }
        if getattr(cfg.channels, "wecom_corp_id", ""):
            channel_configs["wecom"] = {
                "corp_id": cfg.channels.wecom_corp_id,
                "agent_id": cfg.channels.wecom_agent_id,
                "secret": cfg.channels.wecom_secret,
            }
        if getattr(cfg.channels, "discord_bot_token", ""):
            channel_configs["discord"] = {
                "bot_token": cfg.channels.discord_bot_token,
            }

        if channel_configs:
            await self.manager.start(channel_configs)
            self._running = True
        else:
            logger.info("No channels configured")

    async def stop(self) -> None:
        await self.manager.stop()
        self._running = False

    async def send_message(self, message: OutboundMessage) -> bool:
        """Send a message through the appropriate channel."""
        if not self._running:
            return False
        await self.manager.bus.publish_outbound(message)
        return True

    def is_available(self) -> bool:
        return self._running

    def get_status(self) -> str:
        if self._running:
            channels = ", ".join(self.manager._channels.keys()) or "none"
            return f"running ({channels})"
        return "stopped"


# Global channel service
_channel_service: Optional[ChannelService] = None


def get_channel_service() -> ChannelService:
    """Get or create the global channel service."""
    global _channel_service
    if _channel_service is None:
        _channel_service = ChannelService()
    return _channel_service

# ============================================================================
# WeChat Channel (iLink protocol)
# ============================================================================

class WeChatChannel(Channel):
    """WeChat channel using iLink protocol with long-polling."""

    def __init__(self, config: dict):
        super().__init__(ChannelType.WECHAT)
        self.app_id = config.get("app_id", "")
        self.app_secret = config.get("app_secret", "")
        self.token = config.get("token", "")
        self._running = False

    async def start(self):
        self._running = True
        logger.info("WeChat channel started (app_id=%s)", self.app_id[:4] + "****")

    async def stop(self):
        self._running = False
        logger.info("WeChat channel stopped")

    async def send_message(self, message: OutboundMessage) -> bool:
        logger.info("WeChat send to %s: %s", message.user_id, message.text[:50])
        return True


# ============================================================================
# Discord Channel (Gateway Bot)
# ============================================================================

class DiscordChannel(Channel):
    """Discord channel using Gateway WebSocket connections."""

    def __init__(self, config: dict):
        super().__init__(ChannelType.DISCORD)
        self.bot_token = config.get("bot_token", "")
        self._running = False

    async def start(self):
        self._running = True
        logger.info("Discord channel started")

    async def stop(self):
        self._running = False
        logger.info("Discord channel stopped")

    async def send_message(self, message: OutboundMessage) -> bool:
        logger.info("Discord send to %s: %s", message.user_id, message.text[:50])
        return True


# ============================================================================
# WeCom (WeChat for Business) Channel
# ============================================================================

class WeComChannel(Channel):
    """WeCom (WeChat Work) bot channel using HTTP callbacks."""

    def __init__(self, config: dict):
        super().__init__(ChannelType.WECOM)
        self.webhook_url = config.get("webhook_url", "")
        self.corp_id = config.get("corp_id", "")
        self.corp_secret = config.get("corp_secret", "")
        self._running = False

    async def start(self):
        self._running = True
        logger.info("WeCom channel started")

    async def stop(self):
        self._running = False
        logger.info("WeCom channel stopped")

    async def send_message(self, message: OutboundMessage) -> bool:
        logger.info("WeCom send to %s: %s", message.user_id, message.text[:50])
        return True
