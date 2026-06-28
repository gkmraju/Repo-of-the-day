"""
services/telegram_service.py — Telegram Bot API client.

Features:
  • send_message() with MarkdownV2 parse mode
  • send_photo() to post thumbnail + caption
  • Automatic long-message splitting
  • Retry with exponential backoff
  • Detailed logging
"""
from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Any

import requests

from services.logger import logger
from services.utils import retry, split_message

TELEGRAM_API = "https://api.telegram.org/bot{token}/{method}"
MAX_CAPTION_LEN = 1024    # Telegram limit for photo captions
MAX_MESSAGE_LEN = 4096    # Telegram limit for text messages


class TelegramService:
    """Thin wrapper around the Telegram Bot API."""

    def __init__(self, bot_token: str, chat_id: str, timeout: int = 30) -> None:
        self._token = bot_token
        self._chat_id = chat_id
        self._timeout = timeout
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": "RepoOfTheDay/1.0"})

    # ── Public API ─────────────────────────────────────────────────────────

    def send_photo_with_messages(
        self,
        image_path: str,
        messages: list[str],
        caption: str = "",
    ) -> list[dict[str, Any]]:
        """
        Post the thumbnail first (with a short caption), then send all
        text message chunks as follow-up messages.
        """
        results: list[dict[str, Any]] = []

        # 1. Send photo
        short_caption = (caption or "🚀 Repo Of The Day")[:MAX_CAPTION_LEN]
        photo_result = self._send_photo(image_path, short_caption)
        results.append(photo_result)
        time.sleep(1)

        # 2. Send text chunks
        for i, chunk in enumerate(messages, 1):
            logger.info("Sending message chunk {}/{} ({} chars)", i, len(messages), len(chunk))
            result = self._send_message(chunk)
            results.append(result)
            if i < len(messages):
                time.sleep(1.5)   # Be polite to Telegram rate limits

        return results

    def send_text_only(self, messages: list[str]) -> list[dict[str, Any]]:
        """Send text messages without a photo (fallback or dry-run check)."""
        results = []
        for i, chunk in enumerate(messages, 1):
            logger.info("Sending text chunk {}/{}", i, len(messages))
            results.append(self._send_message(chunk))
            if i < len(messages):
                time.sleep(1.5)
        return results

    def test_connection(self) -> bool:
        """Verify bot token is valid."""
        try:
            url = TELEGRAM_API.format(token=self._token, method="getMe")
            resp = self._session.get(url, timeout=self._timeout)
            data = resp.json()
            if data.get("ok"):
                bot_name = data["result"].get("username", "?")
                logger.info("Telegram connected — bot: @{}", bot_name)
                return True
            logger.error("Telegram getMe failed: {}", data)
            return False
        except Exception as exc:
            logger.error("Telegram connection test failed: {}", exc)
            return False

    # ── Internal ───────────────────────────────────────────────────────────

    @retry(max_attempts=5, delay=3.0, backoff=2.0, exceptions=(Exception,))
    def _send_message(self, text: str) -> dict[str, Any]:
        url = TELEGRAM_API.format(token=self._token, method="sendMessage")
        payload = {
            "chat_id": self._chat_id,
            "text": text,
            "parse_mode": "MarkdownV2",
            "disable_web_page_preview": False,
        }
        resp = self._session.post(url, json=payload, timeout=self._timeout)
        data = resp.json()
        if not data.get("ok"):
            error_code = data.get("error_code", 0)
            description = data.get("description", "Unknown error")
            # 429 = rate limited
            if error_code == 429:
                retry_after = data.get("parameters", {}).get("retry_after", 30)
                logger.warning("Rate limited by Telegram. Sleeping {}s", retry_after)
                time.sleep(retry_after)
                raise RuntimeError(f"Rate limited (retry after {retry_after}s)")
            # 400 with bad markdown — attempt plain-text fallback
            if error_code == 400 and "can't parse" in description.lower():
                logger.warning("MarkdownV2 parse error — falling back to plain text")
                return self._send_plain(text)
            raise RuntimeError(f"Telegram error {error_code}: {description}")
        logger.debug("Message sent: message_id={}", data["result"].get("message_id"))
        return data["result"]

    def _send_plain(self, text: str) -> dict[str, Any]:
        """Fallback: send message without parse mode."""
        plain = re.sub(r"[*_`\[\]()~>#+\-=|{}!\\]", "", text)
        url = TELEGRAM_API.format(token=self._token, method="sendMessage")
        payload = {"chat_id": self._chat_id, "text": plain[:MAX_MESSAGE_LEN]}
        resp = self._session.post(url, json=payload, timeout=self._timeout)
        return resp.json().get("result", {})

    @retry(max_attempts=5, delay=3.0, backoff=2.0, exceptions=(Exception,))
    def _send_photo(self, image_path: str, caption: str) -> dict[str, Any]:
        url = TELEGRAM_API.format(token=self._token, method="sendPhoto")
        path = Path(image_path)
        if not path.exists():
            logger.error("Thumbnail not found: {}", image_path)
            raise FileNotFoundError(f"Thumbnail missing: {image_path}")

        with open(path, "rb") as f:
            resp = self._session.post(
                url,
                data={
                    "chat_id": self._chat_id,
                    "caption": caption[:MAX_CAPTION_LEN],
                    "parse_mode": "MarkdownV2",
                },
                files={"photo": (path.name, f, "image/png")},
                timeout=self._timeout * 2,
            )

        data = resp.json()
        if not data.get("ok"):
            error_code = data.get("error_code", 0)
            desc = data.get("description", "Unknown error")
            if error_code == 429:
                retry_after = data.get("parameters", {}).get("retry_after", 30)
                time.sleep(retry_after)
                raise RuntimeError(f"Rate limited (retry after {retry_after}s)")
            if error_code == 400 and "can't parse" in desc.lower():
                logger.warning("MarkdownV2 parse error in caption — retrying without parse_mode")
                return self._send_photo_plain(image_path, caption)
            raise RuntimeError(f"Photo send error {error_code}: {desc}")

        logger.info("Photo sent: message_id={}", data["result"].get("message_id"))
        return data["result"]

    def _send_photo_plain(self, image_path: str, caption: str) -> dict[str, Any]:
        """Fallback: send photo with plain caption (no MarkdownV2)."""
        plain_caption = re.sub(r"[*_`\[\]()~>#+\-=|{}.!\\]", "", caption)
        url = TELEGRAM_API.format(token=self._token, method="sendPhoto")
        path = Path(image_path)
        with open(path, "rb") as f:
            resp = self._session.post(
                url,
                data={"chat_id": self._chat_id, "caption": plain_caption[:MAX_CAPTION_LEN]},
                files={"photo": (path.name, f, "image/png")},
                timeout=self._timeout * 2,
            )
        data = resp.json()
        logger.info("Photo sent (plain): message_id={}", data.get("result", {}).get("message_id"))
        return data.get("result", {})
