"""일간 파일을 모아 주간·월간·연간 주요 이슈를 만든다.

사용법:
    python -X utf8 rollup.py            # 오늘 날짜 기준
    python -X utf8 rollup.py 2026-09-10 # 특정 날짜 기준
"""

from __future__ import annotations

import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import dedupe
import periods
import store

KST = timezone(timedelta(hours=9))

TOP_N = 20

ROLLUP_PERIODS = ("weekly", "monthly", "yearly")


def cluster_score(group: list[dict]) -> tuple[int, int, str]:
    """묶음 순위: 최고 중요도 → 보도된 기사 수 → 최신 게재일."""
    top_importance = max(item["importance"] for item in group)
    latest = max(item["published"] for item in group)
    return (top_importance, len(group), latest)


def merge(group: list[dict]) -> dict:
    """묶음을 대표 기사 1건으로 접고 나머지는 related에 담는다.

    같은 기사가 여러 번 수집될 수 있으므로(하루 여러 번 실행, 기간 겹침)
    대표 기사와 URL이 같은 것은 related에서 뺀다. 기사가 자기 자신을
    관련 기사로 달고 있으면 안 된다.
    """
    lead, rest = group[0], group[1:]

    seen = {dedupe.make_id(lead["url"])}
    related = []
    for item in rest:
        item_id = dedupe.make_id(item["url"])
        if item_id in seen:
            continue
        seen.add(item_id)
        related.append(
            {"title": item["title"], "source": item["source"], "url": item["url"]}
        )

    merged = dict(lead)
    merged["related"] = related
    return merged


def build_period(
    period: str, key: str, dailies: list[dict], now: datetime | None = None
) -> dict:
    """일간 문서 여러 개를 하나의 기간 문서로 만든다."""
    items = [item for doc in dailies for item in doc.get("items", [])]
    groups = sorted(dedupe.cluster(items), key=cluster_score, reverse=True)
    selected = [merge(group) for group in groups[:TOP_N]]

    generated = (now or datetime.now(KST)).isoformat(timespec="seconds")
    shortfall = (
        None
        if len(selected) >= TOP_N
        else f"이 기간에 모인 이슈는 {len(selected)}건입니다."
    )
    return {
        "period": period,
        "key": key,
        "label": periods.label_for(period, key),
        "generated_at": generated,
        "item_count": len(selected),
        "shortfall_note": shortfall,
        "items": selected,
    }


def rollup(data_dir, day: date, now: datetime | None = None) -> list[Path]:
    """day가 속한 주·월·연 파일을 다시 만들고 쓴 경로를 돌려준다."""
    data_dir = Path(data_dir)
    keys = periods.keys_for(day)

    written = []
    for period in ROLLUP_PERIODS:
        key = keys[period]
        start, end = periods.date_range(period, key)
        doc = build_period(
            period, key, store.load_dailies(data_dir, start, end), now=now
        )
        path = data_dir / period / f"{key}.json"
        store.save(path, doc)
        written.append(path)
    return written


def main(argv: list[str]) -> int:
    day = date.fromisoformat(argv[1]) if len(argv) > 1 else datetime.now(KST).date()
    for path in rollup(Path(__file__).resolve().parent / "data", day):
        print(f"작성: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
