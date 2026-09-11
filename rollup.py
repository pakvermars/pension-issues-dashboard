"""일간 파일을 모아 주간·월간·연간 주요 이슈를 만든다.

사용법:
    python -X utf8 rollup.py            # 오늘 날짜 기준
    python -X utf8 rollup.py 2026-09-10 # 특정 날짜 기준
"""

from __future__ import annotations

import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import dedupe
import periods
import store

KST = timezone(timedelta(hours=9))

TOP_N = 20

ROLLUP_PERIODS = ("weekly", "monthly", "yearly")

# 긴 기간의 목록을 짧은 구간 하나가 독차지하지 않도록 상한을 둔다.
# 기사는 사건이 터진 주에 몰리기 마련이라, 이게 없으면 월간은 그 주의 사본이,
# 연간은 그 달의 사본이 된다. (기간, 나누는 단위, 단위당 최대 건수)
YEARLY_MONTH_CAP = 8
MONTHLY_WEEK_CAP = 12

SPREAD_CAPS = {
    "monthly": ("week", MONTHLY_WEEK_CAP),
    "yearly": ("month", YEARLY_MONTH_CAP),
}

# 사람이 바로잡은 병합·분리 지정을 담는 파일. data/ 아래에 둔다.
CORRECTIONS_FILE = "merges.json"


def cluster_score(group: list[dict]) -> tuple[int, int, str]:
    """주간 기준: 최고 중요도 → 보도된 기사 수 → 최신 게재일."""
    top_importance = max(item["importance"] for item in group)
    latest = max(item["published"] for item in group)
    return (top_importance, len(group), latest)


def persistence_score(group: list[dict]) -> tuple[int, int, int, str]:
    """월간·연간 기준: 며칠에 걸쳐 다뤄졌나를 먼저 본다.

    긴 기간에서 알고 싶은 것은 '그날 제일 큰 뉴스'가 아니라 '오래 간 이슈'다.
    같은 날 쏟아진 통신사 사본 여러 건보다, 사흘에 걸쳐 후속이 붙은 이슈를 위로 올린다.
    """
    days = len({item["published"] for item in group})
    top_importance = max(item["importance"] for item in group)
    latest = max(item["published"] for item in group)
    return (days, top_importance, len(group), latest)


SCORES = {
    "weekly": cluster_score,
    "monthly": persistence_score,
    "yearly": persistence_score,
}


def load_corrections(data_dir) -> dict[str, list[list[str]]]:
    """사람이 지정한 병합·분리 목록. 없으면 빈 값."""
    path = Path(data_dir) / CORRECTIONS_FILE
    if not path.is_file():
        return {"same": [], "different": []}
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {
        "same": raw.get("same", []),
        "different": raw.get("different", []),
    }


def _bucket_of(group: list[dict], unit: str) -> str:
    """묶음이 속한 구간. 대표 날짜는 가장 최근 게재일로 본다."""
    latest = max(item["published"] for item in group)
    if unit == "month":
        return latest[:7]
    return periods.keys_for(date.fromisoformat(latest))["weekly"]


def limit_spread(groups: list[list[dict]], unit: str, cap: int) -> list[list[dict]]:
    """구간별로 cap개까지만 남긴다. 순서는 그대로 유지한다."""
    counts: dict[str, int] = {}
    kept = []
    for group in groups:
        bucket = _bucket_of(group, unit)
        if counts.get(bucket, 0) >= cap:
            continue
        counts[bucket] = counts.get(bucket, 0) + 1
        kept.append(group)
    return kept


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
    period: str,
    key: str,
    dailies: list[dict],
    now: datetime | None = None,
    corrections: dict[str, list[list[str]]] | None = None,
) -> dict:
    """일간 문서 여러 개를 하나의 기간 문서로 만든다."""
    corrections = corrections or {"same": [], "different": []}
    items = [item for doc in dailies for item in doc.get("items", [])]

    groups = dedupe.cluster(
        items, same=corrections.get("same"), different=corrections.get("different")
    )
    groups.sort(key=SCORES.get(period, cluster_score), reverse=True)

    if period in SPREAD_CAPS:
        unit, cap = SPREAD_CAPS[period]
        groups = limit_spread(groups, unit, cap)

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
    corrections = load_corrections(data_dir)

    written = []
    for period in ROLLUP_PERIODS:
        key = keys[period]
        start, end = periods.date_range(period, key)
        doc = build_period(
            period,
            key,
            store.load_dailies(data_dir, start, end),
            now=now,
            corrections=corrections,
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
