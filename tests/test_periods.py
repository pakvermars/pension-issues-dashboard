"""기간 키와 기간 범위 계산 테스트."""

import unittest
from datetime import date

import periods


class KeysForTest(unittest.TestCase):
    def test_returns_all_four_period_keys(self):
        self.assertEqual(
            periods.keys_for(date(2026, 9, 10)),
            {
                "daily": "2026-09-10",
                "weekly": "2026-W37",
                "monthly": "2026-09",
                "yearly": "2026",
            },
        )

    def test_week_belongs_to_next_iso_year_in_late_december(self):
        # 2025-12-29(월)은 ISO 기준 2026년 1주차에 속한다.
        keys = periods.keys_for(date(2025, 12, 29))
        self.assertEqual(keys["weekly"], "2026-W01")
        self.assertEqual(keys["yearly"], "2025")

    def test_week_belongs_to_previous_iso_year_in_early_january(self):
        # 2027-01-01(금)은 ISO 기준 2026년 53주차에 속한다.
        keys = periods.keys_for(date(2027, 1, 1))
        self.assertEqual(keys["weekly"], "2026-W53")
        self.assertEqual(keys["yearly"], "2027")


class DateRangeTest(unittest.TestCase):
    def test_daily_range_is_a_single_day(self):
        self.assertEqual(
            periods.date_range("daily", "2026-09-10"),
            (date(2026, 9, 10), date(2026, 9, 10)),
        )

    def test_weekly_range_runs_monday_to_sunday(self):
        self.assertEqual(
            periods.date_range("weekly", "2026-W37"),
            (date(2026, 9, 7), date(2026, 9, 13)),
        )

    def test_monthly_range_ends_on_last_day_of_month(self):
        self.assertEqual(
            periods.date_range("monthly", "2026-02"),
            (date(2026, 2, 1), date(2026, 2, 28)),
        )

    def test_yearly_range_covers_whole_year(self):
        self.assertEqual(
            periods.date_range("yearly", "2026"),
            (date(2026, 1, 1), date(2026, 12, 31)),
        )

    def test_unknown_period_raises(self):
        with self.assertRaises(ValueError):
            periods.date_range("hourly", "2026-09-10")


class LabelForTest(unittest.TestCase):
    def test_daily_label_includes_korean_weekday(self):
        self.assertEqual(periods.label_for("daily", "2026-09-10"), "2026-09-10 (목)")

    def test_weekly_label_shows_range(self):
        self.assertEqual(
            periods.label_for("weekly", "2026-W37"),
            "2026-W37 (2026-09-07 ~ 2026-09-13)",
        )

    def test_monthly_label_is_korean(self):
        self.assertEqual(periods.label_for("monthly", "2026-09"), "2026년 9월")

    def test_yearly_label_is_korean(self):
        self.assertEqual(periods.label_for("yearly", "2026"), "2026년")


if __name__ == "__main__":
    unittest.main()
