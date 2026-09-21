"""조회 시점을 기준으로 뒤를 돌아보는 네 기간의 키와 범위를 계산한다.

일간만 그날 하루를 보고, 주·월·연은 어제까지의 롤링 창이다. 달력 주·달력 월이
아니라서 "9월 21일에 보는 주간"은 9월 14일~20일이 된다. 오늘을 빼는 이유는
일간 탭이 이미 오늘을 보여주고 있기 때문이다.
"""

from __future__ import annotations

import calendar
from datetime import date, timedelta

PERIODS = ("daily", "weekly", "monthly", "yearly")

ROLLING_PERIODS = ("weekly", "monthly", "yearly")

# 롤링 기간은 창이 매번 달라져 달력 이름을 붙일 수 없다. 파일은 하나만 두고 덮어쓴다.
ROLLING_KEY = "current"

WEEKDAY_KO = ("월", "화", "수", "목", "금", "토", "일")


def _shift_back(d: date, *, years: int = 0, months: int = 0) -> date:
    """d에서 연·월을 되돌린 날짜. 그 달에 없는 날짜는 말일로 당겨 잡는다."""
    total = d.year * 12 + (d.month - 1) - years * 12 - months
    year, month = divmod(total, 12)
    month += 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def keys_for(d: date) -> dict[str, str]:
    """날짜 하나를 기준으로 삼은 네 기간의 키."""
    return {
        "daily": d.isoformat(),
        "weekly": ROLLING_KEY,
        "monthly": ROLLING_KEY,
        "yearly": ROLLING_KEY,
    }


def windows_for(d: date) -> dict[str, tuple[date, date]]:
    """d를 조회 시점으로 봤을 때 네 기간이 각각 덮는 첫날과 마지막 날."""
    yesterday = d - timedelta(days=1)
    return {
        "daily": (d, d),
        "weekly": (d - timedelta(days=7), yesterday),
        "monthly": (_shift_back(yesterday, months=1) + timedelta(days=1), yesterday),
        "yearly": (_shift_back(yesterday, years=1) + timedelta(days=1), yesterday),
    }


def iso_week_key(d: date) -> str:
    """날짜가 속한 ISO 주의 이름. 롤링 창 안에서 주 단위로 묶을 때 쓴다.

    화면에는 나오지 않는다. 긴 기간의 목록을 한 주가 독차지하지 않도록
    구간을 나누는 용도다.
    """
    iso = d.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def label_for(period: str, start: date, end: date) -> str:
    """화면에 표시할 기간 이름. 롤링 기간은 덮는 날짜 구간을 그대로 보여준다."""
    if period == "daily":
        return f"{start.isoformat()} ({WEEKDAY_KO[start.weekday()]})"
    if period in ROLLING_PERIODS:
        return f"{start.isoformat()} ~ {end.isoformat()}"
    raise ValueError(f"알 수 없는 기간: {period!r}")
