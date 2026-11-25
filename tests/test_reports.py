"""Tests for worklog.reports, focused on the yearly path."""

import datetime as dt
import os
import tempfile
import unittest
from unittest import mock

from worklog import reports, storage


class YearlyReportTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._old_home = os.environ.get("WORKLOG_HOME")
        os.environ["WORKLOG_HOME"] = self._tmp.name
        storage.write_day(dt.date(2026, 1, 5), ["Kickoff"])
        storage.write_day(dt.date(2026, 3, 10), ["Shipped v1", "Wrote docs"])

    def tearDown(self):
        if self._old_home is None:
            os.environ.pop("WORKLOG_HOME", None)
        else:
            os.environ["WORKLOG_HOME"] = self._old_home
        self._tmp.cleanup()

    def test_yearly_report_condenses_each_logged_month(self):
        prompts = []

        def fake_complete(system, prompt, cfg):
            prompts.append(prompt)
            return "- digest" if prompt.startswith("Condense") else "## Year in review\nGood year."

        with mock.patch.object(reports.ai, "complete", side_effect=fake_complete):
            label, md = reports.generate_report("yearly", "2026", cfg={})

        self.assertEqual(label, "2026")
        self.assertEqual(len(prompts), 3)  # January digest, March digest, final report
        self.assertIn("### January 2026", prompts[-1])
        self.assertIn("### March 2026", prompts[-1])
        self.assertNotIn("### February 2026", prompts[-1])
        self.assertIn("# Yearly Work Report - 2026", md)
        self.assertIn("Good year.", md)

    def test_yearly_report_without_entries_raises(self):
        with self.assertRaises(ValueError) as ctx:
            reports.generate_report("yearly", "1999", cfg={})
        self.assertEqual(str(ctx.exception), "No log entries found for 1999.")

    def test_yearly_raw_deck_has_one_slide_per_logged_month(self):
        label, stats, entries, deck = reports.raw_deck("yearly", "2026")
        self.assertEqual(label, "2026")
        self.assertEqual([s["title"] for s in deck["slides"]], ["January", "March"])
        self.assertEqual(stats["days_logged"], 2)
        self.assertEqual(stats["entries"], 3)
        self.assertIn("Shipped v1", deck["slides"][1]["bullets"][0])

    def test_yearly_raw_deck_caps_month_bullets(self):
        storage.write_day(
            dt.date(2026, 5, 1), [f"entry {i}" for i in range(9)]
        )
        _label, _stats, _entries, deck = reports.raw_deck("yearly", "2026")
        may = next(s for s in deck["slides"] if s["title"] == "May")
        self.assertEqual(len(may["bullets"]), 7)
        self.assertEqual(may["bullets"][-1], "...and 3 more entries")


if __name__ == "__main__":
    unittest.main()
