"""기간 파일을 읽어 index.html을 만든다.

사용법:
    python -X utf8 build.py
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import periods
import store

KST = timezone(timedelta(hours=9))

ROOT = Path(__file__).resolve().parent

PLACEHOLDER = "/*__DATA__*/"


def empty_doc(period: str, key: str) -> dict:
    """아직 파일이 없는 기간을 채울 빈 문서."""
    return {
        "period": period,
        "key": key,
        "label": periods.label_for(period, key),
        "generated_at": "",
        "item_count": 0,
        "shortfall_note": "아직 수집된 이슈가 없습니다.",
        "items": [],
    }


def latest_daily_date(data_dir) -> date | None:
    """가장 최근 일간 파일의 날짜. 파일이 없으면 None."""
    daily_dir = Path(data_dir) / "daily"
    if not daily_dir.is_dir():
        return None

    days = []
    for path in daily_dir.glob("*.json"):
        try:
            days.append(date.fromisoformat(path.stem))
        except ValueError:
            continue
    return max(days) if days else None


def collect(data_dir, day: date) -> dict:
    """day가 속한 네 기간의 문서를 모은다. 없는 기간은 빈 문서로 채운다."""
    data_dir = Path(data_dir)
    docs = {}
    for period, key in periods.keys_for(day).items():
        path = data_dir / period / f"{key}.json"
        docs[period] = store.load(path) if path.exists() else empty_doc(period, key)
    return docs


def render(template: str, docs: dict, now: datetime) -> str:
    """템플릿의 자리표시자를 실제 데이터로 바꾼다."""
    payload = {"built_at": now.isoformat(timespec="minutes"), "periods": docs}
    encoded = json.dumps(payload, ensure_ascii=False)
    # '<'를 이스케이프해 데이터 안의 문자열이 script 태그를 닫지 못하게 한다.
    encoded = encoded.replace("<", "\\u003c")
    return template.replace(PLACEHOLDER, encoded)


def main() -> int:
    data_dir = ROOT / "data"
    day = latest_daily_date(data_dir) or datetime.now(KST).date()
    template = (ROOT / "template.html").read_text(encoding="utf-8")
    html = render(template, collect(data_dir, day), datetime.now(KST))

    output = ROOT / "index.html"
    output.write_text(html, encoding="utf-8")
    print(f"작성: {output} (기준일 {day.isoformat()})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
