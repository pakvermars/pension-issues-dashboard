"""일간·주간·월간·연간 기간 키와 그 범위를 계산한다."""

from __future__ import annotations

import calendar
from datetime import date

PERIODS = ("daily", "weekly", "monthly", "yearly")

WEEKDAY_KO = ("월", "화", "수", "목", "금", "토", "일")


def keys_for(d: date) -> dict[str, str]:
    """날짜 하나가 속하는 네 기간의 키를 돌려준다.

    주 키는 ISO 8601 기준이라 연말·연초에는 달력 연도와 다를 수 있다.
    """
    iso = d.isocalendar()
    return {
        "daily": d.isoformat(),
        "weekly": f"{iso.year}-W{iso.week:02d}",
        "monthly": f"{d.year}-{d.month:02d}",
        "yearly": f"{d.year}",
    }


def date_range(period: str, key: str) -> tuple[date, date]:
    """기간 키가 포함하는 첫날과 마지막 날을 돌려준다."""
    if period == "daily":
        day = date.fromisoformat(key)
        return day, day
    if period == "weekly":
        year, week = key.split("-W")
        return (
            date.fromisocalendar(int(year), int(week), 1),
            date.fromisocalendar(int(year), int(week), 7),
        )
    if period == "monthly":
        year, month = (int(part) for part in key.split("-"))
        last_day = calendar.monthrange(year, month)[1]
        return date(year, month, 1), date(year, month, last_day)
    if period == "yearly":
        year = int(key)
        return date(year, 1, 1), date(year, 12, 31)
    raise ValueError(f"알 수 없는 기간: {period!r}")


def label_for(period: str, key: str) -> str:
    """화면에 표시할 기간 이름."""
    start, end = date_range(period, key)
    if period == "daily":
        return f"{start.isoformat()} ({WEEKDAY_KO[start.weekday()]})"
    if period == "weekly":
        return f"{key} ({start.isoformat()} ~ {end.isoformat()})"
    if period == "monthly":
        return f"{start.year}년 {start.month}월"
    return f"{start.year}년"
