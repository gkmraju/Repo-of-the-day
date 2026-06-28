"""
services/readme_parser.py — Extract structured sections from README markdown.

Handles ATX headings (# Title), Setext headings (Title\n===),
and common README patterns without any AI dependency.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class ParsedReadme:
    raw: str = ""
    plain_text: str = ""
    title: str = ""
    description: str = ""
    installation: str = ""
    usage: str = ""
    features: list[str] = field(default_factory=list)
    examples: list[str] = field(default_factory=list)
    tech_stack: list[str] = field(default_factory=list)
    badges: list[str] = field(default_factory=list)
    screenshots: bool = False
    license_text: str = ""
    contributing: str = ""
    folder_structure: str = ""
    all_sections: dict[str, str] = field(default_factory=dict)


# Section name normaliser
_SECTION_MAP: dict[str, str] = {
    # installation
    "install": "installation",
    "installation": "installation",
    "setup": "installation",
    "getting started": "installation",
    "quick start": "installation",
    "quickstart": "installation",
    # usage
    "usage": "usage",
    "use": "usage",
    "how to use": "usage",
    "how it works": "how_it_works",
    "how does it work": "how_it_works",
    "overview": "how_it_works",
    "architecture": "how_it_works",
    # features
    "features": "features",
    "feature list": "features",
    "key features": "features",
    "highlights": "features",
    # examples
    "example": "examples",
    "examples": "examples",
    "demo": "examples",
    "showcase": "examples",
    # tech stack
    "tech stack": "tech_stack",
    "technologies": "tech_stack",
    "built with": "tech_stack",
    "stack": "tech_stack",
    "dependencies": "tech_stack",
    # contributing
    "contributing": "contributing",
    "contribution": "contributing",
    "contribute": "contributing",
    # license
    "license": "license",
    "licence": "license",
}

_ATX_HEADING = re.compile(r"^(#{1,4})\s+(.+)$", re.MULTILINE)
_CODE_BLOCK = re.compile(r"```[\w]*\n(.*?)```", re.DOTALL)
_BADGE = re.compile(r"!\[.*?\]\(https?://[^\)]+\)")
_BULLET = re.compile(r"^[\s]*[-*+]\s+(.+)$", re.MULTILINE)
_FOLDER = re.compile(r"(├|└|─|│|  )", re.MULTILINE)


def parse_readme(raw: str) -> ParsedReadme:
    """Parse a raw README string into a structured ParsedReadme."""
    if not raw:
        return ParsedReadme()

    parsed = ParsedReadme(raw=raw)

    # Plain text version (strip markdown)
    parsed.plain_text = _to_plain(raw)

    # Badges
    parsed.badges = _BADGE.findall(raw)

    # Screenshots detected
    parsed.screenshots = bool(re.search(r"screenshot|preview|demo\.gif|demo\.png", raw, re.I))

    # Folder structure
    if _FOLDER.search(raw):
        lines = raw.splitlines()
        struct_lines = [l for l in lines if _FOLDER.search(l)]
        parsed.folder_structure = "\n".join(struct_lines[:20])

    # Split into sections
    sections = _split_sections(raw)
    parsed.all_sections = sections

    # Map sections to known keys
    for heading, content in sections.items():
        canonical = _SECTION_MAP.get(heading.lower().strip())
        if canonical == "installation":
            parsed.installation = content
        elif canonical == "usage":
            parsed.usage = content
        elif canonical == "features":
            parsed.features = _extract_bullets(content)
        elif canonical == "examples":
            parsed.examples = _extract_code_blocks(content)
        elif canonical == "tech_stack":
            parsed.tech_stack = _extract_bullets(content)
        elif canonical == "contributing":
            parsed.contributing = content[:500]
        elif canonical == "license":
            parsed.license_text = content[:300]

    # Title: first H1 or repo name from first line
    first_h1 = re.search(r"^#\s+(.+)$", raw, re.MULTILINE)
    if first_h1:
        parsed.title = first_h1.group(1).strip()

    # Description: first meaningful paragraph after title
    parsed.description = _extract_description(raw, parsed.title)

    # If features not found in sections, try to extract from first bullets
    if not parsed.features:
        parsed.features = _extract_bullets(parsed.plain_text)[:8]

    return parsed


# ── Helpers ────────────────────────────────────────────────────────────────

def _split_sections(text: str) -> dict[str, str]:
    """Return {heading: content} for all ATX headings in the text."""
    sections: dict[str, str] = {}
    lines = text.splitlines()
    current_heading = "__intro__"
    current_lines: list[str] = []

    for line in lines:
        m = re.match(r"^#{1,4}\s+(.+)$", line)
        if m:
            if current_lines:
                sections[current_heading] = "\n".join(current_lines).strip()
            current_heading = m.group(1).strip()
            current_lines = []
        else:
            current_lines.append(line)

    if current_lines:
        sections[current_heading] = "\n".join(current_lines).strip()

    return sections


def _to_plain(md: str) -> str:
    """Convert markdown to plain text."""
    # Remove code blocks first (preserve them as-is for extraction)
    no_code = re.sub(r"```[\w]*\n.*?```", "", md, flags=re.DOTALL)
    no_code = re.sub(r"`[^`]+`", "", no_code)
    # Remove HTML tags
    no_code = re.sub(r"<[^>]+>", "", no_code)
    # Remove images / badges
    no_code = re.sub(r"!\[.*?\]\([^\)]+\)", "", no_code)
    # Remove links but keep text
    no_code = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", no_code)
    # Remove headings markers
    no_code = re.sub(r"^#{1,6}\s+", "", no_code, flags=re.MULTILINE)
    # Collapse whitespace
    no_code = re.sub(r"\n{3,}", "\n\n", no_code)
    return no_code.strip()


def _extract_bullets(text: str) -> list[str]:
    matches = _BULLET.findall(text)
    # Clean each bullet
    cleaned = []
    for m in matches:
        item = re.sub(r"[`*_~]", "", m).strip()
        if item and len(item) > 5:
            cleaned.append(item)
    return cleaned[:10]


def _extract_code_blocks(text: str) -> list[str]:
    return _CODE_BLOCK.findall(text)[:3]


def _extract_description(text: str, title: str) -> str:
    """Extract the first meaningful paragraph that isn't a badge line."""
    paragraphs = re.split(r"\n\s*\n", text)
    for para in paragraphs:
        clean = _to_plain(para).strip()
        # Skip if it's just the title or badges
        if not clean or clean == title:
            continue
        if len(clean) < 30:
            continue
        # Skip lines that are entirely badges / shields
        if re.match(r"^\[!\[", para.strip()):
            continue
        # Take up to 200 chars
        return clean[:200]
    return ""
