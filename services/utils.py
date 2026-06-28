"""
services/utils.py — Shared utility helpers used across services.
"""
from __future__ import annotations

import re
import time
from datetime import datetime, timezone
from functools import wraps
from typing import Any, Callable, TypeVar

from services.logger import logger

F = TypeVar("F", bound=Callable[..., Any])


# ── Retry decorator ────────────────────────────────────────────────────────

def retry(
    max_attempts: int = 3,
    delay: float = 2.0,
    backoff: float = 2.0,
    exceptions: tuple[type[Exception], ...] = (Exception,),
) -> Callable[[F], F]:
    """Retry decorator with exponential backoff."""
    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            wait = delay
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:
                    if attempt == max_attempts:
                        logger.error(
                            "{} failed after {} attempts: {}",
                            func.__name__, max_attempts, exc
                        )
                        raise
                    logger.warning(
                        "{} attempt {}/{} failed: {}. Retrying in {:.1f}s…",
                        func.__name__, attempt, max_attempts, exc, wait
                    )
                    time.sleep(wait)
                    wait *= backoff
        return wrapper  # type: ignore[return-value]
    return decorator


# ── Text helpers ───────────────────────────────────────────────────────────

def truncate(text: str, max_len: int, suffix: str = "…") -> str:
    """Truncate text to max_len characters, appending suffix if cut."""
    if len(text) <= max_len:
        return text
    return text[: max_len - len(suffix)] + suffix


def clean_text(text: str) -> str:
    """Strip HTML tags, collapse whitespace."""
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def slugify(text: str) -> str:
    """Convert text to a URL-safe slug."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text.strip("-")


def format_number(n: int | float) -> str:
    """Format large numbers: 12300 → '12.3k'."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}k"
    return str(int(n))


def days_ago(dt: datetime | str) -> int:
    """Return how many days ago a datetime was."""
    if isinstance(dt, str):
        dt = datetime.fromisoformat(dt.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    delta = datetime.now(timezone.utc) - dt
    return delta.days


def stars_tier(stars: int) -> str:
    """Human-readable star tier label."""
    if stars >= 50_000:
        return "🌟 Legendary"
    if stars >= 10_000:
        return "⭐ Popular"
    if stars >= 1_000:
        return "✨ Rising"
    return "🔭 Emerging"


# ── Markdown helpers ───────────────────────────────────────────────────────

_MDCHARS = re.compile(r"([_*\[\]()~`>#+\-=|{}.!\\])")

def escape_markdown_v2(text: str) -> str:
    """Escape all MarkdownV2 special characters."""
    return _MDCHARS.sub(r"\\\1", str(text))


def split_message(text: str, limit: int = 4000) -> list[str]:
    """
    Split a long string into chunks ≤ limit characters,
    breaking on paragraph boundaries where possible.
    """
    if len(text) <= limit:
        return [text]

    chunks: list[str] = []
    paragraphs = text.split("\n\n")
    current = ""

    for para in paragraphs:
        candidate = f"{current}\n\n{para}" if current else para
        if len(candidate) <= limit:
            current = candidate
        else:
            if current:
                chunks.append(current.strip())
            # If a single paragraph exceeds limit, hard-split
            while len(para) > limit:
                chunks.append(para[:limit])
                para = para[limit:]
            current = para

    if current.strip():
        chunks.append(current.strip())

    return chunks


# ── Date helpers ───────────────────────────────────────────────────────────

def friendly_date(dt: datetime | str | None) -> str:
    if dt is None:
        return "Unknown"
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt.replace("Z", "+00:00"))
        except ValueError:
            return dt
    return dt.strftime("%b %d, %Y")


# ── Language colour map (for image generator) ──────────────────────────────

LANGUAGE_COLORS: dict[str, str] = {
    "Python": "#3572A5",
    "JavaScript": "#f1e05a",
    "TypeScript": "#2b7489",
    "Go": "#00ADD8",
    "Rust": "#dea584",
    "Java": "#b07219",
    "C++": "#f34b7d",
    "C": "#555555",
    "C#": "#178600",
    "Ruby": "#701516",
    "PHP": "#4F5D95",
    "Swift": "#ffac45",
    "Kotlin": "#F18E33",
    "Scala": "#c22d40",
    "Shell": "#89e051",
    "Dockerfile": "#384d54",
    "HTML": "#e34c26",
    "CSS": "#563d7c",
    "Jupyter Notebook": "#DA5B0B",
    "Lua": "#000080",
    "Dart": "#00B4AB",
    "Elixir": "#6e4a7e",
    "Haskell": "#5e5086",
    "R": "#198CE7",
    "MATLAB": "#e16737",
}

def get_language_color(language: str | None) -> str:
    return LANGUAGE_COLORS.get(language or "", "#58a6ff")
