"""
services/github_service.py — Multi-source GitHub repository discovery.

Sources (in priority order):
  1. GitHub Trending (web scrape — no API key needed)
  2. GitHub Search API (requires token)
  3. GitHub Topics API
  4. Awesome-list curated repos (optional fallback)
"""
from __future__ import annotations

import base64
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import requests
from bs4 import BeautifulSoup
from github import Github, RateLimitExceededException

from services.logger import logger
from services.utils import retry


# ── Pydantic-style dataclass for raw repo data ─────────────────────────────

class RawRepo:
    """Lightweight container for discovered repo metadata."""

    __slots__ = (
        "full_name", "name", "owner", "description", "url", "homepage",
        "topics", "language", "license", "stars", "forks", "watchers",
        "open_issues", "contributors_count", "created_at", "updated_at",
        "pushed_at", "default_branch", "is_archived", "is_fork",
        "readme_content", "latest_release", "source",
    )

    # Slot type annotations so type checkers can resolve attribute types
    full_name: str | None
    name: str | None
    owner: str | None
    description: str | None
    url: str | None
    homepage: str | None
    topics: list[str] | None
    language: str | None
    license: str | None
    stars: int | None
    forks: int | None
    watchers: int | None
    open_issues: int | None
    contributors_count: int | None
    created_at: str | None
    updated_at: str | None
    pushed_at: str | None
    default_branch: str | None
    is_archived: bool | None
    is_fork: bool | None
    readme_content: str | None
    latest_release: str | None
    source: str | None

    def __init__(self, **kwargs: Any) -> None:
        for slot in self.__slots__:
            setattr(self, slot, kwargs.get(slot))

    def to_dict(self) -> dict[str, Any]:
        return {s: getattr(self, s) for s in self.__slots__}


# ── GitHub Service ─────────────────────────────────────────────────────────

