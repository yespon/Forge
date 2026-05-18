"""Web fetch tool adapted from DeerFlow for Forge."""

import logging
from typing import Optional

import httpx
from langchain_core.tools import tool

logger = logging.getLogger(__name__)


@tool
async def web_fetch_tool(url: str, timeout: int = 10) -> str:
    """Fetch and extract text content from a web page.

    Args:
        url: The URL to fetch
        timeout: Request timeout in seconds (default: 10)

    Returns:
        Page content as text
    """
    logger.info(f"Web fetch: '{url}' (timeout={timeout}s)")

    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()

        content_type = response.headers.get("content-type", "")
        text = response.text

        if "text/html" in content_type or "application/xhtml" in content_type:
            try:
                from markdownify import markdownify
                text = markdownify(text, heading_style="ATX")
            except ImportError:
                pass

        max_chars = 50000
        if len(text) > max_chars:
            text = text[:max_chars] + f"\n\n[... truncated to {max_chars} characters ...]"

        return f"Content from {url}:\n\n{text}"

    except httpx.TimeoutException:
        return f"Error: Request timed out after {timeout} seconds"
    except httpx.HTTPStatusError as e:
        return f"Error: HTTP {e.response.status_code} {e.response.reason_phrase}"
    except httpx.RequestError as e:
        return f"Error: Request failed - {e}"
    except Exception as e:
        return f"Error fetching URL: {e}"