from unittest import TestCase
from unittest.mock import patch

from services.github_service import RawRepo, _parse_kilo
from services.repository_ranker import RepositoryRanker


def make_repo(**overrides: object) -> RawRepo:
    values: dict[str, object] = {
        "full_name": "example/healthy",
        "name": "healthy",
        "owner": "example",
        "description": "A useful project",
        "url": "https://github.com/example/healthy",
        "homepage": "https://example.com",
        "topics": ["python", "automation", "open-source"],
        "language": "Python",
        "license": "MIT",
        "stars": 50_000,
        "forks": 5_000,
        "watchers": 10_000,
        "open_issues": 500,
        "contributors_count": 100,
        "pushed_at": "2026-08-17T00:00:00+00:00",
        "is_archived": False,
        "is_fork": False,
        "source": "test",
    }
    values.update(overrides)
    return RawRepo(**values)


class RepositoryRankerTests(TestCase):
    @patch("services.repository_ranker.days_ago", return_value=1)
    def test_documented_active_repository_outscores_sparse_one(self, _days_ago) -> None:
        ranker = RepositoryRanker()
        complete_readme = (
            "installation usage example features license contributing screenshot quick start "
            * 300
        )
        sparse = make_repo(
            full_name="example/sparse",
            homepage="",
            topics=[],
            license=None,
            stars=10,
            forks=0,
            watchers=0,
            open_issues=0,
            contributors_count=0,
        )

        self.assertGreater(
            ranker.score(make_repo(), complete_readme),
            ranker.score(sparse, "short"),
        )

    def test_non_unit_weights_are_normalized(self) -> None:
        ranker = RepositoryRanker(weights={"stars": 2.0, "recent_activity": 1.0})
        repo = make_repo(pushed_at=None)

        self.assertEqual(ranker.score(repo), 66.67)

    @patch("services.repository_ranker.days_ago", return_value=7)
    def test_activity_boundary_is_fully_scored(self, _days_ago) -> None:
        self.assertEqual(RepositoryRanker._score_activity("ignored"), 1.0)

    @patch("services.repository_ranker.days_ago", return_value=365)
    def test_stale_activity_boundary_scores_zero(self, _days_ago) -> None:
        self.assertEqual(RepositoryRanker._score_activity("ignored"), 0.0)

    def test_growth_signal_handles_ratio_bands(self) -> None:
        score = RepositoryRanker._score_growth

        self.assertEqual(score(0, 10), 0.0)
        self.assertEqual(score(1_000, 20), 0.3)
        self.assertEqual(score(1_000, 100), 1.0)
        self.assertEqual(score(1_000, 400), 0.7)
        self.assertEqual(score(1_000, 600), 0.4)

    @patch("services.repository_ranker.days_ago", return_value=1)
    def test_rank_returns_descending_scores(self, _days_ago) -> None:
        ranker = RepositoryRanker(weights={"stars": 1.0})
        repos = [
            make_repo(full_name="example/small", stars=10),
            make_repo(full_name="example/large", stars=50_000),
        ]

        ranked = ranker.rank(repos)

        self.assertEqual(ranked[0][0].full_name, "example/large")
        self.assertGreater(ranked[0][1], ranked[1][1])


class GitHubParsingTests(TestCase):
    def test_parse_kilo_handles_compact_and_invalid_counts(self) -> None:
        self.assertEqual(_parse_kilo("12.3k"), 12_300)
        self.assertEqual(_parse_kilo("1.2m"), 1_200_000)
        self.assertEqual(_parse_kilo("1,234"), 1_234)
        self.assertEqual(_parse_kilo("unknown"), 0)
