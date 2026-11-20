"""Tests for worklog.dates: date parsing and period ranges."""

import datetime as dt
import unittest

from worklog.dates import daterange, month_range, parse_date, week_range, year_range

TODAY = dt.date(2026, 11, 20)  # a Friday


class ParseDateTest(unittest.TestCase):
    def test_named_days(self):
        self.assertEqual(parse_date("today", TODAY), TODAY)
        self.assertEqual(parse_date("", TODAY), TODAY)
        self.assertEqual(parse_date("yesterday", TODAY), dt.date(2026, 11, 19))
        self.assertEqual(parse_date("tomorrow", TODAY), dt.date(2026, 11, 21))

    def test_offsets(self):
        self.assertEqual(parse_date("-3", TODAY), dt.date(2026, 11, 17))
        self.assertEqual(parse_date("+1", TODAY), dt.date(2026, 11, 21))

    def test_explicit_formats(self):
        expected = dt.date(2026, 11, 3)
        for text in ("2026-11-03", "03-11-2026", "03/11/2026", "2026/11/03"):
            self.assertEqual(parse_date(text, TODAY), expected, text)

    def test_rejects_garbage(self):
        for text in ("not-a-date", "2026-13-01", "32-01-2026"):
            with self.assertRaises(ValueError):
                parse_date(text, TODAY)


class WeekRangeTest(unittest.TestCase):
    def test_this_week_starts_monday(self):
        start, end, label = week_range("this", TODAY)
        self.assertEqual(start, dt.date(2026, 11, 16))
        self.assertEqual(end, dt.date(2026, 11, 22))
        self.assertIn("Week 47, 2026", label)

    def test_last_week(self):
        start, end, _ = week_range("last", TODAY)
        self.assertEqual(start, dt.date(2026, 11, 9))
        self.assertEqual(end, dt.date(2026, 11, 15))

    def test_explicit_iso_week(self):
        start, end, _ = week_range("2026-W01", TODAY)
        self.assertEqual(start, dt.date(2025, 12, 29))
        self.assertEqual(end, dt.date(2026, 1, 4))

    def test_any_date_inside_the_week(self):
        start, _, _ = week_range("2026-11-18", TODAY)
        self.assertEqual(start, dt.date(2026, 11, 16))


class MonthRangeTest(unittest.TestCase):
    def test_this_month(self):
        start, end, label = month_range("this", TODAY)
        self.assertEqual(start, dt.date(2026, 11, 1))
        self.assertEqual(end, dt.date(2026, 11, 30))
        self.assertEqual(label, "November 2026")

    def test_last_month_crosses_year(self):
        start, end, _ = month_range("last", dt.date(2026, 1, 15))
        self.assertEqual(start, dt.date(2025, 12, 1))
        self.assertEqual(end, dt.date(2025, 12, 31))

    def test_december_rollover(self):
        start, end, _ = month_range("2026-12", TODAY)
        self.assertEqual(start, dt.date(2026, 12, 1))
        self.assertEqual(end, dt.date(2026, 12, 31))

    def test_rejects_bad_spec(self):
        with self.assertRaises(ValueError):
            month_range("next", TODAY)


class YearRangeTest(unittest.TestCase):
    def test_full_year(self):
        self.assertEqual(year_range("this", TODAY), (dt.date(2026, 1, 1), dt.date(2026, 12, 31), "2026"))
        self.assertEqual(year_range("last", TODAY)[0], dt.date(2025, 1, 1))
        self.assertEqual(year_range("2024", TODAY)[2], "2024")

    def test_rejects_bad_spec(self):
        with self.assertRaises(ValueError):
            year_range("soon", TODAY)


class DaterangeTest(unittest.TestCase):
    def test_inclusive_range(self):
        days = list(daterange(dt.date(2026, 11, 1), dt.date(2026, 11, 3)))
        self.assertEqual(
            days, [dt.date(2026, 11, 1), dt.date(2026, 11, 2), dt.date(2026, 11, 3)]
        )

    def test_single_day(self):
        d = dt.date(2026, 11, 1)
        self.assertEqual(list(daterange(d, d)), [d])


if __name__ == "__main__":
    unittest.main()
