"""Tests for worklog.cli output paths."""

import contextlib
import datetime as dt
import io
import os
import tempfile
import unittest

from worklog import cli, storage


class CliViewTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._old_home = os.environ.get("WORKLOG_HOME")
        os.environ["WORKLOG_HOME"] = self._tmp.name
        storage.write_day(dt.date(2026, 1, 5), ["Kickoff"])
        storage.write_day(dt.date(2026, 1, 6), ["Planning", "Review"])
        storage.write_day(dt.date(2026, 11, 20), ["Ship"])

    def tearDown(self):
        if self._old_home is None:
            os.environ.pop("WORKLOG_HOME", None)
        else:
            os.environ["WORKLOG_HOME"] = self._old_home
        self._tmp.cleanup()

    def run_cli(self, *argv):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = cli.main(list(argv))
        return code, buf.getvalue()

    def test_view_day(self):
        code, out = self.run_cli("view", "-d", "2026-01-06")
        self.assertEqual(code, 0)
        self.assertIn("Tuesday, 06 January 2026", out)
        self.assertIn("   1. Planning", out)
        self.assertIn("   2. Review", out)

    def test_view_year_groups_by_month(self):
        code, out = self.run_cli("view", "--year", "2026")
        self.assertEqual(code, 0)
        self.assertIn("2026  (3 days logged, 4 entries)", out)
        self.assertIn("January 2026  (2 days, 3 entries)", out)
        self.assertIn("November 2026  (1 day, 1 entry)", out)
        self.assertIn("  2026-01-05 (Monday)", out)
        self.assertIn("    - Kickoff", out)
        self.assertLess(out.index("January 2026"), out.index("November 2026"))

    def test_view_year_summary_prints_only_totals(self):
        code, out = self.run_cli("view", "-y", "2026", "--summary")
        self.assertEqual(code, 0)
        self.assertIn("2026  (3 days logged, 4 entries)", out)
        self.assertIn("January 2026  (2 days, 3 entries)", out)
        self.assertIn("November 2026  (1 day, 1 entry)", out)
        self.assertNotIn("Kickoff", out)
        self.assertNotIn("    - ", out)

    def test_view_year_without_entries(self):
        code, out = self.run_cli("view", "--year", "2025")
        self.assertEqual(code, 0)
        self.assertEqual(out, "2025\n  (no entries)\n")

    def test_summary_requires_year(self):
        with self.assertRaises(SystemExit) as ctx:
            self.run_cli("view", "--summary")
        self.assertEqual(str(ctx.exception), "--summary can only be used with --year.")

    def test_year_shortcut_shows_year_view(self):
        code, out = self.run_cli("year", "2026")
        self.assertEqual(code, 0)
        self.assertIn("2026  (3 days logged, 4 entries)", out)
        self.assertIn("    - Kickoff", out)

    def test_year_shortcut_summary(self):
        code, out = self.run_cli("yr", "2026", "--summary")
        self.assertEqual(code, 0)
        self.assertIn("January 2026  (2 days, 3 entries)", out)
        self.assertNotIn("Kickoff", out)

    def test_year_shortcut_writes_report(self):
        from worklog import reports
        from unittest import mock

        out_path = os.path.join(self._tmp.name, "out", "2026.md")
        with mock.patch.object(reports.ai, "complete", return_value="## Year in review"):
            code, out = self.run_cli("year", "2026", "--summary", "--report", "-o", out_path)
        self.assertEqual(code, 0)
        self.assertIn("## Year in review", out)
        with open(out_path, encoding="utf-8") as fh:
            self.assertIn("## Year in review", fh.read())

    def test_year_shortcut_builds_deck_without_ai(self):
        import importlib.util

        if importlib.util.find_spec("pptx") is None:
            self.skipTest("python-pptx is not installed")
        out_path = os.path.join(self._tmp.name, "out", "2026.pptx")
        code, out = self.run_cli("year", "2026", "--summary", "--ppt", "--no-ai", "-o", out_path)
        self.assertEqual(code, 0)
        self.assertIn("Created", out)
        self.assertTrue(os.path.getsize(out_path) > 0)

    def test_year_shortcut_rejects_no_ai_without_ppt(self):
        with self.assertRaises(SystemExit) as ctx:
            self.run_cli("year", "2026", "--no-ai")
        self.assertEqual(str(ctx.exception), "--no-ai can only be used with --ppt.")

    def test_year_shortcut_rejects_output_without_artifact(self):
        with self.assertRaises(SystemExit) as ctx:
            self.run_cli("year", "2026", "-o", "x.md")
        self.assertEqual(str(ctx.exception), "--output requires --report or --ppt.")


if __name__ == "__main__":
    unittest.main()
