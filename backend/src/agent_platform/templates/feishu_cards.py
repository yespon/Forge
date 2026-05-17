"""Feishu (Lark) interactive card templates.

Provides builders for creating rich interactive cards for notifications,
including approval requests, task status updates, and system alerts.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from agent_platform.models.approval import ApprovalStatus, RiskLevel


class CardColor(str, Enum):
    """Card header color templates."""

    RED = "red"          # High risk, errors, rejections
    ORANGE = "orange"    # Medium risk, warnings
    YELLOW = "yellow"    # Low risk, cautions
    GREEN = "green"      # Success, approvals
    BLUE = "blue"        # Info, neutral
    INDIGO = "indigo"    # System messages
    GREY = "grey"        # Default


class CardTemplate:
    """Card template utilities."""

    @staticmethod
    def risk_to_color(risk_level: RiskLevel) -> CardColor:
        """Map risk level to card color.

        Args:
            risk_level: Risk level enum

        Returns:
            Appropriate card color
        """
        mapping = {
            RiskLevel.CRITICAL: CardColor.RED,
            RiskLevel.HIGH: CardColor.ORANGE,
            RiskLevel.MEDIUM: CardColor.BLUE,
            RiskLevel.LOW: CardColor.GREEN,
        }
        return mapping.get(risk_level, CardColor.BLUE)

    @staticmethod
    def risk_to_emoji(risk_level: RiskLevel) -> str:
        """Get emoji for risk level.

        Args:
            risk_level: Risk level enum

        Returns:
            Emoji string
        """
        mapping = {
            RiskLevel.CRITICAL: "🚨",
            RiskLevel.HIGH: "⚠️",
            RiskLevel.MEDIUM: "ℹ️",
            RiskLevel.LOW: "✓",
        }
        return mapping.get(risk_level, "ℹ️")

    @staticmethod
    def status_to_color(status: ApprovalStatus) -> CardColor:
        """Map approval status to card color.

        Args:
            status: Approval status

        Returns:
            Appropriate card color
        """
        mapping = {
            ApprovalStatus.APPROVED: CardColor.GREEN,
            ApprovalStatus.REJECTED: CardColor.RED,
            ApprovalStatus.PENDING: CardColor.BLUE,
            ApprovalStatus.EXPIRED: CardColor.GREY,
            ApprovalStatus.ESCALATED: CardColor.ORANGE,
            ApprovalStatus.CANCELLED: CardColor.GREY,
        }
        return mapping.get(status, CardColor.BLUE)


@dataclass
class ActionButton:
    """Action button configuration."""

    text: str
    action_type: str
    value: dict[str, Any]
    button_type: str = "default"  # primary, danger, default
    confirm: Optional[dict] = None


class ApprovalCardBuilder:
    """Builder for approval-related interactive cards."""

    @classmethod
    def build_approval_request_card(
        cls,
        approval_id: str,
        tool_name: str,
        tool_input: dict[str, Any],
        risk_level: RiskLevel,
        description: Optional[str] = None,
        context_summary: Optional[str] = None,
        approver_name: Optional[str] = None,
        expires_at: Optional[datetime] = None,
    ) -> dict[str, Any]:
        """Build approval request card.

        Args:
            approval_id: Approval request ID
            tool_name: Name of the tool being called
            tool_input: Tool input arguments
            risk_level: Risk level of the operation
            description: Optional description
            context_summary: Optional context summary
            approver_name: Name of the approver
            expires_at: Expiration datetime

        Returns:
            Card payload for Feishu
        """
        color = CardTemplate.risk_to_color(risk_level)
        emoji = CardTemplate.risk_to_emoji(risk_level)

        elements: list[dict] = []

        # Risk level indicator
        elements.append({
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": f"{emoji} **风险等级**: {cls._risk_to_text(risk_level)}",
            },
        })

        # Tool information
        elements.append({
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": f"**工具**: `{tool_name}`",
            },
        })

        # Tool input (formatted as code block if small, otherwise summary)
        tool_input_str = cls._format_tool_input(tool_input)
        elements.append({
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": f"**输入参数**:\n```\n{tool_input_str[:500]}\n```",
            },
        })

        # Description if provided
        if description:
            elements.append({
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**说明**: {description}",
                },
            })

        # Context summary if provided
        if context_summary:
            elements.append({
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**上下文**: {context_summary}",
                },
            })

        # Expiration info
        if expires_at:
            expires_str = expires_at.strftime("%Y-%m-%d %H:%M:%S")
            elements.append({
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"⏰ **过期时间**: {expires_str}",
                },
            })

        # Divider
        elements.append({"tag": "hr"})

        # Action buttons
        actions = [
            {
                "tag": "button",
                "text": {
                    "tag": "plain_text",
                    "content": "✅ 通过",
                },
                "type": "primary",
                "value": {
                    "action": "approve",
                    "approval_id": approval_id,
                },
            },
            {
                "tag": "button",
                "text": {
                    "tag": "plain_text",
                    "content": "❌ 拒绝",
                },
                "type": "danger",
                "value": {
                    "action": "reject",
                    "approval_id": approval_id,
                },
            },
        ]

        elements.append({
            "tag": "action",
            "actions": actions,
        })

        # View details link
        elements.append({
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": f"[查看详情]({cls._build_approval_url(approval_id)})",
            },
        })

        return {
            "msg_type": "interactive",
            "card": {
                "config": {
                    "wide_screen_mode": True,
                    "enable_forward": True,
                },
                "header": {
                    "title": {
                        "tag": "plain_text",
                        "content": f"🤖 Agent 请求审批",
                    },
                    "template": color.value,
                },
                "elements": elements,
            },
        }

    @classmethod
    def build_task_completed_card(
        cls,
        task_id: str,
        task_name: str,
        result_summary: Optional[str] = None,
        duration: Optional[str] = None,
        output_preview: Optional[str] = None,
    ) -> dict[str, Any]:
        """Build task completed notification card.

        Args:
            task_id: Task ID
            task_name: Task name
            result_summary: Optional result summary
            duration: Optional task duration
            output_preview: Optional output preview

        Returns:
            Card payload for Feishu
        """
        elements: list[dict] = []

        # Task name
        elements.append({
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": f"**任务名称**: {task_name}",
            },
        })

        # Duration
        if duration:
            elements.append({
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"⏱️ **耗时**: {duration}",
                },
            })

        # Result summary
        if result_summary:
            elements.append({
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**执行结果**: {result_summary}",
                },
            })

        # Output preview
        if output_preview:
            elements.append({
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**输出预览**:\n```\n{output_preview[:500]}\n```",
                },
            })

        # Divider
        elements.append({"tag": "hr"})

        # View details link
        elements.append({
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": f"[查看详情]({cls._build_task_url(task_id)})",
            },
        })

        return {
            "msg_type": "interactive",
            "card": {
                "config": {
                    "wide_screen_mode": True,
                    "enable_forward": True,
                },
                "header": {
                    "title": {
                        "tag": "plain_text",
                        "content": "✅ 任务完成",
                    },
                    "template": "green",
                },
                "elements": elements,
            },
        }

    @classmethod
    def build_task_failed_card(
        cls,
        task_id: str,
        task_name: str,
        error_message: str,
        error_code: Optional[str] = None,
        retry_count: Optional[int] = None,
    ) -> dict[str, Any]:
        """Build task failed notification card.

        Args:
            task_id: Task ID
            task_name: Task name
            error_message: Error message
            error_code: Optional error code
            retry_count: Optional retry count

        Returns:
            Card payload for Feishu
        """
        elements: list[dict] = []

        # Task name
        elements.append({
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": f"**任务名称**: {task_name}",
            },
        })

        # Error code
        if error_code:
            elements.append({
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**错误代码**: `{error_code}`",
                },
            })

        # Error message
        elements.append({
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": f"**错误信息**:\n```\n{error_message[:1000]}\n```",
            },
        })

        # Retry count
        if retry_count is not None:
            elements.append({
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**重试次数**: {retry_count}",
                },
            })

        # Divider
        elements.append({"tag": "hr"})

        # Action buttons
        actions = [
            {
                "tag": "button",
                "text": {
                    "tag": "plain_text",
                    "content": "🔄 重试",
                },
                "type": "primary",
                "value": {
                    "action": "retry_task",
                    "task_id": task_id,
                },
            },
            {
                "tag": "button",
                "text": {
                    "tag": "plain_text",
                    "content": "查看详情",
                },
                "type": "default",
                "value": {
                    "action": "view_task",
                    "task_id": task_id,
                },
            },
        ]

        elements.append({
            "tag": "action",
            "actions": actions,
        })

        return {
            "msg_type": "interactive",
            "card": {
                "config": {
                    "wide_screen_mode": True,
                    "enable_forward": True,
                },
                "header": {
                    "title": {
                        "tag": "plain_text",
                        "content": "❌ 任务失败",
                    },
                    "template": "orange",
                },
                "elements": elements,
            },
        }

    @classmethod
    def build_approval_status_change_card(
        cls,
        approval_id: str,
        tool_name: str,
        status: ApprovalStatus,
        decided_by: Optional[str] = None,
        reason: Optional[str] = None,
        decided_at: Optional[datetime] = None,
    ) -> dict[str, Any]:
        """Build approval status change notification card.

        Args:
            approval_id: Approval request ID
            tool_name: Name of the tool
            status: New approval status
            decided_by: Who made the decision
            reason: Optional decision reason
            decided_at: When the decision was made

        Returns:
            Card payload for Feishu
        """
        color = CardTemplate.status_to_color(status)

        status_emoji = {
            ApprovalStatus.APPROVED: "✅",
            ApprovalStatus.REJECTED: "❌",
            ApprovalStatus.EXPIRED: "⏰",
            ApprovalStatus.ESCALATED: "⚠️",
            ApprovalStatus.CANCELLED: "🚫",
        }.get(status, "ℹ️")

        status_text = {
            ApprovalStatus.APPROVED: "已通过",
            ApprovalStatus.REJECTED: "已拒绝",
            ApprovalStatus.EXPIRED: "已过期",
            ApprovalStatus.ESCALATED: "已升级",
            ApprovalStatus.CANCELLED: "已取消",
        }.get(status, status.value)

        elements: list[dict] = []

        # Tool name
        elements.append({
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": f"**工具**: `{tool_name}`",
            },
        })

        # Decision info
        if decided_by:
            elements.append({
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**处理人**: {decided_by}",
                },
            })

        if decided_at:
            decided_str = decided_at.strftime("%Y-%m-%d %H:%M:%S")
            elements.append({
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**处理时间**: {decided_str}",
                },
            })

        # Reason
        if reason:
            elements.append({
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**原因**: {reason}",
                },
            })

        # Divider
        elements.append({"tag": "hr"})

        # View details link
        elements.append({
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": f"[查看详情]({cls._build_approval_url(approval_id)})",
            },
        })

        return {
            "msg_type": "interactive",
            "card": {
                "config": {
                    "wide_screen_mode": True,
                    "enable_forward": True,
                },
                "header": {
                    "title": {
                        "tag": "plain_text",
                        "content": f"{status_emoji} 审批{status_text}",
                    },
                    "template": color.value,
                },
                "elements": elements,
            },
        }

    @classmethod
    def build_system_alert_card(
        cls,
        alert_title: str,
        alert_message: str,
        severity: str = "info",  # info, warning, error, critical
        alert_id: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> dict[str, Any]:
        """Build system alert notification card.

        Args:
            alert_title: Alert title
            alert_message: Alert message
            severity: Alert severity level
            alert_id: Optional alert ID
            metadata: Optional metadata

        Returns:
            Card payload for Feishu
        """
        color_mapping = {
            "critical": CardColor.RED,
            "error": CardColor.ORANGE,
            "warning": CardColor.YELLOW,
            "info": CardColor.BLUE,
        }
        color = color_mapping.get(severity, CardColor.BLUE)

        emoji_mapping = {
            "critical": "🚨",
            "error": "❌",
            "warning": "⚠️",
            "info": "ℹ️",
        }
        emoji = emoji_mapping.get(severity, "ℹ️")

        elements: list[dict] = []

        # Alert message
        elements.append({
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": alert_message,
            },
        })

        # Metadata
        if metadata:
            metadata_str = "\n".join([f"**{k}**: {v}" for k, v in metadata.items()])
            elements.append({
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**详细信息**:\n{metadata_str}",
                },
            })

        # Divider
        elements.append({"tag": "hr"})

        # View details link if alert_id provided
        if alert_id:
            elements.append({
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"[查看详情]({cls._build_alert_url(alert_id)})",
                },
            })

        return {
            "msg_type": "interactive",
            "card": {
                "config": {
                    "wide_screen_mode": True,
                    "enable_forward": True,
                },
                "header": {
                    "title": {
                        "tag": "plain_text",
                        "content": f"{emoji} {alert_title}",
                    },
                    "template": color.value,
                },
                "elements": elements,
            },
        }

    @staticmethod
    def _risk_to_text(risk_level: RiskLevel) -> str:
        """Convert risk level to Chinese text.

        Args:
            risk_level: Risk level enum

        Returns:
            Chinese risk level text
        """
        mapping = {
            RiskLevel.CRITICAL: "严重 🔴",
            RiskLevel.HIGH: "高 🟠",
            RiskLevel.MEDIUM: "中 🟡",
            RiskLevel.LOW: "低 🟢",
        }
        return mapping.get(risk_level, "未知")

    @staticmethod
    def _format_tool_input(tool_input: dict[str, Any]) -> str:
        """Format tool input for display.

        Args:
            tool_input: Tool input dictionary

        Returns:
            Formatted string
        """
        import json

        try:
            return json.dumps(tool_input, ensure_ascii=False, indent=2)
        except (TypeError, ValueError):
            return str(tool_input)

    @staticmethod
    def _build_approval_url(approval_id: str) -> str:
        """Build approval detail URL.

        Args:
            approval_id: Approval ID

        Returns:
            URL string
        """
        # In production, this would be a real URL
        return f"/approvals/{approval_id}"

    @staticmethod
    def _build_task_url(task_id: str) -> str:
        """Build task detail URL.

        Args:
            task_id: Task ID

        Returns:
            URL string
        """
        return f"/tasks/{task_id}"

    @staticmethod
    def _build_alert_url(alert_id: str) -> str:
        """Build alert detail URL.

        Args:
            alert_id: Alert ID

        Returns:
            URL string
        """
        return f"/alerts/{alert_id}"


def create_simple_text_card(
    title: str,
    content: str,
    color: CardColor = CardColor.BLUE,
) -> dict[str, Any]:
    """Create a simple text card.

    Args:
        title: Card title
        content: Card content
        color: Header color

    Returns:
        Card payload
    """
    return {
        "msg_type": "interactive",
        "card": {
            "config": {
                "wide_screen_mode": True,
            },
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": title,
                },
                "template": color.value,
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": content,
                    },
                },
            ],
        },
    }


def create_note_card(
    title: str,
    note_content: str,
    author_name: Optional[str] = None,
    timestamp: Optional[datetime] = None,
) -> dict[str, Any]:
    """Create a note/info card.

    Args:
        title: Card title
        note_content: Note content
        author_name: Optional author name
        timestamp: Optional timestamp

    Returns:
        Card payload
    """
    elements: list[dict] = []

    # Note content
    elements.append({
        "tag": "div",
        "text": {
            "tag": "lark_md",
            "content": note_content,
        },
    })

    # Author info
    if author_name or timestamp:
        info_parts = []
        if author_name:
            info_parts.append(f"**发送人**: {author_name}")
        if timestamp:
            info_parts.append(f"**时间**: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}")

        elements.append({"tag": "hr"})
        elements.append({
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": " | ".join(info_parts),
            },
        })

    return {
        "msg_type": "interactive",
        "card": {
            "config": {
                "wide_screen_mode": True,
            },
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": f"📝 {title}",
                },
                "template": "blue",
            },
            "elements": elements,
        },
    }
