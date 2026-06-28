"""
services/image_generator.py — Premium 1280×720 thumbnail generator using Pillow.

Design: Dark GitHub-inspired theme, gradient background, rounded cards,
professional typography, language colour accent, star badge.
"""
from __future__ import annotations

import io
import math
from pathlib import Path
from typing import TYPE_CHECKING

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from services.logger import logger
from services.utils import format_number, get_language_color

if TYPE_CHECKING:
    from services.repository_analyzer import AnalyzedRepo

# ── Canvas constants ────────────────────────────────────────────────────────
W, H = 1280, 720

# Colour palette (dark GitHub-inspired)
BG_TOP    = (13, 17, 23)      # #0d1117
BG_BOT    = (22, 27, 34)      # #161b22
CARD_BG   = (33, 38, 45)      # #21262d
BORDER    = (48, 54, 61)      # #30363d
TEXT_PRI  = (230, 237, 243)   # #e6edf3
TEXT_SEC  = (139, 148, 158)   # #8b949e
ACCENT    = (88, 166, 255)    # #58a6ff
STAR_COL  = (210, 153, 34)    # #d29922
GREEN     = (63, 185, 80)     # #3fb950
WHITE     = (255, 255, 255)


def _load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Try to load a system font; fall back to PIL default."""
    candidates_bold = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/calibrib.ttf",
    ]
    candidates_reg = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/calibri.ttf",
    ]
    candidates = candidates_bold if bold else candidates_reg
    for path in candidates:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def _hex_to_rgb(hex_str: str) -> tuple[int, int, int]:
    hex_str = hex_str.lstrip("#")
    r, g, b = int(hex_str[0:2], 16), int(hex_str[2:4], 16), int(hex_str[4:6], 16)
    return r, g, b


def _draw_rounded_rect(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int, int, int],
    radius: int,
    fill: tuple,
    outline: tuple | None = None,
    outline_width: int = 1,
) -> None:
    x0, y0, x1, y1 = xy
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=outline_width)


def _gradient_background(img: Image.Image) -> None:
    """Paint a vertical gradient from BG_TOP to BG_BOT."""
    draw = ImageDraw.Draw(img)
    for y in range(H):
        t = y / H
        r = int(BG_TOP[0] + (BG_BOT[0] - BG_TOP[0]) * t)
        g = int(BG_TOP[1] + (BG_BOT[1] - BG_TOP[1]) * t)
        b = int(BG_TOP[2] + (BG_BOT[2] - BG_TOP[2]) * t)
        draw.line([(0, y), (W, y)], fill=(r, g, b))


def _wrap_text(text: str, font: ImageFont.FreeTypeFont | ImageFont.ImageFont, max_width: int) -> list[str]:
    """Word-wrap text to fit within max_width pixels."""
    words = text.split()
    lines: list[str] = []
    current = ""
    dummy_img = Image.new("RGB", (1, 1))
    dummy_draw = ImageDraw.Draw(dummy_img)

    for word in words:
        test = f"{current} {word}".strip() if current else word
        bbox = dummy_draw.textbbox((0, 0), test, font=font)
        if bbox[2] <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word

    if current:
        lines.append(current)
    return lines


def _draw_star_icon(draw: ImageDraw.ImageDraw, x: int, y: int, size: int = 16) -> None:
    """Draw a simple 5-pointed star."""
    points: list[tuple[float, float]] = []
    cx, cy = x + size / 2, y + size / 2
    for i in range(10):
        angle = math.pi * i / 5 - math.pi / 2
        r = size / 2 if i % 2 == 0 else size / 4
        points.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
    draw.polygon(points, fill=STAR_COL)


def _draw_circle_badge(
    draw: ImageDraw.ImageDraw,
    cx: int,
    cy: int,
    radius: int,
    fill: tuple,
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    text_color: tuple = WHITE,
) -> None:
    draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill=fill)
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text((cx - tw // 2, cy - th // 2), text, fill=text_color, font=font)


class ImageGenerator:
    """Generates a 1280×720 thumbnail for the daily repo."""

    def __init__(self, assets_dir: str = "assets") -> None:
        self._assets_dir = Path(assets_dir)
        self._assets_dir.mkdir(parents=True, exist_ok=True)

        # Pre-load fonts
        self._font_title   = _load_font(56, bold=True)
        self._font_heading = _load_font(28, bold=True)
        self._font_body    = _load_font(24)
        self._font_small   = _load_font(20)
        self._font_tiny    = _load_font(16)
        self._font_badge   = _load_font(18, bold=True)

    def generate(self, repo: "AnalyzedRepo") -> str:
        """
        Build the thumbnail and return the file path.
        """
        img = Image.new("RGB", (W, H), BG_TOP)
        _gradient_background(img)
        draw = ImageDraw.Draw(img)

        self._draw_decorative_dots(draw)
        self._draw_header_bar(draw)
        self._draw_title_card(draw, repo)
        self._draw_stats_bar(draw, repo)
        self._draw_features_card(draw, repo)
        self._draw_language_badge(draw, repo)
        self._draw_footer(draw, repo)

        # Add subtle glow effect to accent elements
        img = self._apply_vignette(img)

        out_path = self._assets_dir / f"{repo.full_name.replace('/', '_')}_thumbnail.png"
        img.save(str(out_path), "PNG", optimize=True)
        logger.info("Thumbnail saved: {}", out_path)
        return str(out_path)

    # ── Drawing helpers ────────────────────────────────────────────────────

    def _draw_decorative_dots(self, draw: ImageDraw.ImageDraw) -> None:
        """Subtle grid of dots in the background."""
        dot_color = (30, 35, 42)
        for x in range(0, W, 60):
            for y in range(0, H, 60):
                draw.ellipse((x - 1, y - 1, x + 1, y + 1), fill=dot_color)

    def _draw_header_bar(self, draw: ImageDraw.ImageDraw) -> None:
        """Top accent bar with 'REPO OF THE DAY' branding."""
        # Gradient-like top bar
        for i in range(6):
            alpha = int(255 * (1 - i / 6))
            r, g, b = ACCENT
            draw.line([(0, i), (W, i)], fill=(r, g, b, alpha))

        # Brand pill
        pill_w, pill_h = 280, 44
        pill_x = (W - pill_w) // 2
        _draw_rounded_rect(draw, (pill_x, 20, pill_x + pill_w, 20 + pill_h), 22, ACCENT)
        label = "🚀  REPO OF THE DAY"
        bbox = draw.textbbox((0, 0), label, font=self._font_heading)
        tw = bbox[2] - bbox[0]
        draw.text((pill_x + (pill_w - tw) // 2, 27), label, fill=BG_TOP, font=self._font_heading)

    def _draw_title_card(self, draw: ImageDraw.ImageDraw, repo: "AnalyzedRepo") -> None:
        """Main title area with repo name and description."""
        # Card background
        card_x, card_y = 60, 90
        card_w, card_h = 800, 280
        _draw_rounded_rect(
            draw,
            (card_x, card_y, card_x + card_w, card_y + card_h),
            16,
            CARD_BG,
            outline=BORDER,
            outline_width=1,
        )

        # Repo full name
        owner_part = f"{repo.owner}/"
        draw.text((card_x + 30, card_y + 25), owner_part, fill=TEXT_SEC, font=self._font_body)
        ow_bbox = draw.textbbox((0, 0), owner_part, font=self._font_body)
        ow_w = ow_bbox[2] - ow_bbox[0]
        draw.text((card_x + 30 + ow_w, card_y + 22), repo.name, fill=TEXT_PRI, font=self._font_heading)

        # Description (wrapped)
        desc = repo.description or "An open-source project worth exploring."
        lines = _wrap_text(desc, self._font_body, card_w - 60)[:4]
        y_offset = card_y + 75
        for line in lines:
            draw.text((card_x + 30, y_offset), line, fill=TEXT_SEC, font=self._font_body)
            y_offset += 32

        # Topics pills
        topic_x = card_x + 30
        topic_y = card_y + 200
        for topic in (repo.topics or [])[:6]:
            pill_text = f"  {topic}  "
            bbox = draw.textbbox((0, 0), pill_text, font=self._font_tiny)
            pw = bbox[2] - bbox[0] + 8
            if topic_x + pw > card_x + card_w - 20:
                break
            _draw_rounded_rect(draw, (topic_x, topic_y, topic_x + pw, topic_y + 26), 13, (48, 54, 61))
            draw.text((topic_x + 4, topic_y + 3), pill_text.strip(), fill=ACCENT, font=self._font_tiny)
            topic_x += pw + 8

    def _draw_stats_bar(self, draw: ImageDraw.ImageDraw, repo: "AnalyzedRepo") -> None:
        """Horizontal stats row beneath the title card."""
        stats = [
            ("⭐", format_number(repo.stars), "Stars"),
            ("🍴", format_number(repo.forks), "Forks"),
            ("👥", str(repo.contributors_count or "?"), "Contributors"),
            ("🐛", str(repo.open_issues or 0), "Issues"),
        ]
        box_w = 170
        box_h = 90
        start_x = 60
        y = 390

        for i, (icon, value, label) in enumerate(stats):
            bx = start_x + i * (box_w + 16)
            _draw_rounded_rect(
                draw, (bx, y, bx + box_w, y + box_h), 12, CARD_BG, outline=BORDER
            )
            draw.text((bx + 12, y + 8), icon, fill=TEXT_PRI, font=self._font_heading)
            draw.text((bx + 50, y + 10), value, fill=TEXT_PRI, font=self._font_heading)
            draw.text((bx + 50, y + 46), label, fill=TEXT_SEC, font=self._font_small)

    def _draw_features_card(self, draw: ImageDraw.ImageDraw, repo: "AnalyzedRepo") -> None:
        """Right-side card showing top features."""
        card_x, card_y = 900, 90
        card_w, card_h = 320, 280
        _draw_rounded_rect(
            draw, (card_x, card_y, card_x + card_w, card_y + card_h), 16, CARD_BG, outline=BORDER
        )
        draw.text((card_x + 20, card_y + 18), "✨ Key Highlights", fill=ACCENT, font=self._font_badge)

        features = repo.features[:5] or [repo.description or "Open source & free"]
        y_pos = card_y + 58
        for feat in features:
            short = feat[:38] + "…" if len(feat) > 38 else feat
            draw.text((card_x + 20, y_pos), f"• {short}", fill=TEXT_SEC, font=self._font_tiny)
            y_pos += 28

    def _draw_language_badge(self, draw: ImageDraw.ImageDraw, repo: "AnalyzedRepo") -> None:
        """Language badge in top-right corner."""
        lang = repo.language or "Unknown"
        color = _hex_to_rgb(get_language_color(lang))

        badge_x, badge_y = 900, 390
        badge_w, badge_h = 320, 90

        _draw_rounded_rect(draw, (badge_x, badge_y, badge_x + badge_w, badge_y + badge_h), 12, CARD_BG, outline=BORDER)

        # Colour dot
        draw.ellipse((badge_x + 20, badge_y + 32, badge_x + 42, badge_y + 54), fill=color)

        # Language text
        draw.text((badge_x + 56, badge_y + 22), lang, fill=TEXT_PRI, font=self._font_heading)
        draw.text((badge_x + 56, badge_y + 54), "Primary Language", fill=TEXT_SEC, font=self._font_tiny)

        # Score badge
        score_txt = f"Score: {repo.score:.0f}/100"
        draw.text((badge_x + 180, badge_y + 54), score_txt, fill=GREEN, font=self._font_tiny)

    def _draw_footer(self, draw: ImageDraw.ImageDraw, repo: "AnalyzedRepo") -> None:
        """Bottom bar with URL and branding."""
        footer_y = H - 80

        # Divider
        draw.line([(60, footer_y - 10), (W - 60, footer_y - 10)], fill=BORDER, width=1)

        # Left: GitHub URL
        url_text = repo.url
        draw.text((60, footer_y + 5), url_text, fill=ACCENT, font=self._font_small)

        # Right: Stars tier
        tier = repo.stars_tier or "⭐ Popular"
        bbox = draw.textbbox((0, 0), tier, font=self._font_badge)
        tw = bbox[2] - bbox[0]
        draw.text((W - 60 - tw, footer_y + 5), tier, fill=STAR_COL, font=self._font_badge)

        # Bottom date label
        from datetime import datetime
        today = datetime.now().strftime("%B %d, %Y")
        date_text = f"📅  {today}  •  github.com/trending"
        draw.text((60, footer_y + 38), date_text, fill=TEXT_SEC, font=self._font_tiny)

    def _apply_vignette(self, img: Image.Image) -> Image.Image:
        """Apply a subtle corner vignette for depth."""
        mask = Image.new("L", (W, H), 255)
        draw = ImageDraw.Draw(mask)
        # Gradient from corners
        for r in range(min(W, H) // 3, 0, -1):
            alpha = int(255 * (1 - r / (min(W, H) // 3)) * 0.15)
            draw.ellipse((W // 2 - r, H // 2 - r, W // 2 + r, H // 2 + r), fill=255 - alpha)
        # Compose
        dark = Image.new("RGB", (W, H), BG_TOP)
        img = Image.composite(img, dark, mask)
        return img
