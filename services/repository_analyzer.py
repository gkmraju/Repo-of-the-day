"""
services/repository_analyzer.py — Full pipeline: fetch + parse + score + summarize.

Orchestrates GitHubService, ReadmeParser, RepositoryRanker, and Summarizer
into a single AnalyzedRepo result object.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from services.github_service import GitHubService, RawRepo
from services.logger import logger
from services.readme_parser import ParsedReadme, parse_readme
from services.repository_ranker import RepositoryRanker
from services.summarizer import Summarizer
from services.utils import days_ago, format_number, friendly_date, stars_tier

if TYPE_CHECKING:
    pass


@dataclass
class AnalyzedRepo:
    """All data needed to render the Telegram message and thumbnail."""

    # Core identity
    full_name: str = ""
    name: str = ""
    owner: str = ""
    description: str = ""
    url: str = ""
    homepage: str = ""

    # Metadata
    topics: list[str] = field(default_factory=list)
    language: str = ""
    license: str = ""

    # Stats
    stars: int = 0
    forks: int = 0
    watchers: int = 0
    open_issues: int = 0
    contributors_count: int = 0
    stars_formatted: str = ""
    forks_formatted: str = ""
    stars_tier: str = ""

    # Dates
    created_at: str = ""
    updated_at: str = ""
    pushed_at: str = ""
    created_friendly: str = ""
    updated_friendly: str = ""
    days_since_push: int = 0
    latest_release: str = ""

    # Scoring
    score: float = 0.0
    score_breakdown: dict[str, float] = field(default_factory=dict)

    # Generated content
    what_is: str = ""
    why_useful: str = ""
    audience: list[str] = field(default_factory=list)
    features: list[str] = field(default_factory=list)
    how_it_works: str = ""
    installation: str = ""
    quick_example: str = ""
    tech_stack: list[str] = field(default_factory=list)
    pros: list[str] = field(default_factory=list)
    cons: list[str] = field(default_factory=list)
    learnings: list[str] = field(default_factory=list)
    similar_projects: list[dict] = field(default_factory=list)
    one_liner: str = ""
    keywords: list[str] = field(default_factory=list)

    # Source tracking
    source: str = ""
    thumbnail_path: str = ""

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


class RepositoryAnalyzer:
    """
    High-level pipeline that takes a RawRepo and returns AnalyzedRepo.
    """

    def __init__(
        self,
        github_service: GitHubService,
        ranker: RepositoryRanker,
        summarizer: Summarizer,
    ) -> None:
        self._gh = github_service
        self._ranker = ranker
        self._summarizer = summarizer

    def analyze(self, repo: RawRepo) -> AnalyzedRepo:
        """
        Full analysis of a single repository.
        Returns an AnalyzedRepo populated with all content.
        """
        logger.info("Analyzing: {}", repo.full_name)

        # 1. Fetch README
        readme_raw = self._gh.fetch_readme(repo.full_name)
        readme: ParsedReadme = parse_readme(readme_raw)

        # 2. Fetch latest release
        latest_release = self._gh.fetch_latest_release(repo.full_name) or ""

        # 3. Score
        score = self._ranker.score(repo, readme_raw)

        # 4. Generate content
        content = self._summarizer.generate(repo, readme)

        # 5. Assemble
        return AnalyzedRepo(
            full_name=repo.full_name or "",
            name=repo.name or "",
            owner=repo.owner or "",
            description=repo.description or "",
            url=repo.url or "",
            homepage=repo.homepage or "",
            topics=repo.topics or [],
            language=repo.language or "",
            license=repo.license or "",
            stars=repo.stars or 0,
            forks=repo.forks or 0,
            watchers=repo.watchers or 0,
            open_issues=repo.open_issues or 0,
            contributors_count=repo.contributors_count or 0,
            stars_formatted=format_number(repo.stars or 0),
            forks_formatted=format_number(repo.forks or 0),
            stars_tier=stars_tier(repo.stars or 0),
            created_at=repo.created_at or "",
            updated_at=repo.updated_at or "",
            pushed_at=repo.pushed_at or "",
            created_friendly=friendly_date(repo.created_at),
            updated_friendly=friendly_date(repo.updated_at),
            days_since_push=days_ago(repo.pushed_at) if repo.pushed_at else 999,
            latest_release=latest_release,
            score=score,
            what_is=content["what_is"],
            why_useful=content["why_useful"],
            audience=content["audience"],
            features=content["features"],
            how_it_works=content["how_it_works"],
            installation=content["installation"],
            quick_example=content["quick_example"],
            tech_stack=content["tech_stack"],
            pros=content["pros"],
            cons=content["cons"],
            learnings=content["learnings"],
            similar_projects=content["similar_projects"],
            one_liner=content["one_liner"],
            keywords=content["keywords"],
            source=repo.source or "",
        )
