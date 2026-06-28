"""
services/markdown_formatter.py — Render AnalyzedRepo into a Telegram MarkdownV2 message.

Telegram MarkdownV2 requires escaping of: _ * [ ] ( ) ~ ` > # + - = | { } . !
We build the message from the Jinja2 template, then escape properly.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

from jinja2 import Environment, FileSystemLoader, select_autoescape

from services.logger import logger
from services.utils import escape_markdown_v2, format_number, split_message

if TYPE_CHECKING:
    from services.repository_analyzer import AnalyzedRepo

# Characters that MUST be escaped in Telegram MarkdownV2
_MUST_ESCAPE = re.compile(r"([_\*\[\]\(\)~`>#+\-=|{}.!\\])")

# Characters inside *bold*, _italic_, `code` sections that must NOT be double-escaped
_CODE_BLOCK_RE = re.compile(r"(```[\s\S]*?```|`[^`]+`|\*[^\*]+\*|__[^_]+__|_[^_]+_)")


def _escape(text: str) -> str:
    """Escape all MarkdownV2 special characters in plain text."""
    return _MUST_ESCAPE.sub(r"\\\1", str(text))


def _code(text: str) -> str:
    """Wrap in MarkdownV2 inline code."""
    # Escape backticks inside code content
    return f"`{text.replace('`', chr(8216))}`"


def _bold(text: str) -> str:
    return f"*{_escape(text)}*"


def _italic(text: str) -> str:
    return f"_{_escape(text)}_"


def _link(label: str, url: str) -> str:
    return f"[{_escape(label)}]({url})"


DIVIDER = _escape("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")


class MarkdownFormatter:
    """Formats an AnalyzedRepo into one or more Telegram-ready message strings."""

    def format(self, repo: "AnalyzedRepo") -> list[str]:
        """
        Return a list of message chunks, each ≤ 4096 characters,
        ready for sequential Telegram delivery.
        """
        parts = self._build_parts(repo)
        full_message = "\n".join(parts)
        chunks = split_message(full_message, limit=4000)
        logger.info("Message split into {} chunk(s), total {} chars", len(chunks), len(full_message))
        return chunks

    def _build_parts(self, repo: "AnalyzedRepo") -> list[str]:
        p = []

        # ── Header ─────────────────────────────────────────────────────────
        p.append(DIVIDER)
        p.append(f"🚀 {_bold('REPO OF THE DAY')}")
        p.append(DIVIDER)
        p.append(f"📦 {_bold('Repository:')} {_escape(repo.full_name)}")
        p.append(f"⭐ {_bold('Stars:')} {_escape(format_number(repo.stars))} {_escape(repo.stars_tier)}")
        p.append(f"💻 {_bold('Language:')} {_escape(repo.language or 'N/A')}")
        p.append(f"👤 {_bold('Author:')} {_escape(repo.owner)}")
        if repo.license:
            p.append(f"📜 {_bold('License:')} {_escape(repo.license)}")
        if repo.topics:
            topics_str = "  ".join(f"#{_escape(t)}" for t in repo.topics[:6])
            p.append(f"🏷️  {topics_str}")
        p.append("")

        # ── What is it ─────────────────────────────────────────────────────
        p.append(DIVIDER)
        p.append(f"📖 {_bold('What is it?')}")
        p.append(DIVIDER)
        p.append(_escape(repo.what_is))
        p.append("")

        # ── Why useful ─────────────────────────────────────────────────────
        p.append(DIVIDER)
        p.append(f"❓ {_bold('Why is it useful?')}")
        p.append(DIVIDER)
        p.append(_escape(repo.why_useful))
        p.append("")

        # ── Audience ───────────────────────────────────────────────────────
        if repo.audience:
            p.append(DIVIDER)
            p.append(f"👥 {_bold('Who should use it?')}")
            p.append(DIVIDER)
            for aud in repo.audience:
                p.append(f"• {_escape(aud)}")
            p.append("")

        # ── Key Features ───────────────────────────────────────────────────
        if repo.features:
            p.append(DIVIDER)
            p.append(f"✨ {_bold('Key Features')}")
            p.append(DIVIDER)
            for feat in repo.features[:8]:
                p.append(f"▸ {_escape(feat)}")
            p.append("")

        # ── How it works ───────────────────────────────────────────────────
        if repo.how_it_works:
            p.append(DIVIDER)
            p.append(f"⚙️ {_bold('How it works')}")
            p.append(DIVIDER)
            p.append(_escape(repo.how_it_works[:600]))
            p.append("")

        # ── Installation ───────────────────────────────────────────────────
        if repo.installation:
            p.append(DIVIDER)
            p.append(f"📦 {_bold('Installation')}")
            p.append(DIVIDER)
            install = repo.installation[:400].strip()
            # Wrap in code block if it looks like commands
            if any(c in install for c in ["pip ", "npm ", "git clone", "cargo ", "go install", "apt "]):
                p.append(f"```\n{install}\n```")
            else:
                p.append(_escape(install))
            p.append("")

        # ── Quick example ──────────────────────────────────────────────────
        if repo.quick_example:
            p.append(DIVIDER)
            p.append(f"💻 {_bold('Quick Example')}")
            p.append(DIVIDER)
            ex = repo.quick_example[:400].strip()
            p.append(f"```\n{ex}\n```")
            p.append("")

        # ── Tech stack ─────────────────────────────────────────────────────
        if repo.tech_stack:
            p.append(DIVIDER)
            p.append(f"🛠 {_bold('Tech Stack')}")
            p.append(DIVIDER)
            for item in repo.tech_stack[:6]:
                p.append(f"• {_escape(item)}")
            p.append("")

        # ── Pros & Cons ────────────────────────────────────────────────────
        if repo.pros or repo.cons:
            p.append(DIVIDER)
            p.append(f"✅ {_bold('Pros')}  ·  ⚠️ {_bold('Considerations')}")
            p.append(DIVIDER)
            for pro in repo.pros[:4]:
                p.append(f"✅ {_escape(pro)}")
            for con in repo.cons[:3]:
                p.append(f"⚠️ {_escape(con)}")
            p.append("")

        # ── What can you learn ─────────────────────────────────────────────
        if repo.learnings:
            p.append(DIVIDER)
            p.append(f"🎓 {_bold('What Can You Learn?')}")
            p.append(DIVIDER)
            for item in repo.learnings[:5]:
                p.append(f"📌 {_escape(item)}")
            p.append("")

        # ── Similar projects ───────────────────────────────────────────────
        if repo.similar_projects:
            p.append(DIVIDER)
            p.append(f"🔄 {_bold('Similar Projects')}")
            p.append(DIVIDER)
            for proj in repo.similar_projects[:5]:
                name = proj.get("name", "")
                desc = proj.get("desc", "")
                url  = f"https://github.com/{name}"
                p.append(f"• {_link(name, url)} — {_escape(desc)}")
            p.append("")

        # ── GitHub Stats ───────────────────────────────────────────────────
        p.append(DIVIDER)
        p.append(f"📊 {_bold('GitHub Statistics')}")
        p.append(DIVIDER)
        p.append(f"⭐ Stars:        {_bold(_escape(format_number(repo.stars)))}")
        p.append(f"🍴 Forks:        {_escape(format_number(repo.forks))}")
        p.append(f"👥 Contributors: {_escape(str(repo.contributors_count or '?'))}")
        p.append(f"🐞 Open Issues:  {_escape(str(repo.open_issues or 0))}")
        p.append(f"📅 Last Updated: {_escape(repo.updated_friendly)}")
        if repo.latest_release:
            p.append(f"🏷️  Latest Release: {_escape(repo.latest_release)}")
        p.append("")

        # ── Link ───────────────────────────────────────────────────────────
        p.append(DIVIDER)
        p.append(f"🔗 {_bold('Repository Link')}")
        p.append(DIVIDER)
        p.append(_link(f"👉 {repo.full_name}", repo.url))
        if repo.homepage:
            p.append(_link("🌐 Homepage", repo.homepage))
        p.append("")

        # ── One-liner ──────────────────────────────────────────────────────
        p.append(DIVIDER)
        p.append(_escape(repo.one_liner))
        p.append("")
        p.append(_escape("💡 Learn something new every day!"))
        p.append(_escape("🔔 Follow this channel for daily repos!"))
        p.append(DIVIDER)

        return p
