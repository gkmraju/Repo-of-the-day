from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from services.storage import Storage


class StorageTests(TestCase):
    def test_history_and_cache_round_trip(self) -> None:
        with TemporaryDirectory() as temp_dir:
            storage = Storage(temp_dir)

            storage.mark_as_sent(
                "example/project",
                "https://github.com/example/project",
                {"language": "Python", "topics": ["automation", "python"]},
            )
            storage.set_cache("daily", {"winner": "example/project"})

            self.assertTrue(storage.is_already_sent("example/project"))
            self.assertEqual(storage.total_sent(), 1)
            self.assertEqual(
                storage.get_cached("daily"),
                {"winner": "example/project"},
            )
            self.assertEqual(
                storage.get_history_summary()["languages"],
                {"Python": 1},
            )

    def test_corrupt_files_return_safe_empty_values(self) -> None:
        with TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir)
            (data_dir / "sent_repositories.json").write_text("not json")
            (data_dir / "repository_cache.json").write_text("not json")
            storage = Storage(temp_dir)

            self.assertEqual(storage.get_sent_repos(), [])
            self.assertEqual(storage.get_cache(), {})

    def test_clear_cache_preserves_history(self) -> None:
        with TemporaryDirectory() as temp_dir:
            storage = Storage(temp_dir)
            storage.mark_as_sent("example/project", "https://example.com/project")
            storage.set_cache("key", "value")

            storage.clear_cache()

            self.assertEqual(storage.get_cache(), {})
            self.assertEqual(storage.total_sent(), 1)
