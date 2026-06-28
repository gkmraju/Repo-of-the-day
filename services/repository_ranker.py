"""
services/repository_ranker.py — Weighted multi-signal scoring algorithm.

Each repository receives a normalised score between 0 and 100.
Weights are loaded from config so operators can tune without code changes.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from services.logger import logger
from services.utils import days_ago

if TYPE_CHECKING:
    from services.github_service import RawRepo


# ── Scorer ─────────────────────────────────────────────────────────────────

class RepositoryRanker:
    """
    Computes a composite score for a RawRepo using configurable weights.

    Signals
    -------
    stars            — absolute star count (log-normalised)
    recent_activity  — days since last push (inverted, capped at 365)
    growth_potential — forks-to-stars ratio (proxy for derivative projects)
    readme_quality   — length & presence of key sections
    contributors     — number of contributors (log-normalised)
    issue_activity   — open issues (moderate is good; too many = penalty)
    documentation    — homepage URL, topics, license presence
    popularity       — watchers count (log-normalised)
    community        — contributor-to-star ratio
    """

    def __init__(self, weights: dict[str, float] | None = None) -> None:
        self._weights = weights or {
            "stars": 0.25,
            "recent_activity": 0.20,
            "growth_potential": 0.10,
            "readme_quality": 0.10,
            "contributors": 0.10,
            "issue_activity": 0.05,
            "documentation": 0.10,
            "popularity": 0.05,
            "community": 0.05,
        }
        total = sum(self._weights.values())
        if abs(total - 1.0) > 0.01:
            logger.warning("Weights sum to {:.3f} (expected 1.0) — normalising", total)
            self._weights = {k: v / total for k, v in self._weights.items()}

    # ── Public API ─────────────────────────────────────────────────────────

    def score(self, repo: "RawRepo", readme: str = "") -> float:
        """Return a composite score in [0, 100]."""
        signals = {
            "stars":            self._score_stars(repo.stars or 0),
            "recent_activity":  self._score_activity(repo.pushed_at),
            "growth_potential": self._score_growth(repo.stars or 0, repo.forks or 0),
            "readme_quality":   self._score_readme(readme),
            "contributors":     self._score_contributors(repo.contributors_count or 0),
            "issue_activity":   self._score_issues(repo.open_issues or 0, repo.stars or 0),
            "documentation":    self._score_documentation(repo),
            "popularity":       self._score_popularity(repo.watchers or 0),
            "community":        self._score_community(repo.contributors_count or 0, repo.stars or 0),
        }

        composite = sum(self._weights.get(k, 0) * v for k, v in signals.items())
        final = min(100.0, max(0.0, composite * 100))

        logger.debug(
            "Score {:.1f} for {} | {}",
            final,
            repo.full_name,
            " | ".join(f"{k}={v:.2f}" for k, v in signals.items()),
        )
        return round(final, 2)

    def rank(self, repos: list["RawRepo"], readmes: dict[str, str] | None = None) -> list[tuple["RawRepo", float]]:
        """Return list of (repo, score) sorted descending."""
        readmes = readmes or {}
        scored = [(r, self.score(r, readmes.get(r.full_name, ""))) for r in repos]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored

    # ── Individual signal scorers ──────────────────────────────────────────

    @staticmethod
    def _score_stars(stars: int) -> float:
        """Log-normalise star count. 50k stars → ~1.0."""
        if stars <= 0:
            return 0.0
        return min(1.0, math.log10(stars + 1) / math.log10(50_001))

    @staticmethod
    def _score_activity(pushed_at: str | None) -> float:
        """
        Repos pushed within 7 days → 1.0, drops linearly to 0 at 365 days.
        """
        if not pushed_at:
            return 0.0
        age = days_ago(pushed_at)
        if age <= 7:
            return 1.0
        if age >= 365:
            return 0.0
        return 1.0 - (age - 7) / (365 - 7)

    @staticmethod
    def _score_growth(stars: int, forks: int) -> float:
        """
        Healthy fork/star ratio ≈ 0.1–0.3 is considered a good sign of
        derivative usage.  Very high ratio (>0.5) may indicate bot forks.
        """
        if stars <= 0:
            return 0.0
        ratio = forks / stars
        if ratio < 0.05:
            return 0.3
        if ratio <= 0.30:
            return 1.0
        if ratio <= 0.50:
            return 0.7
        return 0.4

    @staticmethod
    def _score_readme(readme: str) -> float:
        """
        Score based on README length and presence of key sections.
        """
        if not readme:
            return 0.0

        score = 0.0
        length = len(readme)

        # Length component (cap at 10k chars)
        score += min(0.4, length / 25_000)

        # Section presence
        lower = readme.lower()
        section_keywords = [
            ("installation", 0.1),
            ("usage", 0.1),
            ("example", 0.1),
            ("feature", 0.1),
            ("license", 0.05),
            ("contribut", 0.05),
            ("screenshot", 0.05),
            ("quick start", 0.05),
        ]
        for kw, weight in section_keywords:
            if kw in lower:
                score += weight

        return min(1.0, score)

    @staticmethod
    def _score_contributors(count: int) -> float:
        """Log-normalise contributor count. 100+ → 1.0."""
        if count <= 0:
            return 0.0
        return min(1.0, math.log10(count + 1) / math.log10(101))

    @staticmethod
    def _score_issues(open_issues: int, stars: int) -> float:
        """
        A healthy ratio of issues/stars signals engagement.
        Too many issues relative to stars may indicate instability.
        """
        if stars <= 0:
            return 0.5
        ratio = open_issues / max(stars, 1)
        if ratio < 0.001:
            return 0.4   # No issues — dormant?
        if ratio <= 0.05:
            return 1.0   # Healthy
        if ratio <= 0.15:
            return 0.7
        return 0.3        # Issue-heavy

    @staticmethod
    def _score_documentation(repo: "RawRepo") -> float:
        """Score based on homepage, topics, and license."""
        score = 0.0
        if repo.homepage:
            score += 0.3
        topics = repo.topics or []
        score += min(0.4, len(topics) * 0.08)
        if repo.license:
            score += 0.3
        return min(1.0, score)

    @staticmethod
    def _score_popularity(watchers: int) -> float:
        """Log-normalise watcher count."""
        if watchers <= 0:
            return 0.0
        return min(1.0, math.log10(watchers + 1) / math.log10(10_001))

    @staticmethod
    def _score_community(contributors: int, stars: int) -> float:
        """High contributor/star ratio indicates strong open-source community."""
        if stars <= 0:
            return 0.0
        ratio = contributors / max(stars, 1)
        return min(1.0, ratio / 0.005)   # 0.5% contributor/star is excellent
