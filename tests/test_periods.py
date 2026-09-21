"""기간 키와 조회 시점 기준 기간 창 계산 테스트."""

import unittest
from datetime import date

import periods


class KeysForTest(unittest.TestCase):
    def test_daily_is_dated_and_rolling_periods_share_one_key(self):
        self.assertEqual(
            periods.keys_for(date(2026, 9, 21)),
            {
                "daily": "2026-09-21",
                "weekly": "current",
                "monthly": "current",
                "yearly": "current",
            },
        )


class WindowsForTest(unittest.TestCase):
    def test_daily_window_is_the_day_itself(self):
        self.assertEqual(
            periods.windows_for(date(2026, 9, 21))["daily"],
            (date(2026, 9, 21), date(2026, 9, 21)),
        )

    def test_weekly_window_is_the_seven_days_before_today(self):
        self.assertEqual(
            periods.windows_for(date(2026, 9, 21))["weekly"],
            (date(2026, 9, 14), date(2026, 9, 20)),
        )

    def test_monthly_window_runs_from_a_month_back_to_yesterday(self):
        self.assertEqual(
            periods.windows_for(date(2026, 9, 21))["monthly"],
            (date(2026, 8, 21), date(2026, 9, 20)),
        )

    def test_yearly_window_runs_from_a_year_back_to_yesterday(self):
        self.assertEqual(
            periods.windows_for(date(2026, 9, 21))["yearly"],
            (date(2025, 9, 21), date(2026, 9, 20)),
        )

    def test_weekly_window_crosses_the_year_boundary(self):
        self.assertEqual(
            periods.windows_for(date(2026, 1, 1))["weekly"],
            (date(2025, 12, 25), date(2025, 12, 31)),
        )

    def test_monthly_window_clamps_when_the_earlier_month_is_shorter(self):
        # 어제가 3-30이고 2월에는 30일이 없다. 2-28로 당겨 잡아 3-01부터 센다.
        self.assertEqual(
            periods.windows_for(date(2026, 3, 31))["monthly"],
            (date(2026, 3, 1), date(2026, 3, 30)),
        )

    def test_yearly_window_clamps_on_a_leap_day(self):
        # 어제가 2028-02-29이고 2027년에는 2-29가 없다. 2-28로 당겨 잡는다.
        self.assertEqual(
            periods.windows_for(date(2028, 3, 1))["yearly"],
            (date(2027, 3, 1), date(2028, 2, 29)),
        )


class IsoWeekKeyTest(unittest.TestCase):
    """롤링 창 안에서 한 주가 목록을 독차지하지 않게 묶을 때 쓰는 구간 이름."""

    def test_days_in_the_same_week_share_a_key(self):
        self.assertEqual(
            periods.iso_week_key(date(2026, 9, 7)),
            periods.iso_week_key(date(2026, 9, 13)),
        )

    def test_the_next_monday_starts_a_new_key(self):
        self.assertNotEqual(
            periods.iso_week_key(date(2026, 9, 13)),
            periods.iso_week_key(date(2026, 9, 14)),
        )

    def test_late_december_can_belong_to_the_next_iso_year(self):
        # 2025-12-29(월)은 ISO 기준 2026년 1주차다.
        self.assertEqual(periods.iso_week_key(date(2025, 12, 29)), "2026-W01")


class LabelForTest(unittest.TestCase):
    def test_daily_label_includes_korean_weekday(self):
        self.assertEqual(
            periods.label_for("daily", date(2026, 9, 21), date(2026, 9, 21)),
            "2026-09-21 (월)",
        )

    def test_rolling_label_shows_the_window_it_covers(self):
        self.assertEqual(
            periods.label_for("weekly", date(2026, 9, 14), date(2026, 9, 20)),
            "2026-09-14 ~ 2026-09-20",
        )

    def test_yearly_label_shows_both_years(self):
        self.assertEqual(
            periods.label_for("yearly", date(2025, 9, 21), date(2026, 9, 20)),
            "2025-09-21 ~ 2026-09-20",
        )

    def test_unknown_period_raises(self):
        with self.assertRaises(ValueError):
            periods.label_for("hourly", date(2026, 9, 21), date(2026, 9, 21))


if __name__ == "__main__":
    unittest.main()
