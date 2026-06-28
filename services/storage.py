"""
services/storage.py — Persistent JSON-based history & cache management.

Tracks every repository that has already been posted so we never duplicate.
"""
from __future__ import annotations

import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import orjson

from services.logger import logger


class Storage:
    """Thread-safe JSON storage for sent-repository history and repo cache."""

    def __init__(self, data_dir: str = "data") -> None:
        self._dir = Path(data_dir)
        self._dir.mkdir(parents=True, exist_ok=True)

        self._history_path = self._dir / "sent_repositories.json"
        self._cache_path = self._dir / "repository_cache.json"
        self._lock = threading.Lock()

        self._ensure_files()

    # ── Private helpers ────────────────────────────────────────────────────

    def _ensure_files(self) -> None:
        if not self._history_path.exists():
            self._history_path.write_bytes(orjson.dumps([]))
        if not self._cache_path.exists():
            self._cache_path.write_bytes(orjson.dumps({}))

    def _read_json(self, path: Path) -> Any:
        try:
            return orjson.loads(path.read_bytes())
        except (orjson.JSONDecodeError, FileNotFoundError) as exc:
            logger.warning("Corrupt/missing {}: {} — resetting", path.name, exc)
            return [] if "sent" in path.name else {}

    def _write_json(self, path: Path, data: Any) -> None:
        tmp = path.with_suffix(".tmp")
        tmp.write_bytes(orjson.dumps(data, option=orjson.OPT_INDENT_2))
        tmp.replace(path)

    # ── History ────────────────────────────────────────────────────────────

    def get_sent_repos(self) -> list[dict[str, Any]]:
        with self._lock:
            return self._read_json(self._history_path)

    def get_sent_repo_urls(self) -> set[str]:
        """Return a set of full_name strings already posted."""
        return {r.get("full_name", "") for r in self.get_sent_repos()}

    def mark_as_sent(self, repo_full_name: str, repo_url: str, metadata: dict[str, Any] | None = None) -> None:
        """Persist a repo as sent so it is never picked again."""
        with self._lock:
            history: list[dict[str, Any]] = self._read_json(self._history_path)
            entry: dict[str, Any] = {
                "full_name": repo_full_name,
                "url": repo_url,
                "posted_at": datetime.now(timezone.utc).isoformat(),
            }
            if metadata:
                entry.update(metadata)
            history.append(entry)
            self._write_json(self._history_path, history)
        logger.info("Marked as sent: {}", repo_full_name)

    def is_already_sent(self, repo_full_name: str) -> bool:
        return repo_full_name in self.get_sent_repo_urls()

    def total_sent(self) -> int:
        return len(self.get_sent_repos())

    # ── Cache ──────────────────────────────────────────────────────────────

    def get_cache(self) -> dict[str, Any]:
        with self._lock:
            return self._read_json(self._cache_path)

    def set_cache(self, key: str, value: Any) -> None:
        with self._lock:
            cache = self._read_json(self._cache_path)
            cache[key] = value
            self._write_json(self._cache_path, cache)

    def get_cached(self, key: str) -> Any | None:
        return self.get_cache().get(key)

    def clear_cache(self) -> None:
        with self._lock:
            self._write_json(self._cache_path, {})
        logger.info("Cache cleared")

    # ── Analytics ──────────────────────────────────────────────────────────

    def get_history_summary(self) -> dict[str, Any]:
        history = self.get_sent_repos()
        return {
            "total_sent": len(history),
            "last_posted": history[-1] if history else None,
            "languages": _count_field(history, "language"),
            "topics": _count_field_list(history, "topics"),
        }


# ── Helpers ────────────────────────────────────────────────────────────────

def _count_field(records: list[dict[str, Any]], field: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for r in records:
        val = r.get(field)
        if val:
            counts[val] = counts.get(val, 0) + 1
    return dict(sorted(counts.items(), key=lambda x: -x[1]))


def _count_field_list(records: list[dict[str, Any]], field: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for r in records:
        for item in r.get(field, []):
            counts[item] = counts.get(item, 0) + 1
    return dict(sorted(counts.items(), key=lambda x: -x[1])[:20])
