"""
app.py — Repo Of The Day main orchestrator.

Usage:
  python app.py                    # Normal run (post to Telegram)
  python app.py --dry-run          # Generate content, skip Telegram
  python app.py --force OWNER/REPO # Analyse a specific repo
  python app.py --stats            # Show posting history stats
  python app.py --clear-cache      # Reset the discovery cache
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# ── Import services (after env is loaded) ──────────────────────────────────
from config import get_settings
from services.github_service import GitHubService, RawRepo
from services.image_generator import ImageGenerator
from services.logger import logger, setup_logger
from services.markdown_formatter import MarkdownFormatter
from services.repository_analyzer import RepositoryAnalyzer
from services.repository_ranker import RepositoryRanker
from services.storage import Storage
from services.summarizer import Summarizer
from services.telegram_service import TelegramService


# ── HTML report generator ──────────────────────────────────────────────────

def generate_html_report(repo: object, reports_dir: str = "reports") -> str:
    """Render the Jinja2 HTML report and save to disk."""
    try:
        from jinja2 import Environment, FileSystemLoader
        env = Environment(loader=FileSystemLoader("templates"))
        template = env.get_template("html_report.jinja2")
        now_str = datetime.now().strftime("%B %d, %Y at %H:%M IST")
        html = template.render(repo=repo, now=now_str)

        out_dir = Path(reports_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        slug = getattr(repo, "full_name", "unknown").replace("/", "_")
        date = datetime.now().strftime("%Y-%m-%d")
        out_path = out_dir / f"{date}_{slug}.html"
        out_path.write_text(html, encoding="utf-8")
        logger.info("HTML report saved: {}", out_path)
        return str(out_path)
    except Exception as exc:
        logger.warning("HTML report generation failed: {}", exc)
        return ""


# ── Core pipeline ──────────────────────────────────────────────────────────

def run(
    dry_run: bool = False,
    force_repo: str | None = None,
    verbose: bool = False,
) -> int:
    """
    Main pipeline.  Returns 0 on success, 1 on error.
    """
    start = time.perf_counter()
    settings = get_settings()
    setup_logger(settings.logs_dir, level="DEBUG" if verbose else "INFO")

    logger.info("=" * 60)
    logger.info("Repo Of The Day  —  {}  (dry_run={})", datetime.now().isoformat(), dry_run)
    logger.info("=" * 60)

    # ── Initialise services ────────────────────────────────────────────────
    storage = Storage(settings.data_dir)
    github  = GitHubService(settings.github_token, settings.request_timeout)
    ranker  = RepositoryRanker(settings.weights)
    summ    = Summarizer()
    analyzer = RepositoryAnalyzer(github, ranker, summ)
    formatter = MarkdownFormatter()
    img_gen = ImageGenerator(settings.assets_dir)
    telegram = TelegramService(
        settings.telegram_bot_token,
        settings.telegram_chat_id,
    )

    # ── Rate limit check ───────────────────────────────────────────────────
    rl = github.get_rate_limit()
    if rl:
        logger.info("GitHub API — core remaining: {}, search remaining: {}",
                    rl.get("core_remaining"), rl.get("search_remaining"))
        if rl.get("core_remaining", 100) < 20:
            logger.error("GitHub rate limit nearly exhausted. Aborting.")
            return 1

    # ── Step 1: Discover or use forced repo ───────────────────────────────
    if force_repo:
        logger.info("Force mode: analysing {}", force_repo)
        try:
            gh_repo = github._gh.get_repo(force_repo)
            raw_repos = [github._gh_repo_to_raw(gh_repo, source="forced")]
        except Exception as exc:
            logger.error("Cannot fetch forced repo {}: {}", force_repo, exc)
            return 1
    else:
        logger.info("Discovering repositories…")
        raw_repos = github.discover_repos(
            min_stars=settings.min_stars,
            max_per_source=settings.max_repos_per_source,
        )
        if not raw_repos:
            logger.error("No repositories discovered. Check GitHub token and network.")
            return 1

    # ── Step 2: Filter already-sent ───────────────────────────────────────
    sent = storage.get_sent_repo_urls()
    logger.info("History: {} repos already sent", len(sent))

    if not force_repo:
        filtered = [r for r in raw_repos if r.full_name not in sent and not r.is_archived and not r.is_fork]
        logger.info("After filtering: {} candidate repos", len(filtered))
        if not filtered:
            logger.warning("All discovered repos already sent — expanding search…")
            filtered = [r for r in raw_repos if not r.is_archived]
            if not filtered:
                logger.error("No fresh repos available.")
                return 1
    else:
        filtered = raw_repos

    # ── Step 3: Score and rank ─────────────────────────────────────────────
    logger.info("Scoring {} repos…", len(filtered))
    scored = ranker.rank(filtered)

    # Log top-5
    logger.info("Top 5 scored repos:")
    for rank_i, (repo, score) in enumerate(scored[:5], 1):
        logger.info("  #{}: {} — {:.1f}", rank_i, repo.full_name, score)

    winner_raw, winner_score = scored[0]
    logger.info("SELECTED: {} (score={:.1f})", winner_raw.full_name, winner_score)

    # ── Step 4: Full analysis ─────────────────────────────────────────────
    logger.info("Analysing {}…", winner_raw.full_name)
    repo = analyzer.analyze(winner_raw)

    # ── Step 5: Generate thumbnail ────────────────────────────────────────
    logger.info("Generating thumbnail…")
    try:
        thumbnail_path = img_gen.generate(repo)
        repo.thumbnail_path = thumbnail_path
    except Exception as exc:
        logger.error("Thumbnail generation failed: {}", exc)
        thumbnail_path = ""

    # ── Step 6: Format message ────────────────────────────────────────────
    logger.info("Formatting Telegram message…")
    message_chunks = formatter.format(repo)
    logger.info("{} message chunk(s), total {} chars",
                len(message_chunks), sum(len(c) for c in message_chunks))

    # ── Step 7: Generate HTML report ─────────────────────────────────────
    generate_html_report(repo, settings.reports_dir)

    # ── Step 8: Post to Telegram (skip in dry-run) ────────────────────────
    if dry_run:
        logger.info("DRY-RUN — skipping Telegram posting")
        logger.info("First message chunk preview:\n{}", message_chunks[0][:500])
    else:
        # Verify bot connectivity first
        if not telegram.test_connection():
            logger.error("Telegram connection failed — aborting.")
            return 1

        logger.info("Posting to Telegram…")
        caption = f"🚀 *Repo Of The Day* — {repo.full_name}"
        try:
            if thumbnail_path and Path(thumbnail_path).exists():
                results = telegram.send_photo_with_messages(
                    thumbnail_path, message_chunks, caption
                )
            else:
                results = telegram.send_text_only(message_chunks)
            logger.info("Posted {} messages successfully", len(results))
        except Exception as exc:
            logger.error("Telegram posting failed: {}", exc)
            return 1

        # ── Step 9: Mark as sent ──────────────────────────────────────────
        storage.mark_as_sent(
            repo_full_name=repo.full_name,
            repo_url=repo.url,
            metadata={
                "name": repo.name,
                "language": repo.language,
                "stars": repo.stars,
                "topics": repo.topics[:5],
                "score": repo.score,
            },
        )

    elapsed = time.perf_counter() - start
    logger.info("=" * 60)
    logger.info("Done in {:.1f}s  |  Repo: {}  |  Score: {:.1f}",
                elapsed, repo.full_name, repo.score)
    logger.info("=" * 60)
    return 0


# ── CLI ────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="repo_of_the_day",
        description="Discover, analyse, and post the best GitHub repo of the day to Telegram.",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Generate content but do NOT post to Telegram.",
    )
    parser.add_argument(
        "--force", metavar="OWNER/REPO",
        help="Skip discovery and analyse a specific repository.",
    )
    parser.add_argument(
        "--stats", action="store_true",
        help="Print posting history statistics and exit.",
    )
    parser.add_argument(
        "--clear-cache", action="store_true",
        help="Clear the discovery cache and exit.",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Enable DEBUG-level logging.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    # Handle simple utility commands first
    if args.stats:
        from config import get_settings
        from services.storage import Storage
        setup_logger()
        settings = get_settings()
        storage = Storage(settings.data_dir)
        summary = storage.get_history_summary()
        print(f"\n{'='*40}")
        print(f"  Repo Of The Day — History Stats")
        print(f"{'='*40}")
        print(f"  Total sent:   {summary['total_sent']}")
        if summary["last_posted"]:
            lp = summary["last_posted"]
            print(f"  Last posted:  {lp.get('full_name')} on {lp.get('posted_at','?')[:10]}")
        if summary["languages"]:
            print(f"  Top languages: {', '.join(list(summary['languages'].keys())[:5])}")
        print(f"{'='*40}\n")
        sys.exit(0)

    if args.clear_cache:
        from config import get_settings
        from services.storage import Storage
        setup_logger()
        settings = get_settings()
        Storage(settings.data_dir).clear_cache()
        print("Cache cleared.")
        sys.exit(0)

    # Determine dry-run mode
    dry = args.dry_run or get_settings().dry_run

    exit_code = run(
        dry_run=dry,
        force_repo=args.force,
        verbose=args.verbose,
    )
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
