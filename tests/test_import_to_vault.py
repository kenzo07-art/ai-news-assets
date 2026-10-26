import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "import_to_vault.py"


class ImportSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="news-import-test-")
        self.addCleanup(self.temp.cleanup)
        self.vault = Path(self.temp.name)
        self.git("init", "-q")
        self.git("config", "user.name", "Test")
        self.git("config", "user.email", "test@example.com")
        (self.vault / "unrelated.md").write_text("original\n")
        self.git("add", "unrelated.md")
        self.git("commit", "-q", "-m", "Initial")
        spec = importlib.util.spec_from_file_location("news_import", SCRIPT)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.module.VAULT = str(self.vault)
        self.module.LOG_DIR = str(self.vault / "log")

    def git(self, *args):
        return subprocess.check_output(
            ["git", *args], cwd=self.vault, text=True, stderr=subprocess.STDOUT
        ).strip()

    def test_commit_preserves_unrelated_staged_and_unstaged_changes(self):
        (self.vault / "unrelated.md").write_text("staged\n")
        self.git("add", "unrelated.md")
        (self.vault / "unrelated.md").write_text("unstaged\n")
        written = self.module.write_day_section("2026-10-27", "claude", "### News\n- Item")
        index = self.module.rebuild_index("2026-10")
        self.module.commit([written, index], "Import news")
        self.assertEqual(self.git("show", "HEAD:unrelated.md"), "original")
        self.assertEqual(self.git("show", ":unrelated.md"), "staged")
        self.assertEqual((self.vault / "unrelated.md").read_text(), "unstaged\n")
        changed = self.git("diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD")
        self.assertEqual(changed.splitlines(), ["log/2026-10.md", "log/2026-10/2026-10-27.md"])

    def test_pending_target_is_not_overwritten_or_committed(self):
        written = self.module.write_day_section("2026-10-27", "claude", "### Original")
        self.module.commit([written], "Import Claude")
        path = Path(written)
        path.write_text(path.read_text() + "\nHuman edit\n")
        before = path.read_bytes()
        with self.assertRaisesRegex(SystemExit, "pending changes in target"):
            self.module.write_day_section("2026-10-27", "codex", "### Codex")
        self.assertEqual(path.read_bytes(), before)

    def test_pending_index_is_not_overwritten(self):
        written = self.module.write_day_section("2026-10-27", "claude", "### Original")
        index = self.module.rebuild_index("2026-10")
        self.module.commit([written, index], "Import")
        path = Path(index)
        path.write_text(path.read_text() + "\nHuman edit\n")
        before = path.read_bytes()
        with self.assertRaisesRegex(SystemExit, "pending changes in target"):
            self.module.rebuild_index("2026-10")
        self.assertEqual(path.read_bytes(), before)

    def test_retry_does_not_duplicate_or_lose_either_side(self):
        day = "2026-10-27"
        path = self.module.write_day_section(day, "claude", "### Claude\n- Claude item")
        self.module.commit([path], "Claude")
        path = self.module.write_day_section(day, "codex", "### Codex\n- Codex item")
        self.module.commit([path], "Codex")
        before = Path(path).read_bytes()
        self.assertIsNone(self.module.write_day_section(day, "claude", "Replacement"))
        self.assertIsNone(self.module.write_day_section(day, "codex", "Replacement"))
        self.assertEqual(Path(path).read_bytes(), before)
        self.assertEqual(before.count(b"<!-- imported:"), 2)

    def test_dry_run_makes_no_files_or_history_changes(self):
        head = self.git("rev-parse", "HEAD")
        self.assertIsNone(self.module.write_day_section("2026-10-27", "claude", "News", True))
        self.assertFalse((self.vault / "log").exists())
        self.assertEqual(self.git("rev-parse", "HEAD"), head)

    def test_batch_conflict_is_found_before_any_day_is_written(self):
        day = "2026-10-28"
        path = Path(self.module.day_path(day))
        path.parent.mkdir(parents=True)
        path.write_text("Pending human note\n")
        with self.assertRaisesRegex(SystemExit, "pending changes in target"):
            self.module.preflight_targets(["2026-10-27", day])
        self.assertFalse(Path(self.module.day_path("2026-10-27")).exists())
        self.assertEqual(path.read_text(), "Pending human note\n")


if __name__ == "__main__":
    unittest.main()
