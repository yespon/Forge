"""Memory system adapted from DeerFlow for Forge.

Provides conversation memory with:
- Per-user isolated fact storage
- Keyword-based retrieval with scoring
- Debounced background update queue
- Deduplication on store
"""

import json
import logging
import os
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

DEFAULT_STORAGE_DIR = ".forge/memory"


@dataclass
class MemoryFact:
    """A stored memory fact."""
    content: str
    category: str = "general"  # general, preference, knowledge, context, behavior, goal
    confidence: float = 1.0
    timestamp: float = field(default_factory=time.time)
    source: str = "conversation"
    id: str = ""

    def __post_init__(self):
        if not self.id:
            import hashlib
            self.id = hashlib.sha256(self.content.encode()).hexdigest()[:12]


class MemoryStore:
    """Persistent per-user storage for memory facts."""

    def __init__(self, storage_path: str, user_id: str = "default"):
        self.base_path = storage_path
        self.user_id = user_id
        self._facts: list[MemoryFact] = []
        self._user_context: dict[str, str] = {}
        self._lock = threading.Lock()
        self._load()

    @property
    def _file_path(self) -> Path:
        return Path(self.base_path) / self.user_id / "memory.json"

    def _load(self) -> None:
        """Load facts from disk."""
        path = self._file_path
        if path.exists():
            try:
                data = json.loads(path.read_text())
                self._facts = [MemoryFact(**f) for f in data.get("facts", [])]
                self._user_context = data.get("user_context", {})
                logger.info("Loaded %d memory facts for user %s", len(self._facts), self.user_id)
            except Exception as e:
                logger.warning("Failed to load memory for %s: %s", self.user_id, e)

    def _save(self) -> None:
        """Save facts to disk atomically (temp file + rename)."""
        path = self._file_path
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "version": 2,
                "user_id": self.user_id,
                "user_context": self._user_context,
                "facts": [
                    {
                        "id": f.id,
                        "content": f.content,
                        "category": f.category,
                        "confidence": f.confidence,
                        "timestamp": f.timestamp,
                        "source": f.source,
                    }
                    for f in self._facts
                ],
            }
            tmp_path = path.with_suffix(".tmp")
            tmp_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
            tmp_path.rename(path)
        except Exception as e:
            logger.warning("Failed to save memory for %s: %s", self.user_id, e)

    def add_fact(self, fact: MemoryFact) -> bool:
        """Add or update a memory fact. Returns True if new fact added."""
        with self._lock:
            # Deduplicate by normalized content
            normalized = fact.content.strip().lower()
            for i, existing in enumerate(self._facts):
                if existing.content.strip().lower() == normalized:
                    if fact.confidence > existing.confidence:
                        self._facts[i] = fact
                        self._save()
                    return False
            self._facts.append(fact)
            self._save()
            return True

    def update_user_context(self, key: str, value: str) -> None:
        """Update a user context field (workContext, personalContext, etc.)."""
        with self._lock:
            self._user_context[key] = value
            self._save()

    def get_relevant_facts(self, query: str, max_facts: int = 15) -> list[MemoryFact]:
        """Get relevant facts based on keyword scoring."""
        if not query:
            # No query: return most recent facts
            return sorted(self._facts, key=lambda f: f.timestamp, reverse=True)[:max_facts]

        query_lower = query.lower()
        keywords = set(w for w in query_lower.split() if len(w) > 2)

        scored: list[tuple[float, MemoryFact]] = []
        for fact in self._facts:
            fact_lower = fact.content.lower()
            # Keyword match score
            kw_score = sum(1 for kw in keywords if kw in fact_lower)
            # Recency boost (last 24h = +1, last week = +0.5)
            age_hours = (time.time() - fact.timestamp) / 3600
            recency = 1.0 if age_hours < 24 else (0.5 if age_hours < 168 else 0.0)
            # Confidence weight
            score = (kw_score * 2 + recency) * fact.confidence
            if score > 0:
                scored.append((score, fact))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [fact for _, fact in scored[:max_facts]]

    def get_all_facts(self) -> list[MemoryFact]:
        return list(self._facts)

    @property
    def fact_count(self) -> int:
        return len(self._facts)

    def clear(self) -> None:
        with self._lock:
            self._facts = []
            self._user_context = {}
            self._save()


