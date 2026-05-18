"""Upload manager — safe file storage with document conversion.

Handles file uploads with:
- Symlink attack protection (realpath validation)
- Thread-scoped directory isolation
- Automatic document conversion (PDF/DOCX/PPTX/XLSX → Markdown)
- Duplicate filename handling
"""

from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path
from typing import Optional

import structlog

logger = structlog.get_logger(__name__)

# Supported document types for conversion
CONVERTIBLE_EXTENSIONS = {
    ".pdf",
    ".docx",
    ".doc",
    ".pptx",
    ".ppt",
    ".xlsx",
    ".xls",
    ".html",
    ".htm",
    ".epub",
    ".rtf",
}

# Max file size (50MB)
MAX_FILE_SIZE = 50 * 1024 * 1024

# Dangerous filename patterns
DANGEROUS_PATTERNS = re.compile(r"[<>:\"|?*\x00-\x1f]")


class UploadManager:
    """Manages file uploads with safety and conversion capabilities."""

    def __init__(self, base_dir: Optional[str] = None):
        self._base_dir = Path(base_dir or os.environ.get("UPLOAD_DIR", ".forge/uploads"))
        self._base_dir.mkdir(parents=True, exist_ok=True)

    def _thread_dir(self, thread_id: str) -> Path:
        """Get the upload directory for a thread."""
        safe_id = re.sub(r"[^a-zA-Z0-9_-]", "", thread_id)
        thread_dir = self._base_dir / safe_id
        thread_dir.mkdir(parents=True, exist_ok=True)
        return thread_dir

    def _safe_filename(self, filename: str) -> str:
        """Sanitize filename to prevent path traversal and special chars."""
        # Strip path components
        filename = Path(filename).name
        # Remove dangerous characters
        filename = DANGEROUS_PATTERNS.sub("_", filename)
        # Prevent dotfile creation
        if filename.startswith("."):
            filename = "_" + filename
        # Limit length
        if len(filename) > 255:
            stem = Path(filename).stem[:200]
            suffix = Path(filename).suffix
            filename = stem + suffix
        return filename or "unnamed"

    def _deduplicate_filename(self, directory: Path, filename: str) -> str:
        """Add numeric suffix if file already exists."""
        target = directory / filename
        if not target.exists():
            return filename

        stem = Path(filename).stem
        suffix = Path(filename).suffix
        counter = 1
        while (directory / f"{stem}_{counter}{suffix}").exists():
            counter += 1
        return f"{stem}_{counter}{suffix}"

    def _validate_path(self, path: Path, base: Path) -> bool:
        """Validate that resolved path is within the base directory (symlink protection)."""
        try:
            resolved = path.resolve(strict=False)
            base_resolved = base.resolve(strict=False)
            return str(resolved).startswith(str(base_resolved))
        except (OSError, ValueError):
            return False

    async def save_file(
        self,
        thread_id: str,
        filename: str,
        content: bytes,
        *,
        convert: bool = True,
    ) -> dict:
        """Save an uploaded file to thread-scoped storage.

        Args:
            thread_id: Thread/session identifier for directory scoping.
            filename: Original filename.
            content: File bytes.
            convert: Whether to attempt document → Markdown conversion.

        Returns:
            Dict with file_path, markdown_path (if converted), and metadata.
        """
        if len(content) > MAX_FILE_SIZE:
            raise ValueError(f"File too large: {len(content)} bytes (max {MAX_FILE_SIZE})")

        thread_dir = self._thread_dir(thread_id)
        safe_name = self._safe_filename(filename)
        safe_name = self._deduplicate_filename(thread_dir, safe_name)

        target_path = thread_dir / safe_name
        if not self._validate_path(target_path, self._base_dir):
            raise ValueError("Invalid file path (potential path traversal)")

        # Write file
        target_path.write_bytes(content)
        logger.info("file_uploaded", thread_id=thread_id, filename=safe_name, size=len(content))

        result = {
            "file_path": str(target_path),
            "filename": safe_name,
            "size": len(content),
            "content_hash": hashlib.sha256(content).hexdigest()[:16],
        }

        # Attempt document conversion
        suffix = Path(safe_name).suffix.lower()
        if convert and suffix in CONVERTIBLE_EXTENSIONS:
            markdown = await self._convert_to_markdown(target_path, suffix)
            if markdown:
                md_path = target_path.with_suffix(".md")
                md_path.write_text(markdown, encoding="utf-8")
                result["markdown_path"] = str(md_path)
                result["converted"] = True
                logger.info("file_converted", filename=safe_name, md_path=str(md_path))

        return result

    async def _convert_to_markdown(self, file_path: Path, suffix: str) -> Optional[str]:
        """Convert a document to Markdown using markitdown or fallback."""
        try:
            from markitdown import MarkItDown

            md = MarkItDown()
            result = md.convert(str(file_path))
            return result.text_content if result else None
        except ImportError:
            logger.debug("markitdown_not_available", hint="pip install markitdown")
            return None
        except Exception as e:
            logger.warning("conversion_failed", file=str(file_path), error=str(e))
            return None

    async def list_files(self, thread_id: str) -> list[dict]:
        """List uploaded files for a thread."""
        thread_dir = self._thread_dir(thread_id)
        files = []
        for f in sorted(thread_dir.iterdir()):
            if f.is_file() and not f.name.startswith("."):
                files.append({
                    "filename": f.name,
                    "path": str(f),
                    "size": f.stat().st_size,
                    "suffix": f.suffix,
                })
        return files

    async def get_file_content(self, thread_id: str, filename: str) -> Optional[bytes]:
        """Read a file's content."""
        thread_dir = self._thread_dir(thread_id)
        safe_name = self._safe_filename(filename)
        target = thread_dir / safe_name

        if not self._validate_path(target, self._base_dir):
            return None
        if not target.exists():
            return None
        return target.read_bytes()

    async def delete_file(self, thread_id: str, filename: str) -> bool:
        """Delete an uploaded file."""
        thread_dir = self._thread_dir(thread_id)
        safe_name = self._safe_filename(filename)
        target = thread_dir / safe_name

        if not self._validate_path(target, self._base_dir):
            return False
        if target.exists():
            target.unlink()
            # Also remove converted markdown if exists
            md_path = target.with_suffix(".md")
            if md_path.exists():
                md_path.unlink()
            return True
        return False
