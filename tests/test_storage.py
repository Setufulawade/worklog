"""Tests for worklog.storage: day-file round-tripping and aggregation."""

import datetime as dt
import os
import tempfile
import unittest
from pathlib import Path

from worklog import storage


class StorageTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._old_home = os.environ.get("WORKLOG_HOME")
        os.environ["WORKLOG_HOME"] = self._tmp.name
        self.root = Path(self._tmp.name)

    def tearDown(self):
        if self._old_home is None:
            os.environ.pop("WORKLOG_HOME", None)
        else:
            os.environ["WORKLOG_HOME"] = self._old_home
        self._tmp.cleanup()

    def test_day_file_layout(self):
        self.assertEqual(
            storage.day_file(dt.date(2026, 11, 20)),
            self.root / "logs" / "2026" / "2026-11-20.txt",
        )

    def test_empty_day_reads_as_empty_list(self):
        self.assertEqual(storage.read_day(dt.date(2026, 11, 20)), [])

    def test_append_and_read(self):
        d = dt.date(2026, 11, 20)
        self.assertEqual(storage.append_lines(d, [" one ", "two"]), 2)
        self.assertEqual(storage.read_day(d), ["one", "two"])
        self.assertEqual(storage.append_lines(d, ["three"]), 1)
        self.assertEqual(storage.read_day(d), ["one", "two", "three"])

    def test_blank_lines_are_ignored(self):
        d = dt.date(2026, 11, 20)
        self.assertEqual(storage.append_lines(d, ["", "   ", "\n"]), 0)
        self.assertFalse(storage.day_file(d).exists())
        self.assertEqual(storage.append_lines(d, ["", "real", " "]), 1)
        self.assertEqual(storage.read_day(d), ["real"])

    def test_write_day_replaces_contents(self):
        d = dt.date(2026, 11, 20)
        storage.write_day(d, ["a", "b"])
        storage.write_day(d, ["c"])
        self.assertEqual(storage.read_day(d), ["c"])

    def test_writing_nothing_deletes_the_file(self):
        d = dt.date(2026, 11, 20)
        storage.write_day(d, ["a"])
        self.assertTrue(storage.day_file(d).exists())
        storage.write_day(d, [])
        self.assertFalse(storage.day_file(d).exists())

    def test_days_with_logs_scoped_to_month(self):
        storage.write_day(dt.date(2026, 11, 2), ["a", "b"])
        storage.write_day(dt.date(2026, 11, 20), ["c"])
        storage.write_day(dt.date(2026, 10, 31), ["old"])
        storage.write_day(dt.date(2025, 11, 5), ["older"])

        found = storage.days_with_logs(2026, 11)
        self.assertEqual(
            found, {dt.date(2026, 11, 2): 2, dt.date(2026, 11, 20): 1}
        )

    def test_days_with_logs_ignores_stray_files(self):
        folder = self.root / "logs" / "2026"
        folder.mkdir(parents=True)
        (folder / "not-a-date.txt").write_text("junk\n", encoding="utf-8")
        self.assertEqual(storage.days_with_logs(2026, 11), {})

    def test_days_with_logs_missing_year(self):
        self.assertEqual(storage.days_with_logs(1999, 1), {})

    def test_entries_between_skips_empty_days_and_sorts(self):
        storage.write_day(dt.date(2026, 11, 3), ["third"])
        storage.write_day(dt.date(2026, 11, 1), ["first"])
        entries = storage.entries_between(dt.date(2026, 11, 1), dt.date(2026, 11, 5))
        self.assertEqual(
            entries, {dt.date(2026, 11, 1): ["first"], dt.date(2026, 11, 3): ["third"]}
        )
        self.assertEqual(list(entries), sorted(entries))

    def test_format_entries(self):
        entries = {
            dt.date(2026, 11, 2): ["did a thing", "did another"],
            dt.date(2026, 11, 3): ["shipped it"],
        }
        text = storage.format_entries(entries)
        self.assertIn("2026-11-02 (Monday)", text)
        self.assertIn("  - did a thing", text)
        self.assertIn("2026-11-03 (Tuesday)", text)
        self.assertTrue(text.endswith("\n"))

    def test_format_entries_empty(self):
        self.assertEqual(storage.format_entries({}), "")

    def test_config_dir_follows_home_override(self):
        self.assertEqual(storage.config_dir(), self.root)


if __name__ == "__main__":
    unittest.main()
