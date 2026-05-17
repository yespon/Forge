"""Web search tools adapted from DeerFlow for Forge.

Provides web search and web fetch capabilities using DuckDuckGo.
"""

import logging
from typing import Optional

from langchain_core.tools import tool

logger = logging.getLogger(__name__)


@tool
async def web_search_tool(query: str, max_results: int = 5) -> str:
    """Search the web for information.

    Args:
        query: The search query
        max_results: Maximum number of results to return (default: 5, max: 20)

    Returns:
        Search results as formatted text
    """
    actual_max = min(max_results, 20)
    if actual_max < 1:
        actual_max = 1

    logger.info(f"Web search: '{query}' (max_results={actual_max})")

    try:
        from ddgs import DuckDuckGoSearch

        ddgs = DuckDuckGoSearch()
        results = []
        for i, r in enumerate(ddgs.text(query)):
            if i >= actual_max:
                break
            title = r.get("title", "")
            body = r.get("body", "")
            href = r.get("href", "")
            results.append(f"### {i+1}. {title}\n{body}\nURL: {href}\n")

        if not results:
            return f"No results found for: {query}"

        return f"Search results for '{query}':\n\n" + "\n".join(results)
    except ImportError:
        return "Web search is unavailable: duckduckgo-search package not installed"
    except Exception as e:
        logger.warning(f"Web search failed: {e}")
        return f"Search failed: {e}"


@tool
async def web_fetch_tool(url: str, timeout: int = 10) -> str:
    """Fetch and extract text content from a web page.

    Args:
        url: The URL to fetch
        timeout: Request timeout in seconds (default: 10)

    Returns:
        Page content as text
    """
    import httpx

    logger.info(f"Web fetch: '{url}' (timeout={timeout}s)")

    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()

        content_type = response.headers.get("content-type", "")
        text = response.text

        if "text/html" in content_type or "application/xhtml" in content_type:
            # Try to extract text from HTML
            try:
                from markdownify import markdownify
                text = markdownify(text, heading_style="ATX")
            except ImportError:
                pass

        # Truncate to reasonable length
        max_chars = 50000
        if len(text) > max_chars:
            text = text[:max_chars] + f"\n\n[... truncated to {max_chars} characters ...]"

        return f"Content from {url}:\n\n{text}"

    except httpx.TimeoutException:
        return f"Error: Request timed out after {timeout} seconds"
    except httpx.HTTPStatusError as e:
        return f"Error: HTTP {e.response.status_code} - {e.response.reason_phrase}"
    except httpx.RequestError as e:
        return f"Error: Request failed - {e}"
    except Exception as e:
        return f"Error fetching URL: {e}"