class GitHubService:
    """Discovers GitHub repositories from multiple free sources."""

    TRENDING_URL = "https://github.com/trending"
    TRENDING_LANGS = ["", "python", "javascript", "typescript", "go", "rust", "java"]

    SEARCH_QUERIES = [
        "stars:>1000 pushed:>{date} sort:stars",
        "stars:>500 topic:machine-learning pushed:>{date}",
        "stars:>500 topic:developer-tools pushed:>{date}",
        "stars:>500 topic:cli pushed:>{date}",
        "stars:>500 topic:api pushed:>{date}",
        "stars:>300 topic:open-source pushed:>{date} sort:updated",
    ]

    HOT_TOPICS = [
        "machine-learning", "devops", "cli", "api", "automation",
        "data-science", "security", "web", "database", "infrastructure",
        "llm", "ai", "blockchain", "game", "mobile",
    ]

    def __init__(self, token: str, timeout: int = 30) -> None:
        self._gh: Any = Github(token)
        self._token = token
        self._timeout = timeout
        self._headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "RepoOfTheDay/1.0",
        }

    # ── Public entry point ─────────────────────────────────────────────────

    def discover_repos(self, min_stars: int = 300, max_per_source: int = 50) -> list[RawRepo]:
        """
        Collect repositories from all sources, deduplicate, and return.
        """
        seen: set[str] = set()
        all_repos: list[RawRepo] = []

        sources = [
            ("GitHub Trending", lambda: self._fetch_trending(max_per_source)),
            ("GitHub Search",   lambda: self._fetch_search(min_stars, max_per_source)),
            ("GitHub Topics",   lambda: self._fetch_topics(min_stars, max_per_source)),
        ]

        for name, fetch_fn in sources:
            try:
                repos = fetch_fn()
                new = [r for r in repos if r.full_name not in seen]
                seen.update(r.full_name for r in new)
                all_repos.extend(new)
                logger.info("Source '{}': {} repos collected ({} new)", name, len(repos), len(new))
            except Exception as exc:
                logger.warning("Source '{}' failed: {}", name, exc)

        logger.info("Total unique repos discovered: {}", len(all_repos))
        return all_repos

    # ── Source 1: GitHub Trending scraper ─────────────────────────────────

    @retry(max_attempts=3, delay=5.0, exceptions=(Exception,))
    def _fetch_trending(self, limit: int) -> list[RawRepo]:
        repos: list[RawRepo] = []

        for lang in self.TRENDING_LANGS:
            url = f"{self.TRENDING_URL}/{lang}" if lang else self.TRENDING_URL
            try:
                resp = requests.get(
                    url,
                    headers={"User-Agent": "Mozilla/5.0 RepoOfTheDay/1.0"},
                    timeout=self._timeout,
                )
                resp.raise_for_status()
                repos.extend(self._parse_trending_html(resp.text))
                time.sleep(1.5)           # Be polite
            except Exception as exc:
                logger.debug("Trending lang={} failed: {}", lang, exc)

            if len(repos) >= limit:
                break

        # Enrich with full API data
        return self._enrich_repos(repos[:limit], source="trending")

    def _parse_trending_html(self, html: str) -> list[RawRepo]:
        soup = BeautifulSoup(html, "lxml")
        raw: list[RawRepo] = []

        for article in soup.select("article.Box-row"):
            try:
                link = article.select_one("h2 a")
                if not link:
                    continue
                full_name = str(link.get("href") or "").lstrip("/")
                if "/" not in full_name:
                    continue

                desc_el = article.select_one("p")
                description = desc_el.get_text(strip=True) if desc_el else ""

                lang_el = article.select_one("[itemprop='programmingLanguage']")
                language = lang_el.get_text(strip=True) if lang_el else None

                star_el = article.select_one("a[href$='/stargazers']")
                stars = 0
                if star_el:
                    star_txt = star_el.get_text(strip=True).replace(",", "")
                    stars = _parse_kilo(star_txt)

                owner, name = full_name.split("/", 1)
                raw.append(RawRepo(
                    full_name=full_name,
                    name=name,
                    owner=owner,
                    description=description,
                    url=f"https://github.com/{full_name}",
                    language=language,
                    stars=stars,
                    source="trending",
                ))
            except Exception as exc:
                logger.debug("Parse trending row failed: {}", exc)

        return raw

    # ── Source 2: GitHub Search API ────────────────────────────────────────

    @retry(max_attempts=3, delay=10.0, exceptions=(RateLimitExceededException, Exception))
    def _fetch_search(self, min_stars: int, limit: int) -> list[RawRepo]:
        repos: list[RawRepo] = []
        cutoff = (datetime.now(timezone.utc) - timedelta(days=90)).strftime("%Y-%m-%d")

        for query_tpl in self.SEARCH_QUERIES:
            query = query_tpl.format(date=cutoff)
            try:
                results = self._gh.search_repositories(
                    query=query,
                    sort="stars",
                    order="desc",
                )
                count = 0
                for repo in results:
                    if repo.stargazers_count < min_stars:
                        break
                    if repo.archived or repo.fork:
                        continue
                    repos.append(self._gh_repo_to_raw(repo, source="search"))
                    count += 1
                    if count >= limit // len(self.SEARCH_QUERIES) + 1:
                        break
                time.sleep(2)
            except RateLimitExceededException:
                logger.warning("GitHub rate limit hit — sleeping 60s")
                time.sleep(60)
            except Exception as exc:
                logger.debug("Search query '{}' failed: {}", query, exc)

            if len(repos) >= limit:
                break

        return repos[:limit]

    # ── Source 3: GitHub Topics ────────────────────────────────────────────

    @retry(max_attempts=3, delay=5.0, exceptions=(Exception,))
    def _fetch_topics(self, min_stars: int, limit: int) -> list[RawRepo]:
        repos: list[RawRepo] = []
        cutoff = (datetime.now(timezone.utc) - timedelta(days=60)).strftime("%Y-%m-%d")

        for topic in self.HOT_TOPICS:
            query = f"topic:{topic} stars:>{min_stars} pushed:>{cutoff}"
            try:
                results = self._gh.search_repositories(query=query, sort="stars", order="desc")
                count = 0
                for repo in results:
                    if repo.archived or repo.fork:
                        continue
                    repos.append(self._gh_repo_to_raw(repo, source=f"topic:{topic}"))
                    count += 1
                    if count >= 5:
                        break
                time.sleep(1.5)
            except Exception as exc:
                logger.debug("Topic '{}' failed: {}", topic, exc)

            if len(repos) >= limit:
                break

        return repos[:limit]

    # ── Enrich / full metadata ─────────────────────────────────────────────

    def _enrich_repos(self, stubs: list[RawRepo], source: str) -> list[RawRepo]:
        """Fill in full metadata for trending stubs via the API."""
        enriched: list[RawRepo] = []
        for stub in stubs:
            try:
                gh_repo = self._gh.get_repo(stub.full_name)
                enriched.append(self._gh_repo_to_raw(gh_repo, source=source))
                time.sleep(0.5)
            except Exception as exc:
                logger.debug("Enrichment failed for {}: {}", stub.full_name, exc)
                enriched.append(stub)
        return enriched

    def _gh_repo_to_raw(self, repo: Any, source: str) -> RawRepo:
        """Convert a PyGithub Repository object to RawRepo."""
        try:
            license_name = repo.license.name if repo.license else None
        except Exception:
            license_name = None

        try:
            contributors_count = repo.get_contributors(anon=False).totalCount
        except Exception:
            contributors_count = 0

        return RawRepo(
            full_name=repo.full_name,
            name=repo.name,
            owner=repo.owner.login,
            description=repo.description or "",
            url=repo.html_url,
            homepage=repo.homepage or "",
            topics=repo.get_topics() if hasattr(repo, "get_topics") else [],
            language=repo.language,
            license=license_name,
            stars=repo.stargazers_count,
            forks=repo.forks_count,
            watchers=repo.watchers_count,
            open_issues=repo.open_issues_count,
            contributors_count=contributors_count,
            created_at=repo.created_at.isoformat() if repo.created_at else None,
            updated_at=repo.updated_at.isoformat() if repo.updated_at else None,
            pushed_at=repo.pushed_at.isoformat() if repo.pushed_at else None,
            default_branch=repo.default_branch,
            is_archived=repo.archived,
            is_fork=repo.fork,
            source=source,
        )

    # ── Full README fetch ──────────────────────────────────────────────────

    def fetch_readme(self, full_name: str) -> str:
        """Fetch raw README content for a repository."""
        try:
            repo = self._gh.get_repo(full_name)
            readme = repo.get_readme()
            return base64.b64decode(readme.content).decode("utf-8", errors="replace")
        except Exception as exc:
            logger.debug("README fetch failed for {}: {}", full_name, exc)
            return ""

    def fetch_latest_release(self, full_name: str) -> str | None:
        """Return the latest release tag name, or None."""
        try:
            repo = self._gh.get_repo(full_name)
            release = repo.get_latest_release()
            return release.tag_name
        except Exception:
            return None

    def get_rate_limit(self) -> dict[str, Any]:
        try:
            rl = self._gh.get_rate_limit()
            return {
                "core_remaining": rl.core.remaining,
                "core_reset": rl.core.reset.isoformat(),
                "search_remaining": rl.search.remaining,
            }
        except Exception:
            return {}


# ── Helpers ────────────────────────────────────────────────────────────────

def _parse_kilo(text: str) -> int:
    """Parse '12.3k' → 12300, '1,234' → 1234."""
    text = text.strip().replace(",", "")
    if text.endswith("k"):
        return int(float(text[:-1]) * 1000)
    if text.endswith("m"):
        return int(float(text[:-1]) * 1_000_000)
    try:
        return int(text)
    except ValueError:
        return 0
