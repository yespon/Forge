"""Uploads module — File upload management with document conversion.

Provides:
- Safe file storage with symlink protection
- PDF/Office/HTML → Markdown automatic conversion
- Thread-scoped file organization
- Upload injection into conversation context
"""

from agent_platform.harness.uploads.manager import UploadManager

__all__ = ["UploadManager"]