class MemoryQueue:
    """Queue for processing memory updates with debouncing."""

    def __init__(self, store: MemoryStore, debounce_seconds: int = 30):
        self.store = store
        self.debounce_seconds = debounce_seconds
        self._pending: list[dict] = []
        self._last_flush = 0.0
        self._timer: Optional[threading.Timer] = None
        self._lock = threading.Lock()

    def enqueue(self, messages: list[dict], user_id: str = "default") -> None:
        """Add messages to the update queue. Debounces flushes."""
        with self._lock:
            self._pending.append({
                "messages": messages,
                "user_id": user_id,
                "timestamp": time.time(),
            })

            # Cancel existing timer and start a new one
            if self._timer:
                self._timer.cancel()
            self._timer = threading.Timer(self.debounce_seconds, self._flush_sync)
            self._timer.daemon = True
            self._timer.start()

    def _flush_sync(self) -> None:
        """Synchronous flush called by timer thread."""
        with self._lock:
            if not self._pending:
                return
            batches = list(self._pending)
            self._pending = []
            self._last_flush = time.time()

        for batch in batches:
            self._extract_facts(batch["messages"])

    def _extract_facts(self, messages: list[dict]) -> None:
        """Extract facts from conversation messages."""
        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if not content or len(content) < 20:
                continue

            if role == "user":
                # User statements often contain preferences / context
                for indicator in ["I prefer", "I always", "I usually", "My ", "I work",
                                  "I like", "I use", "I need", "I want", "Remember that"]:
                    if indicator.lower() in content.lower():
                        fact_text = content[:300].strip()
                        self.store.add_fact(MemoryFact(
                            content=fact_text,
                            category="preference" if "prefer" in content.lower() else "context",
                            confidence=0.7,
                            source="user_statement",
                        ))
                        break

    async def flush(self) -> list[MemoryFact]:
        """Explicit async flush for testing."""
        self._flush_sync()
        return []


class MemoryManager:
    """Manages the full memory lifecycle with per-user isolation."""

    def __init__(
        self,
        storage_path: str = DEFAULT_STORAGE_DIR,
        debounce_seconds: int = 30,
        max_facts: int = 100,
        injection_enabled: bool = True,
        max_injection_tokens: int = 2000,
        user_id: str = "default",
    ):
        self.storage_path = storage_path
        self.max_facts = max_facts
        self.injection_enabled = injection_enabled
        self.max_injection_tokens = max_injection_tokens
        self.user_id = user_id
        self.store = MemoryStore(storage_path, user_id=user_id)
        self.queue = MemoryQueue(self.store, debounce_seconds)

    def get_memory_context(self, query: str = "") -> str:
        """Get memory context to inject into system prompt."""
        if not self.injection_enabled:
            return ""

        facts = self.store.get_relevant_facts(query, max_facts=15)
        user_ctx = self.store._user_context

        if not facts and not user_ctx:
            return ""

        parts = ["<memory>"]

        # User context summary
        if user_ctx:
            for key, value in user_ctx.items():
                if value:
                    parts.append(f"  <{key}>{value}</{key}>")

        # Facts
        if facts:
            parts.append("  <facts>")
            token_budget = self.max_injection_tokens
            for fact in facts:
                line = f"    - [{fact.category}] {fact.content}"
                tokens = len(line) // 4
                if token_budget - tokens < 0:
                    break
                token_budget -= tokens
                parts.append(line)
            parts.append("  </facts>")

        parts.append("</memory>")
        return "\n".join(parts)

    def store_fact(self, content: str, category: str = "general", confidence: float = 1.0) -> bool:
        """Store a new memory fact, enforcing max_facts limit."""
        if self.store.fact_count >= self.max_facts:
            # Remove lowest-confidence fact
            all_facts = self.store.get_all_facts()
            if all_facts:
                weakest = min(all_facts, key=lambda f: (f.confidence, f.timestamp))
                self.store._facts.remove(weakest)

        fact = MemoryFact(content=content, category=category, confidence=confidence)
        return self.store.add_fact(fact)

    async def process_conversation(self, messages: list[dict]) -> None:
        """Process conversation messages for memory extraction."""
        self.queue.enqueue(messages, user_id=self.user_id)

    def get_status(self) -> dict:
        """Get memory system status."""
        return {
            "user_id": self.user_id,
            "fact_count": self.store.fact_count,
            "injection_enabled": self.injection_enabled,
            "max_facts": self.max_facts,
            "storage_path": str(self.store._file_path),
        }


# Per-user memory manager cache
_memory_managers: dict[str, MemoryManager] = {}


def get_memory_manager(
    storage_path: str = DEFAULT_STORAGE_DIR,
    debounce_seconds: int = 30,
    user_id: str = "default",
) -> MemoryManager:
    """Get or create a memory manager for a specific user."""
    key = f"{user_id}:{storage_path}"
    if key not in _memory_managers:
        _memory_managers[key] = MemoryManager(
            storage_path=storage_path,
            debounce_seconds=debounce_seconds,
            user_id=user_id,
        )
    return _memory_managers[key]