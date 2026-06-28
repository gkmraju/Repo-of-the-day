"""
services/markdown_formatter.py — Render AnalyzedRepo into a Telegram MarkdownV2 message.

Telegram MarkdownV2 requires escaping of: _ * [ ] ( ) ~ ` > # + - = | { } . !
"""
from __future__ import annotations

import re
from typing import TYPE_CHECKING

from services.logger import logger
from services.utils import format_number, split_message

if TYPE_CHECKING:
    from services.repository_analyzer import AnalyzedRepo

_MUST_ESCAPE = re.compile(r"([_\*\[\]\(\)~`>#+\-=|{}.!\\])")


def _escape(text: str) -> str:
    """Escape all MarkdownV2 special chars in plain text."""
    return _MUST_ESCAPE.sub(r"\\\1", str(text))


def _clean(text: str) -> str:
    """Strip markdown markers from summarizer output before escaping."""
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    text = re.sub(r"_{1,2}(.+?)_{1,2}", r"\1", text)
    text = re.sub(r"`(.+?)`", r"\1", text)
    text = re.sub(r"^[•\-]\s*", "", text, flags=re.MULTILINE)
    return text.strip()


def _bold(text: str) -> str:
    return f"*{_escape(text)}*"


def _link(label: str, url: str) -> str:
    return f"[{_escape(label)}]({url})"


class MarkdownFormatter:
    """Formats an AnalyzedRepo into one or more Telegram-ready message strings."""

    def format(self, repo: "AnalyzedRepo") -> list[str]:
        parts = self._build_parts(repo)
        full_message = "\n".join(parts)
        chunks = split_message(full_message, limit=4000)
        logger.info("Message split into {} chunk(s), total {} chars", len(chunks), len(full_message))
        return chunks

    def _build_parts(self, repo: "AnalyzedRepo") -> list[str]:
        p: list[str] = []

        # ── Header ─────────────────────────────────────────────────────────
        p.append(f"🚀 {_bold('REPO OF THE DAY')}")
        p.append("")
        p.append(f"📦 {_bold(_escape(repo.full_name))}")
        p.append(f"⭐ {_escape(format_number(repo.stars))} stars  {_escape(repo.stars_tier)}")
        p.append(f"💻 {_escape(repo.language or 'N/A')}  📜 {_escape(repo.license or 'N/A')}")
        p.append(f"👤 {_escape(repo.owner)}  📅 {_escape(repo.updated_friendly)}")
        if repo.topics:
            p.append("  ".join(f"\\#{_escape(t)}" for t in repo.topics[:5]))
        p.append("")

        # ── What is it ─────────────────────────────────────────────────────
        p.append(f"📖 {_bold('About')}")
        p.append(_escape(_clean(repo.what_is)))
        p.append("")

        # ── Key Features ───────────────────────────────────────────────────
        if repo.features:
            p.append(f"✨ {_bold('Key Features')}")
            for feat in repo.features[:5]:
                p.append(f"▸ {_escape(_clean(feat))}")
            p.append("")

        # ── Why useful (one-liner style) ────────────────────────────────────
        if repo.why_useful:
            first_line = _clean(repo.why_useful).split("\n")[0].strip()
            if first_line:
                p.append(f"💡 {_escape(first_line)}")
                p.append("")

        # ── Link ───────────────────────────────────────────────────────────
        p.append(_link(f"🔗 {repo.full_name}", repo.url))
        if repo.homepage:
            p.append(_link("🌐 Homepage", repo.homepage))

        return p
