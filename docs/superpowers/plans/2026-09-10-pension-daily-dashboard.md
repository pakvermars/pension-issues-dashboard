# 퇴직연금 주요 이슈 데일리 대시보드 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 매일 자동으로 퇴직연금·연금 주요 이슈 10건을 수집·요약해, 일간/주간/월간/연간 탭으로 볼 수 있는 단일 웹 화면(`index.html`)을 만든다.

**Architecture:** 데이터와 화면을 분리한다. 뉴스는 날짜별 JSON으로 `data/daily/`에 누적되고, `rollup.py`가 그 파일들을 모아 주간·월간·연간 파일을 만든다. `build.py`는 네 기간 파일을 읽어 `template.html`에 데이터를 인라인으로 주입해 `index.html`을 생성한다. 뉴스 수집·요약은 코드가 아니라 Claude가 런북(`daily_update.md`)을 따라 수행한다.

**Tech Stack:** Python 3.12 표준 라이브러리만 (json, difflib, hashlib, datetime, calendar, urllib, unittest). 화면은 의존성 없는 HTML + 바닐라 JS.

**Spec:** `docs/superpowers/specs/2026-09-10-pension-daily-dashboard-design.md`

## Global Constraints

- **외부 패키지 설치 금지.** Python 3.12 표준 라이브러리만 사용한다. 테스트는 `unittest`.
- **모든 파이썬 실행에 `-X utf8`을 붙인다.** Windows 콘솔 기본 인코딩이 cp949라 한글 출력이 깨진다. 예: `python -X utf8 rollup.py`
- **모든 파일은 UTF-8.** 파이썬에서 파일을 읽고 쓸 때 항상 `encoding="utf-8"`을 명시한다.
- **카테고리는 정확히 3종:** `제도·규제`, `업계·경쟁사`, `가입자·사회`. 가운뎃점은 U+00B7(`·`)이다.
- **TOP_N = 10.** 기간별 선정 건수.
- **시간대는 KST(UTC+9).** `timezone(timedelta(hours=9))`.
- **주 경계는 ISO 8601** — 월요일 시작, 일요일 종료. 주 키는 `YYYY-Www`.
- **`index.html`은 `file://`에서 단독 동작해야 한다.** 외부 네트워크 요청(CDN, 폰트, fetch) 금지. 데이터는 파일 안에 인라인으로 넣는다.
- **화면에 보이는 모든 문구는 한국어.**
- **테스트 실행 명령(프로젝트 루트에서):** `python -X utf8 -m unittest discover -s tests -t . -v`

---

### Task 1: 프로젝트 뼈대와 기간 계산 (`periods.py`)

기간 키(일간/주간/월간/연간) 계산은 이후 모든 모듈이 의존하므로 가장 먼저 만든다. 연말·연초에 ISO 주가 해를 넘나드는 것이 유일한 함정이다.

**Files:**
- Create: `periods.py`
- Create: `tests/__init__.py` (빈 파일)
- Create: `tests/test_periods.py`
- Create: `.gitignore`

**Interfaces:**
- Consumes: 없음
- Produces:
  - `PERIODS: tuple[str, ...]` = `("daily", "weekly", "monthly", "yearly")`
  - `keys_for(d: date) -> dict[str, str]` — 네 기간의 키
  - `date_range(period: str, key: str) -> tuple[date, date]` — 기간의 첫날과 마지막 날
  - `label_for(period: str, key: str) -> str` — 화면 표시용 기간 이름

- [ ] **Step 1: git 저장소 초기화와 `.gitignore` 작성**

프로젝트 루트(`퇴직연금 주요 이슈`)에서 실행:

```bash
git init
```

`.gitignore`:

```
__pycache__/
*.pyc
.DS_Store
Thumbs.db
```

- [ ] **Step 2: 실패하는 테스트 작성**

`tests/__init__.py`는 빈 파일로 만든다.

`tests/test_periods.py`:

```python
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
```

- [ ] **Step 3: 테스트가 실패하는지 확인**

Run: `python -X utf8 -m unittest discover -s tests -t . -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'periods'`

- [ ] **Step 4: `periods.py` 구현**

```python
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
```

- [ ] **Step 5: 테스트 통과 확인**

Run: `python -X utf8 -m unittest discover -s tests -t . -v`
Expected: PASS — 12 tests OK

- [ ] **Step 6: 커밋**

```bash
git add .gitignore periods.py tests/__init__.py tests/test_periods.py
git commit -m "feat: 일간/주간/월간/연간 기간 키 계산 추가"
```

---

### Task 2: 데이터 저장소와 스키마 검증 (`store.py`)

기간 파일을 읽고 쓰는 유일한 통로. 잘못된 데이터가 파일에 들어가면 화면이 조용히 깨지므로, 저장 시점에 검증해서 막는다.

**Files:**
- Create: `store.py`
- Create: `tests/test_store.py`

**Interfaces:**
- Consumes: 없음
- Produces:
  - `CATEGORIES: tuple[str, str, str]` = `("제도·규제", "업계·경쟁사", "가입자·사회")`
  - `ITEM_FIELDS: tuple[str, ...]` — 기사 필수 필드 이름
  - `item_errors(item: dict) -> list[str]` — 기사 1건의 문제 목록 (빈 리스트면 정상)
  - `doc_errors(doc: dict) -> list[str]` — 기간 문서의 문제 목록
  - `save(path, doc: dict) -> None` — 검증 후 UTF-8 JSON으로 저장. `item_count`를 자동으로 채운다. 문제가 있으면 `ValueError`
  - `load(path) -> dict`
  - `load_dailies(data_dir, start: date, end: date) -> list[dict]` — 범위 안의 일간 문서를 날짜 순으로

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_store.py`:

```python
"""기간 파일 검증과 입출력 테스트."""

import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

import store


def sample_item(**overrides):
    item = {
        "id": "abc123def456",
        "title": "퇴직연금 디폴트옵션 수익률 공시",
        "summary": "고용노동부가 디폴트옵션 상품별 수익률을 공시했다. 원리금보장형이 3%대를 기록했다. 실적배당형은 상품별 편차가 컸다.",
        "category": "제도·규제",
        "importance": 4,
        "source": "한국경제",
        "published": "2026-09-10",
        "url": "https://example.com/news/1",
    }
    item.update(overrides)
    return item


def sample_doc(**overrides):
    doc = {
        "period": "daily",
        "key": "2026-09-10",
        "label": "2026-09-10 (목)",
        "generated_at": "2026-09-10T07:40:00+09:00",
        "item_count": 1,
        "shortfall_note": None,
        "items": [sample_item()],
    }
    doc.update(overrides)
    return doc


class ItemErrorsTest(unittest.TestCase):
    def test_valid_item_has_no_errors(self):
        self.assertEqual(store.item_errors(sample_item()), [])

    def test_missing_required_field_is_reported(self):
        item = sample_item()
        del item["summary"]
        self.assertIn("필수 항목 누락: summary", store.item_errors(item))

    def test_unknown_category_is_reported(self):
        errors = store.item_errors(sample_item(category="기타"))
        self.assertTrue(any("카테고리" in message for message in errors))

    def test_importance_out_of_range_is_reported(self):
        errors = store.item_errors(sample_item(importance=7))
        self.assertTrue(any("중요도" in message for message in errors))

    def test_url_without_scheme_is_reported(self):
        errors = store.item_errors(sample_item(url="example.com/news/1"))
        self.assertTrue(any("원문 링크" in message for message in errors))

    def test_bad_published_date_is_reported(self):
        errors = store.item_errors(sample_item(published="2026/09/10"))
        self.assertTrue(any("게재일" in message for message in errors))


class SaveLoadTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_save_then_load_round_trips(self):
        path = self.root / "daily" / "2026-09-10.json"
        store.save(path, sample_doc())
        self.assertEqual(store.load(path)["key"], "2026-09-10")

    def test_saved_file_keeps_korean_readable(self):
        path = self.root / "daily" / "2026-09-10.json"
        store.save(path, sample_doc())
        self.assertIn("퇴직연금", path.read_text(encoding="utf-8"))

    def test_save_fills_item_count(self):
        path = self.root / "daily" / "2026-09-10.json"
        store.save(path, sample_doc(item_count=99))
        self.assertEqual(store.load(path)["item_count"], 1)

    def test_save_rejects_invalid_document(self):
        path = self.root / "daily" / "bad.json"
        with self.assertRaises(ValueError):
            store.save(path, sample_doc(items=[sample_item(importance=0)]))
        self.assertFalse(path.exists())

    def test_save_creates_missing_directories(self):
        path = self.root / "weekly" / "2026-W37.json"
        store.save(path, sample_doc(period="weekly", key="2026-W37"))
        self.assertTrue(path.exists())


class LoadDailiesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        for day in ("2026-09-06", "2026-09-08", "2026-09-10", "2026-09-20"):
            store.save(self.root / "daily" / f"{day}.json", sample_doc(key=day))
        (self.root / "daily" / "메모.json").write_text("{}", encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_only_documents_inside_range_are_loaded(self):
        docs = store.load_dailies(self.root, date(2026, 9, 7), date(2026, 9, 13))
        self.assertEqual([doc["key"] for doc in docs], ["2026-09-08", "2026-09-10"])

    def test_files_without_a_date_name_are_skipped(self):
        docs = store.load_dailies(self.root, date(2026, 1, 1), date(2026, 12, 31))
        self.assertEqual(len(docs), 4)

    def test_missing_daily_directory_returns_empty_list(self):
        empty = Path(self.tmp.name) / "없음"
        self.assertEqual(store.load_dailies(empty, date(2026, 1, 1), date(2026, 12, 31)), [])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

Run: `python -X utf8 -m unittest tests.test_store -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'store'`

- [ ] **Step 3: `store.py` 구현**

```python
"""기간 파일(JSON)의 검증과 입출력을 담당한다."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

CATEGORIES = ("제도·규제", "업계·경쟁사", "가입자·사회")

ITEM_FIELDS = (
    "id",
    "title",
    "summary",
    "category",
    "importance",
    "source",
    "published",
    "url",
)

DOC_FIELDS = ("period", "key", "label", "generated_at", "items")


def item_errors(item: dict) -> list[str]:
    """기사 1건에서 발견된 문제를 한국어 메시지 목록으로 돌려준다."""
    errors = []
    for field in ITEM_FIELDS:
        if item.get(field) in (None, ""):
            errors.append(f"필수 항목 누락: {field}")

    if item.get("category") not in CATEGORIES:
        errors.append(f"카테고리가 잘못됨: {item.get('category')!r}")

    importance = item.get("importance")
    if not isinstance(importance, int) or not 1 <= importance <= 5:
        errors.append(f"중요도는 1~5 사이 정수여야 함: {importance!r}")

    url = str(item.get("url", ""))
    if not url.startswith(("http://", "https://")):
        errors.append(f"원문 링크가 http(s)로 시작하지 않음: {url!r}")

    try:
        date.fromisoformat(str(item.get("published")))
    except ValueError:
        errors.append(f"게재일 형식이 잘못됨: {item.get('published')!r}")

    return errors


def doc_errors(doc: dict) -> list[str]:
    """기간 문서 전체에서 발견된 문제를 돌려준다."""
    errors = [f"필수 항목 누락: {field}" for field in DOC_FIELDS if field not in doc]
    for index, item in enumerate(doc.get("items", [])):
        errors.extend(f"items[{index}]: {message}" for message in item_errors(item))
    return errors


def save(path, doc: dict) -> None:
    """검증을 통과한 문서만 UTF-8 JSON으로 저장한다."""
    errors = doc_errors(doc)
    if errors:
        raise ValueError("저장할 수 없는 문서입니다: " + "; ".join(errors))

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(doc, item_count=len(doc["items"]))
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def load(path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_dailies(data_dir, start: date, end: date) -> list[dict]:
    """start~end 사이에 실제로 존재하는 일간 문서를 날짜 순으로 읽는다."""
    daily_dir = Path(data_dir) / "daily"
    if not daily_dir.is_dir():
        return []

    docs = []
    for path in sorted(daily_dir.glob("*.json")):
        try:
            day = date.fromisoformat(path.stem)
        except ValueError:
            continue  # 날짜 이름이 아닌 파일은 건너뛴다
        if start <= day <= end:
            docs.append(load(path))
    return docs
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -X utf8 -m unittest discover -s tests -t . -v`
Expected: PASS — 25 tests OK

- [ ] **Step 5: 커밋**

```bash
git add store.py tests/test_store.py
git commit -m "feat: 기간 파일 검증과 입출력 추가"
```

---

### Task 3: 중복 기사 묶기 (`dedupe.py`)

같은 사건을 여러 매체가 보도하거나 속보 뒤에 후속 기사가 나오면, 주간·월간 목록이 같은 이야기로 채워진다. URL이 같거나 제목이 충분히 비슷한 기사를 하나로 묶는다.

**Files:**
- Create: `dedupe.py`
- Create: `tests/test_dedupe.py`

**Interfaces:**
- Consumes: 없음
- Produces:
  - `SIMILARITY_THRESHOLD: float` = `0.72`
  - `normalize_url(url: str) -> str` — 추적 파라미터·`www.`·끝 슬래시를 제거한 정규화 URL
  - `make_id(url: str) -> str` — 정규화 URL의 SHA-1 앞 12자
  - `title_key(title: str) -> str` — 한글/영문/숫자만 남긴 소문자 문자열
  - `similarity(a: str, b: str) -> float` — 제목 유사도 0.0~1.0
  - `cluster(items: list[dict], threshold: float = SIMILARITY_THRESHOLD) -> list[list[dict]]` — 각 묶음은 중요도 내림차순, 동점이면 게재일 오름차순으로 정렬

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_dedupe.py`:

```python
"""URL 정규화와 기사 묶기 테스트."""

import unittest

import dedupe


def article(title, url, importance=3, published="2026-09-10"):
    return {
        "title": title,
        "url": url,
        "importance": importance,
        "published": published,
        "source": "테스트일보",
    }


class NormalizeUrlTest(unittest.TestCase):
    def test_strips_tracking_parameters(self):
        self.assertEqual(
            dedupe.normalize_url("https://n.example.com/a/1?utm_source=naver&id=7"),
            "https://n.example.com/a/1?id=7",
        )

    def test_strips_www_and_trailing_slash_and_upgrades_scheme(self):
        self.assertEqual(
            dedupe.normalize_url("http://www.Example.com/news/1/"),
            "https://example.com/news/1",
        )

    def test_keeps_root_path(self):
        self.assertEqual(dedupe.normalize_url("https://example.com/"), "https://example.com/")


class MakeIdTest(unittest.TestCase):
    def test_same_article_different_tracking_gets_same_id(self):
        first = dedupe.make_id("https://www.example.com/news/1?utm_medium=social")
        second = dedupe.make_id("http://example.com/news/1")
        self.assertEqual(first, second)

    def test_different_articles_get_different_ids(self):
        self.assertNotEqual(
            dedupe.make_id("https://example.com/news/1"),
            dedupe.make_id("https://example.com/news/2"),
        )

    def test_id_is_twelve_characters(self):
        self.assertEqual(len(dedupe.make_id("https://example.com/news/1")), 12)


class SimilarityTest(unittest.TestCase):
    def test_follow_up_headline_is_similar(self):
        score = dedupe.similarity(
            "퇴직연금 디폴트옵션 수익률 공시, 원리금보장형 3%대",
            "[속보] 디폴트옵션 수익률 공시…원리금보장형 3%대 기록",
        )
        self.assertGreater(score, dedupe.SIMILARITY_THRESHOLD)

    def test_unrelated_headline_is_not_similar(self):
        score = dedupe.similarity(
            "퇴직연금 디폴트옵션 수익률 공시, 원리금보장형 3%대",
            "국민연금 개혁안 국회 통과",
        )
        self.assertLess(score, dedupe.SIMILARITY_THRESHOLD)


class ClusterTest(unittest.TestCase):
    def test_similar_titles_are_grouped_and_others_separated(self):
        items = [
            article("퇴직연금 디폴트옵션 수익률 공시, 원리금보장형 3%대", "https://a.com/1"),
            article("[속보] 디폴트옵션 수익률 공시…원리금보장형 3%대 기록", "https://b.com/2"),
            article("국민연금 개혁안 국회 통과", "https://c.com/3"),
        ]
        groups = dedupe.cluster(items)
        self.assertEqual(sorted(len(group) for group in groups), [1, 2])

    def test_same_url_is_grouped_even_with_different_titles(self):
        items = [
            article("퇴직연금 적립금 400조 돌파", "https://a.com/news/9"),
            article("전혀 다른 제목이 붙은 같은 기사", "https://www.a.com/news/9?utm_source=x"),
        ]
        self.assertEqual(len(dedupe.cluster(items)), 1)

    def test_group_leader_is_the_most_important_article(self):
        items = [
            article("퇴직연금 디폴트옵션 수익률 공시, 원리금보장형 3%대", "https://a.com/1", importance=2),
            article("[속보] 디폴트옵션 수익률 공시…원리금보장형 3%대 기록", "https://b.com/2", importance=5),
        ]
        group = dedupe.cluster(items)[0]
        self.assertEqual(group[0]["url"], "https://b.com/2")

    def test_empty_input_returns_empty_list(self):
        self.assertEqual(dedupe.cluster([]), [])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

Run: `python -X utf8 -m unittest tests.test_dedupe -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'dedupe'`

- [ ] **Step 3: `dedupe.py` 구현**

```python
"""같은 사건을 다룬 기사를 하나로 묶는다."""

from __future__ import annotations

import difflib
import hashlib
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

TRACKING_PREFIXES = ("utm_", "fbclid", "gclid", "igshid", "ref")

SIMILARITY_THRESHOLD = 0.72

_KEEP_ONLY = re.compile(r"[^0-9A-Za-z가-힣]+")


def normalize_url(url: str) -> str:
    """추적 파라미터와 표기 차이를 걷어낸 비교용 URL."""
    parts = urlsplit(url.strip())
    host = parts.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    query = [
        (key, value)
        for key, value in parse_qsl(parts.query)
        if not key.lower().startswith(TRACKING_PREFIXES)
    ]
    path = parts.path.rstrip("/") or "/"
    return urlunsplit(("https", host, path, urlencode(query), ""))


def make_id(url: str) -> str:
    """정규화한 URL로 만든 12자리 식별자."""
    digest = hashlib.sha1(normalize_url(url).encode("utf-8")).hexdigest()
    return digest[:12]


def title_key(title: str) -> str:
    """비교용으로 기호와 공백을 걷어낸 제목."""
    return _KEEP_ONLY.sub("", title).lower()


def similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, title_key(a), title_key(b)).ratio()


def cluster(items: list[dict], threshold: float = SIMILARITY_THRESHOLD) -> list[list[dict]]:
    """URL이 같거나 제목이 충분히 비슷한 기사끼리 묶는다.

    각 묶음은 중요도가 높은 기사가 앞에 오도록 정렬해 돌려준다.
    """
    groups: list[list[dict]] = []
    for item in items:
        for group in groups:
            if any(_is_same_story(existing, item, threshold) for existing in group):
                group.append(item)
                break
        else:
            groups.append([item])

    return [
        sorted(group, key=lambda item: (-item["importance"], item["published"]))
        for group in groups
    ]


def _is_same_story(a: dict, b: dict, threshold: float) -> bool:
    if make_id(a["url"]) == make_id(b["url"]):
        return True
    return similarity(a["title"], b["title"]) >= threshold
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -X utf8 -m unittest discover -s tests -t . -v`
Expected: PASS — 37 tests OK

- [ ] **Step 5: 커밋**

```bash
git add dedupe.py tests/test_dedupe.py
git commit -m "feat: 중복·후속 기사 묶기 추가"
```

---

### Task 4: 기간별 집계 (`rollup.py`)

일간 파일들을 모아 주간·월간·연간 TOP 10을 만든다. 묶음 점수는 결정적이어야 같은 입력에 같은 결과가 나온다.

점수 기준(내림차순): ① 묶음 안 최고 중요도 ② 묶인 기사 수 ③ 가장 최근 게재일.

**Files:**
- Create: `rollup.py`
- Create: `tests/test_rollup.py`

**Interfaces:**
- Consumes: `periods.keys_for`, `periods.date_range`, `periods.label_for`, `store.load_dailies`, `store.save`, `dedupe.cluster`
- Produces:
  - `KST: timezone`, `TOP_N: int` = `10`
  - `cluster_score(group: list[dict]) -> tuple[int, int, str]`
  - `merge(group: list[dict]) -> dict` — 대표 기사 1건 + `related` 목록
  - `build_period(period: str, key: str, dailies: list[dict], now: datetime | None = None) -> dict`
  - `rollup(data_dir: Path, day: date, now: datetime | None = None) -> list[Path]` — 주간·월간·연간 3개 파일을 쓰고 경로 목록을 돌려준다
  - `main(argv: list[str]) -> int` — CLI 진입점

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_rollup.py`:

```python
"""일간 파일을 모아 기간별 TOP 10을 만드는 로직 테스트."""

import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path

import rollup
import store

FIXED_NOW = datetime(2026, 9, 10, 7, 40, tzinfo=rollup.KST)

# 서로 묶이지 않도록 유사도가 충분히 낮은 제목들 (최대 0.4, 임계값 0.72).
DISTINCT_TITLES = [
    "퇴직연금 적립금 400조 돌파",
    "국민연금 개혁안 국회 통과",
    "디폴트옵션 원리금보장형 쏠림 심화",
    "은행권 IRP 수수료 인하 경쟁",
    "증권사 퇴직연금 점유율 확대",
    "TDF 순자산 사상 최대",
    "중도인출 사유 주택구입이 최다",
    "기금형 퇴직연금 도입 논의 재점화",
    "보험사 퇴직연금 시장 이탈 가속",
    "고용노동부 감독규정 개정 예고",
    "연금 수령 비중 소폭 상승",
    "로보어드바이저 일임 서비스 확대",
    "DB형 최소적립비율 미달 사업장 증가",
    "퇴직연금 실물이전 제도 시행",
    "고령층 노후소득 실태조사 발표",
]


def item(title, url, importance=3, published="2026-09-10", category="제도·규제"):
    return {
        "id": url[-6:].rjust(12, "0"),
        "title": title,
        "summary": "요약 문장 하나. 요약 문장 둘. 요약 문장 셋.",
        "category": category,
        "importance": importance,
        "source": "테스트일보",
        "published": published,
        "url": url,
    }


def daily_doc(key, items):
    return {
        "period": "daily",
        "key": key,
        "label": key,
        "generated_at": "2026-09-10T07:40:00+09:00",
        "item_count": len(items),
        "shortfall_note": None,
        "items": items,
    }


class ClusterScoreTest(unittest.TestCase):
    def test_score_uses_top_importance_then_count_then_recency(self):
        group = [
            item("가", "https://a.com/1", importance=5, published="2026-09-08"),
            item("가 후속", "https://b.com/2", importance=2, published="2026-09-10"),
        ]
        self.assertEqual(rollup.cluster_score(group), (5, 2, "2026-09-10"))


class MergeTest(unittest.TestCase):
    def test_leader_is_kept_and_rest_move_into_related(self):
        group = [
            item("디폴트옵션 수익률 공시", "https://a.com/1", importance=5),
            item("디폴트옵션 수익률 공시 후속", "https://b.com/2", importance=2),
        ]
        merged = rollup.merge(group)
        self.assertEqual(merged["url"], "https://a.com/1")
        self.assertEqual(merged["related"], [
            {"title": "디폴트옵션 수익률 공시 후속", "source": "테스트일보", "url": "https://b.com/2"}
        ])

    def test_single_article_gets_empty_related(self):
        merged = rollup.merge([item("혼자", "https://a.com/1")])
        self.assertEqual(merged["related"], [])


class BuildPeriodTest(unittest.TestCase):
    def test_duplicate_stories_across_days_collapse_into_one(self):
        dailies = [
            daily_doc("2026-09-08", [item("퇴직연금 디폴트옵션 수익률 공시, 원리금보장형 3%대", "https://a.com/1", importance=4, published="2026-09-08")]),
            daily_doc("2026-09-10", [item("[속보] 디폴트옵션 수익률 공시…원리금보장형 3%대 기록", "https://b.com/2", importance=5, published="2026-09-10")]),
        ]
        doc = rollup.build_period("weekly", "2026-W37", dailies, now=FIXED_NOW)
        self.assertEqual(doc["item_count"], 1)
        self.assertEqual(len(doc["items"][0]["related"]), 1)

    def test_items_are_ordered_by_score(self):
        dailies = [daily_doc("2026-09-10", [
            item("은행권 IRP 수수료 인하 경쟁", "https://a.com/1", importance=2),
            item("국민연금 개혁안 국회 통과", "https://b.com/2", importance=5),
            item("TDF 순자산 사상 최대", "https://c.com/3", importance=3),
        ])]
        doc = rollup.build_period("weekly", "2026-W37", dailies, now=FIXED_NOW)
        self.assertEqual(
            [i["title"] for i in doc["items"]],
            ["국민연금 개혁안 국회 통과", "TDF 순자산 사상 최대", "은행권 IRP 수수료 인하 경쟁"],
        )

    def test_at_most_ten_items_are_selected(self):
        items = [
            item(title, f"https://a.com/{n}", importance=3)
            for n, title in enumerate(DISTINCT_TITLES)
        ]
        doc = rollup.build_period("monthly", "2026-09", [daily_doc("2026-09-10", items)], now=FIXED_NOW)
        self.assertEqual(doc["item_count"], 10)
        self.assertIsNone(doc["shortfall_note"])

    def test_shortfall_note_is_set_when_fewer_than_ten(self):
        doc = rollup.build_period("weekly", "2026-W37", [daily_doc("2026-09-10", [item("하나", "https://a.com/1")])], now=FIXED_NOW)
        self.assertIn("1건", doc["shortfall_note"])

    def test_empty_input_produces_empty_document(self):
        doc = rollup.build_period("yearly", "2026", [], now=FIXED_NOW)
        self.assertEqual(doc["items"], [])
        self.assertEqual(doc["label"], "2026년")
        self.assertEqual(doc["generated_at"], "2026-09-10T07:40:00+09:00")


class RollupTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        store.save(self.root / "daily" / "2026-09-08.json",
                   daily_doc("2026-09-08", [item("퇴직연금 적립금 400조 돌파", "https://a.com/1", published="2026-09-08")]))
        store.save(self.root / "daily" / "2026-09-10.json",
                   daily_doc("2026-09-10", [item("국민연금 개혁안 국회 통과", "https://b.com/2", published="2026-09-10")]))
        store.save(self.root / "daily" / "2026-08-20.json",
                   daily_doc("2026-08-20", [item("디폴트옵션 수익률 공시", "https://c.com/3", published="2026-08-20")]))

    def tearDown(self):
        self.tmp.cleanup()

    def test_writes_three_period_files(self):
        written = rollup.rollup(self.root, date(2026, 9, 10), now=FIXED_NOW)
        self.assertEqual(
            sorted(path.name for path in written),
            ["2026-09.json", "2026-W37.json", "2026.json"],
        )

    def test_weekly_excludes_days_outside_the_week(self):
        rollup.rollup(self.root, date(2026, 9, 10), now=FIXED_NOW)
        weekly = store.load(self.root / "weekly" / "2026-W37.json")
        self.assertEqual(
            sorted(i["title"] for i in weekly["items"]),
            ["국민연금 개혁안 국회 통과", "퇴직연금 적립금 400조 돌파"],
        )

    def test_yearly_includes_every_day_of_the_year(self):
        rollup.rollup(self.root, date(2026, 9, 10), now=FIXED_NOW)
        yearly = store.load(self.root / "yearly" / "2026.json")
        self.assertEqual(yearly["item_count"], 3)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

Run: `python -X utf8 -m unittest tests.test_rollup -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'rollup'`

- [ ] **Step 3: `rollup.py` 구현**

```python
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

TOP_N = 10

ROLLUP_PERIODS = ("weekly", "monthly", "yearly")


def cluster_score(group: list[dict]) -> tuple[int, int, str]:
    """묶음 순위: 최고 중요도 → 보도된 기사 수 → 최신 게재일."""
    top_importance = max(item["importance"] for item in group)
    latest = max(item["published"] for item in group)
    return (top_importance, len(group), latest)


def merge(group: list[dict]) -> dict:
    """묶음을 대표 기사 1건으로 접고 나머지는 related에 담는다."""
    lead, rest = group[0], group[1:]
    merged = dict(lead)
    merged["related"] = [
        {"title": item["title"], "source": item["source"], "url": item["url"]}
        for item in rest
    ]
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
        doc = build_period(period, key, store.load_dailies(data_dir, start, end), now=now)
        path = data_dir / period / f"{key}.json"
        store.save(path, doc)
        written.append(path)
    return written


def main(argv: list[str]) -> int:
    day = date.fromisoformat(argv[1]) if len(argv) > 1 else datetime.now(KST).date()
    for path in rollup(Path(__file__).parent / "data", day):
        print(f"작성: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -X utf8 -m unittest discover -s tests -t . -v`
Expected: PASS — 49 tests OK

- [ ] **Step 5: 커밋**

```bash
git add rollup.py tests/test_rollup.py
git commit -m "feat: 주간/월간/연간 집계 추가"
```

---

### Task 5: 화면 생성 (`template.html`, `build.py`)

네 기간 문서를 `template.html`에 인라인으로 주입해 `index.html`을 만든다. 이 태스크의 목표는 **동작하는 화면**이다 — 탭 전환, 카테고리 필터, 원문 링크, 부족 안내가 모두 작동해야 한다. 시각 디자인은 다음 태스크에서 다듬는다.

**Files:**
- Create: `template.html`
- Create: `build.py`
- Create: `tests/test_build.py`

**Interfaces:**
- Consumes: `periods.keys_for`, `periods.label_for`, `store.load`
- Produces:
  - `PLACEHOLDER: str` = `"/*__DATA__*/"`
  - `empty_doc(period: str, key: str) -> dict`
  - `latest_daily_date(data_dir) -> date | None`
  - `collect(data_dir, day: date) -> dict` — `{"daily": doc, "weekly": doc, "monthly": doc, "yearly": doc}`
  - `render(template: str, docs: dict, now: datetime) -> str`
  - `main() -> int` — CLI 진입점

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_build.py`:

```python
"""index.html 생성 테스트."""

import json
import re
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path

import build
import store

FIXED_NOW = datetime(2026, 9, 10, 7, 40, tzinfo=build.KST)

TEMPLATE = (
    '<!doctype html><html><body>'
    '<script id="payload" type="application/json">/*__DATA__*/</script>'
    '</body></html>'
)


def daily_doc(key, items):
    return {
        "period": "daily",
        "key": key,
        "label": key,
        "generated_at": "2026-09-10T07:40:00+09:00",
        "item_count": len(items),
        "shortfall_note": None,
        "items": items,
    }


def item(title="퇴직연금 적립금 400조 돌파", url="https://example.com/news/1"):
    return {
        "id": "abc123def456",
        "title": title,
        "summary": "요약 문장 하나. 요약 문장 둘. 요약 문장 셋.",
        "category": "업계·경쟁사",
        "importance": 4,
        "source": "테스트일보",
        "published": "2026-09-10",
        "url": url,
    }


def payload_of(html):
    match = re.search(
        r'<script id="payload" type="application/json">(.*?)</script>', html, re.DOTALL
    )
    return json.loads(match.group(1))


class CollectTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_missing_period_files_become_empty_documents(self):
        docs = build.collect(self.root, date(2026, 9, 10))
        self.assertEqual(set(docs), {"daily", "weekly", "monthly", "yearly"})
        self.assertEqual(docs["weekly"]["items"], [])
        self.assertEqual(docs["weekly"]["label"], "2026-W37 (2026-09-07 ~ 2026-09-13)")
        self.assertIn("아직", docs["yearly"]["shortfall_note"])

    def test_existing_files_are_loaded(self):
        store.save(self.root / "daily" / "2026-09-10.json", daily_doc("2026-09-10", [item()]))
        docs = build.collect(self.root, date(2026, 9, 10))
        self.assertEqual(docs["daily"]["item_count"], 1)


class LatestDailyDateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_returns_none_when_no_daily_files(self):
        self.assertIsNone(build.latest_daily_date(self.root))

    def test_returns_the_newest_date(self):
        for day in ("2026-09-08", "2026-09-10", "2026-09-09"):
            store.save(self.root / "daily" / f"{day}.json", daily_doc(day, [item()]))
        self.assertEqual(build.latest_daily_date(self.root), date(2026, 9, 10))


class RenderTest(unittest.TestCase):
    def setUp(self):
        self.docs = {
            "daily": daily_doc("2026-09-10", [item()]),
            "weekly": build.empty_doc("weekly", "2026-W37"),
            "monthly": build.empty_doc("monthly", "2026-09"),
            "yearly": build.empty_doc("yearly", "2026"),
        }

    def test_placeholder_is_replaced(self):
        html = build.render(TEMPLATE, self.docs, FIXED_NOW)
        self.assertNotIn(build.PLACEHOLDER, html)

    def test_payload_parses_as_json(self):
        payload = payload_of(build.render(TEMPLATE, self.docs, FIXED_NOW))
        self.assertEqual(payload["built_at"], "2026-09-10T07:40+09:00")
        self.assertEqual(payload["periods"]["daily"]["item_count"], 1)

    def test_korean_is_not_escaped(self):
        html = build.render(TEMPLATE, self.docs, FIXED_NOW)
        self.assertIn("퇴직연금", html)

    def test_angle_bracket_in_data_cannot_close_the_script_tag(self):
        self.docs["daily"]["items"][0]["title"] = "</script><script>alert(1)</script>"
        html = build.render(TEMPLATE, self.docs, FIXED_NOW)
        self.assertEqual(html.count("</script>"), 1)
        payload = payload_of(html)
        self.assertEqual(
            payload["periods"]["daily"]["items"][0]["title"],
            "</script><script>alert(1)</script>",
        )


class TemplateFileTest(unittest.TestCase):
    def test_real_template_has_placeholder_and_no_external_requests(self):
        text = (Path(__file__).resolve().parent.parent / "template.html").read_text(encoding="utf-8")
        self.assertIn(build.PLACEHOLDER, text)
        self.assertNotIn("http://", text)
        self.assertNotIn("https://", text)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

Run: `python -X utf8 -m unittest tests.test_build -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'build'`

- [ ] **Step 3: `build.py` 구현**

```python
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
```

- [ ] **Step 4: `template.html` 구현**

외부 요청 없이 동작해야 한다. CSS는 이 단계에서는 최소한만 넣고, 다음 태스크에서 다듬는다.

```html
<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>퇴직연금 주요 이슈</title>
<style>
  :root { color-scheme: light dark; }
  body { font-family: system-ui, sans-serif; margin: 0 auto; max-width: 860px; padding: 24px 16px 64px; line-height: 1.6; }
  h1 { margin: 0 0 4px; font-size: 1.5rem; }
  .meta { margin: 0 0 20px; opacity: 0.7; font-size: 0.85rem; }
  .tabs { display: flex; gap: 8px; margin-bottom: 12px; flex-wrap: wrap; }
  .tabs button { padding: 8px 16px; cursor: pointer; border: 1px solid currentColor; background: transparent; color: inherit; border-radius: 999px; font: inherit; }
  .tabs button[aria-selected="true"] { background: currentColor; }
  .tabs button[aria-selected="true"] span { filter: invert(1); }
  .filters { display: flex; gap: 6px; margin-bottom: 16px; flex-wrap: wrap; font-size: 0.85rem; }
  .filters button { padding: 4px 12px; cursor: pointer; border: 1px solid currentColor; background: transparent; color: inherit; border-radius: 999px; font: inherit; opacity: 0.55; }
  .filters button[aria-pressed="true"] { opacity: 1; }
  .notice { padding: 12px 14px; border: 1px dashed currentColor; border-radius: 8px; margin-bottom: 16px; font-size: 0.9rem; }
  article { padding: 16px 0; border-top: 1px solid rgba(128,128,128,0.35); }
  article h2 { margin: 6px 0; font-size: 1.05rem; }
  .rank { font-variant-numeric: tabular-nums; opacity: 0.5; margin-right: 6px; }
  .badge { display: inline-block; padding: 2px 8px; border-radius: 999px; border: 1px solid currentColor; font-size: 0.75rem; }
  .summary { margin: 8px 0; }
  .source { font-size: 0.85rem; opacity: 0.7; }
  .source a { color: inherit; }
  details { margin-top: 8px; font-size: 0.85rem; }
  details ul { margin: 8px 0 0; padding-left: 18px; }
</style>
</head>
<body>
<h1>퇴직연금 주요 이슈</h1>
<p class="meta" id="meta"></p>

<nav class="tabs" id="tabs" aria-label="기간 선택"></nav>
<div class="filters" id="filters" aria-label="카테고리 필터"></div>
<main id="list"></main>

<script id="payload" type="application/json">/*__DATA__*/</script>
<script>
(function () {
  var DATA = JSON.parse(document.getElementById('payload').textContent);
  var PERIOD_NAMES = { daily: '일간', weekly: '주간', monthly: '월간', yearly: '연간' };
  var ORDER = ['daily', 'weekly', 'monthly', 'yearly'];
  var CATEGORIES = ['제도·규제', '업계·경쟁사', '가입자·사회'];

  var currentPeriod = 'daily';
  var currentCategory = null;

  var tabsEl = document.getElementById('tabs');
  var filtersEl = document.getElementById('filters');
  var listEl = document.getElementById('list');
  var metaEl = document.getElementById('meta');

  function el(tag, className, text) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function buildTabs() {
    ORDER.forEach(function (period) {
      var button = el('button');
      button.appendChild(el('span', null, PERIOD_NAMES[period]));
      button.setAttribute('aria-selected', String(period === currentPeriod));
      button.addEventListener('click', function () {
        currentPeriod = period;
        render();
      });
      tabsEl.appendChild(button);
    });
  }

  function buildFilters() {
    [null].concat(CATEGORIES).forEach(function (category) {
      var button = el('button', null, category === null ? '전체' : category);
      button.setAttribute('aria-pressed', String(category === currentCategory));
      button.addEventListener('click', function () {
        currentCategory = category;
        render();
      });
      filtersEl.appendChild(button);
    });
  }

  function articleNode(item, rank) {
    var node = el('article');

    var head = el('div');
    head.appendChild(el('span', 'rank', String(rank)));
    head.appendChild(el('span', 'badge', item.category));
    node.appendChild(head);

    node.appendChild(el('h2', null, item.title));
    node.appendChild(el('p', 'summary', item.summary));

    var source = el('p', 'source', item.source + ' · ' + item.published + ' · ');
    var link = el('a', null, '원문 보기');
    link.href = item.url;
    link.target = '_blank';
    link.rel = 'noopener noreferrer';
    source.appendChild(link);
    node.appendChild(source);

    var related = item.related || [];
    if (related.length > 0) {
      var details = el('details');
      details.appendChild(el('summary', null, '관련 기사 ' + related.length + '건'));
      var list = el('ul');
      related.forEach(function (rel) {
        var li = el('li');
        var relLink = el('a', null, rel.source + ' — ' + rel.title);
        relLink.href = rel.url;
        relLink.target = '_blank';
        relLink.rel = 'noopener noreferrer';
        li.appendChild(relLink);
        list.appendChild(li);
      });
      details.appendChild(list);
      node.appendChild(details);
    }
    return node;
  }

  function render() {
    var doc = DATA.periods[currentPeriod];

    metaEl.textContent = doc.label + ' 기준 · 화면 갱신 ' + DATA.built_at;

    Array.prototype.forEach.call(tabsEl.children, function (button, index) {
      button.setAttribute('aria-selected', String(ORDER[index] === currentPeriod));
    });
    Array.prototype.forEach.call(filtersEl.children, function (button, index) {
      var category = index === 0 ? null : CATEGORIES[index - 1];
      button.setAttribute('aria-pressed', String(category === currentCategory));
    });

    listEl.textContent = '';

    if (doc.shortfall_note) {
      listEl.appendChild(el('p', 'notice', doc.shortfall_note));
    }

    var items = doc.items.filter(function (item) {
      return currentCategory === null || item.category === currentCategory;
    });

    if (items.length === 0) {
      listEl.appendChild(el('p', 'notice', '표시할 이슈가 없습니다.'));
      return;
    }

    items.forEach(function (item, index) {
      listEl.appendChild(articleNode(item, index + 1));
    });
  }

  buildTabs();
  buildFilters();
  render();
})();
</script>
</body>
</html>
```

- [ ] **Step 5: 테스트 통과 확인**

Run: `python -X utf8 -m unittest discover -s tests -t . -v`
Expected: PASS — 60 tests OK

- [ ] **Step 6: 샘플 데이터로 실제 화면 생성 확인**

임시 샘플을 만들어 파이프라인 전체가 도는지 본다.

```bash
python -X utf8 -c "
import store, rollup, build
from datetime import date
items = [{
    'id': f'sample{n:06d}',
    'title': f'샘플 퇴직연금 이슈 {n}',
    'summary': '샘플 요약 문장 하나. 샘플 요약 문장 둘. 샘플 요약 문장 셋.',
    'category': ['제도·규제', '업계·경쟁사', '가입자·사회'][n % 3],
    'importance': 5 - (n % 5),
    'source': '샘플일보',
    'published': '2026-09-10',
    'url': f'https://example.com/news/{n}',
} for n in range(10)]
store.save('data/daily/2026-09-10.json', {
    'period': 'daily', 'key': '2026-09-10', 'label': '2026-09-10 (목)',
    'generated_at': '2026-09-10T07:40:00+09:00', 'item_count': 10,
    'shortfall_note': None, 'items': items,
})
rollup.rollup('data', date(2026, 9, 10))
"
python -X utf8 build.py
```

Expected: `작성: ...\index.html (기준일 2026-09-10)`

브라우저에서 `index.html`을 열어 다음을 눈으로 확인한다:
- 일간/주간/월간/연간 탭 전환이 되는가
- 카테고리 필터가 동작하는가
- `원문 보기`가 새 탭으로 열리는가
- 주간 탭 카드에 `관련 기사 N건`이 나오는가(샘플에서는 안 나올 수 있음 — 중복이 없으므로 정상)

- [ ] **Step 7: 샘플 데이터 삭제 후 커밋**

샘플은 실제 데이터가 아니므로 커밋하지 않는다.

```bash
rm -rf data index.html
git add template.html build.py tests/test_build.py
git commit -m "feat: 기간 데이터를 인라인으로 담은 index.html 생성 추가"
```

---

### Task 6: 화면 디자인 마감

동작은 되지만 아직 기본 브라우저 스타일에 가깝다. 매일 아침 보는 화면이므로 읽기 편하고 훑기 쉬워야 한다.

**REQUIRED SUB-SKILL:** 이 태스크를 시작할 때 `frontend-design:frontend-design` 스킬을 먼저 호출한다.

**Files:**
- Modify: `template.html` (`<style>` 블록과 필요 시 마크업 구조)

**Interfaces:**
- Consumes: Task 5의 `template.html` 구조 — `#meta`, `#tabs`, `#filters`, `#list`, `#payload`
- Produces: 변경 없음 (JS의 DOM 조회 대상 id와 클래스 이름은 그대로 유지해야 `build.py` 테스트와 렌더 로직이 깨지지 않는다)

- [ ] **Step 1: `frontend-design` 스킬 호출**

- [ ] **Step 2: 디자인 요구사항을 만족하도록 `template.html` 수정**

지켜야 할 것:
- 외부 요청 금지 — 웹폰트, CDN, 이미지 URL 모두 불가. 시스템 폰트 스택만 사용
- 라이트/다크 모두 대응 (`prefers-color-scheme`)
- 카테고리 3종에 서로 구분되는 색을 주되, 라이트·다크 양쪽에서 대비가 충분할 것
- 순위 번호가 눈에 띄어 10건을 빠르게 훑을 수 있을 것
- 모바일 폭(360px)에서 가로 스크롤이 생기지 않을 것
- id(`meta`, `tabs`, `filters`, `list`, `payload`)와 JS가 붙이는 클래스(`rank`, `badge`, `summary`, `source`, `notice`)는 이름을 바꾸지 말 것

- [ ] **Step 3: 테스트가 여전히 통과하는지 확인**

Run: `python -X utf8 -m unittest discover -s tests -t . -v`
Expected: PASS — 60 tests OK (특히 `test_real_template_has_placeholder_and_no_external_requests`)

- [ ] **Step 4: 샘플 데이터로 화면 확인**

Task 5 Step 6의 샘플 생성 명령을 다시 실행하고 `build.py`로 빌드한 뒤, 브라우저에서 확인한다:
- 라이트 모드와 다크 모드 양쪽 (OS 설정을 바꾸거나 브라우저 개발자도구의 렌더링 패널 사용)
- 창 폭 360px

- [ ] **Step 5: 샘플 삭제 후 커밋**

```bash
rm -rf data index.html
git add template.html
git commit -m "style: 대시보드 화면 디자인 마감"
```

---

### Task 7: 일일 수집 런북 (`daily_update.md`)과 첫 실전 수집

뉴스 수집·요약은 코드가 아니라 Claude가 한다. 매일 같은 품질이 나오려면 절차가 문서로 고정돼 있어야 한다. 이 태스크는 런북을 쓰고, 그 런북대로 오늘 데이터를 실제로 한 번 수집해 파이프라인 전체를 검증한다.

**Files:**
- Create: `daily_update.md`
- Create: `README.md`
- Create (실행 결과): `data/daily/<오늘>.json`, `data/weekly/*.json`, `data/monthly/*.json`, `data/yearly/*.json`, `index.html`

**Interfaces:**
- Consumes: `store.save`의 스키마, `rollup.py` CLI, `build.py` CLI
- Produces: `daily_update.md` — 스케줄 에이전트가 매일 그대로 따르는 절차

- [ ] **Step 1: `daily_update.md` 작성**

```markdown
# 일일 수집 런북

매일 오전 7시 40분(KST)에 이 절차를 그대로 수행한다.
프로젝트 루트는 이 파일이 있는 폴더다.

## 1. 검색

오늘 날짜(KST) 기준으로 다음 질의를 각각 웹 검색한다. 오늘·어제 기사만 본다.

- `퇴직연금`
- `IRP 개인형퇴직연금`
- `확정기여형 DC 퇴직연금`
- `확정급여형 DB 퇴직연금`
- `퇴직연금 디폴트옵션`
- `퇴직연금 적립금`
- `퇴직연금 수익률`
- `기금형 퇴직연금`
- `연금개혁`
- `퇴직연금 TDF`

## 2. 선별

모인 기사에서 다음 기준으로 **정확히 10건**(부족하면 있는 만큼)을 고른다.

**카테고리 3종** — 각 기사에 하나씩 붙인다. 값은 정확히 이 문자열이어야 한다.

- `제도·규제` — 법 개정, 금감원·고용노동부 가이드라인, 기금형·디폴트옵션 등 제도 변화
- `업계·경쟁사` — 은행·증권·보험사의 점유율, 신상품·서비스, 수수료 경쟁, 로보어드바이저
- `가입자·사회` — 중도인출, 연금화 수령, 고령화·노후설계, 국민연금 개혁 등

**균형** — 세 카테고리에서 각각 최소 1건은 포함한다.

**중요도(`importance`, 1~5)** — 5는 제도 확정·대형 발표처럼 업무에 직접 영향을 주는 건, 1은 참고용 단신.

**제외** — 광고성 기사, 특정 상품 홍보, 같은 사건의 단순 중복 보도(가장 충실한 1건만 남긴다).

## 3. 요약

각 기사를 **3~4문장**으로 요약한다.

- 기사에 실제로 있는 사실만 쓴다. 추측이나 배경 설명을 덧붙이지 않는다.
- 숫자(금액, 비율, 시행일)는 기사에 나온 그대로 옮긴다.
- 문장은 평서형으로 끝낸다.

## 4. 저장

`data/daily/YYYY-MM-DD.json`에 아래 형식으로 저장한다. `id`는 URL 기반으로 만든다.

```python
python -X utf8 -c "import dedupe; print(dedupe.make_id('여기에 기사 URL'))"
```

```json
{
  "period": "daily",
  "key": "2026-09-10",
  "label": "2026-09-10 (목)",
  "generated_at": "2026-09-10T07:40:00+09:00",
  "item_count": 10,
  "shortfall_note": null,
  "items": [
    {
      "id": "a1b2c3d4e5f6",
      "title": "기사 제목",
      "summary": "요약 문장 하나. 요약 문장 둘. 요약 문장 셋.",
      "category": "제도·규제",
      "importance": 4,
      "source": "언론사명",
      "published": "2026-09-10",
      "url": "https://..."
    }
  ]
}
```

`label`은 `python -X utf8 -c "import periods; print(periods.label_for('daily', '2026-09-10'))"`로 얻는다.
10건을 못 채웠으면 `shortfall_note`에 사유를 한국어로 적는다.

유료 기사나 로그인이 필요한 매체는 `source` 끝에 ` (유료)`를 붙인다.

## 5. 집계와 빌드

```bash
python -X utf8 rollup.py
python -X utf8 build.py
```

## 6. 검토

`data/weekly/`, `data/monthly/`, `data/yearly/`의 오늘자 파일을 열어 확인한다.

- 같은 사건이 두 항목으로 갈라져 있으면, 한쪽을 지우고 다른 쪽 `related`에 옮긴다.
- 순위가 실제 중요도와 어긋나면 `items` 순서를 직접 바꾼다.
- 고쳤으면 `python -X utf8 build.py`를 다시 실행한다.

## 7. 실패했을 때

검색이 실패하거나 관련 기사를 하나도 못 찾았으면, **아무 파일도 쓰지 않고 중단한다.**
`index.html`은 마지막으로 성공한 데이터를 그대로 보여준다.

## 8. 게시

`index.html`을 Artifact로 재게시한다. 반드시 기존과 **같은 URL**로 업데이트한다
(`Artifact` 도구의 `url` 파라미터에 기존 주소를 넘긴다). 주소는 `README.md`에 적혀 있다.
```

- [ ] **Step 2: `README.md` 작성**

```markdown
# 퇴직연금 주요 이슈 데일리 대시보드

매일 아침 퇴직연금·연금 주요 이슈 10건을 수집·요약해 보여주는 화면.

## 보는 방법

- **로컬** — `index.html` 더블클릭
- **웹** — (Task 8에서 Artifact URL을 여기에 적는다)

## 화면

일간 / 주간 / 월간 / 연간 4개 탭. 각 탭에 최대 10건. 카테고리 배지로 필터할 수 있고,
`원문 보기`로 기사 전문으로 이동한다.

## 직접 갱신하기

```bash
python -X utf8 rollup.py    # 일간 파일들 → 주간/월간/연간 재집계
python -X utf8 build.py     # 데이터 → index.html
```

뉴스 수집·요약 절차는 `daily_update.md`에 있다.

## 구조

| 파일 | 역할 |
|---|---|
| `periods.py` | 일간/주간/월간/연간 기간 키와 범위 계산 |
| `store.py` | 기간 파일(JSON) 검증과 입출력 |
| `dedupe.py` | 중복·후속 기사 묶기 |
| `rollup.py` | 일간 파일 → 기간별 TOP 10 |
| `build.py` | 기간 파일 → `index.html` |
| `template.html` | 화면 뼈대. 데이터가 인라인으로 주입된다 |
| `data/` | 날짜별 원본 데이터 |

## 테스트

```bash
python -X utf8 -m unittest discover -s tests -t . -v
```
```

- [ ] **Step 3: 런북대로 오늘 데이터를 실제로 수집**

`daily_update.md`의 1~5단계를 그대로 수행한다. 실제 웹 검색으로 오늘자 기사를 찾고, 요약하고, `data/daily/<오늘>.json`에 저장한 뒤 `rollup.py`와 `build.py`를 실행한다.

- [ ] **Step 4: 저장한 데이터가 스키마를 통과하는지 확인**

```bash
python -X utf8 -c "
import store, glob
for path in sorted(glob.glob('data/*/*.json')):
    errors = store.doc_errors(store.load(path))
    print(path, '정상' if not errors else errors)
"
```

Expected: 모든 줄이 `정상`

- [ ] **Step 5: 실제 화면 확인**

브라우저에서 `index.html`을 연다. 확인할 것:
- 일간 탭에 오늘 기사 10건(또는 부족 안내)이 나오는가
- 요약이 3~4문장인가
- `원문 보기` 링크를 클릭하면 실제 기사가 열리는가 — **10건 모두 눌러본다**
- 주간/월간/연간 탭에도 같은 내용이 나오는가(첫날이므로 정상)

- [ ] **Step 6: 커밋**

```bash
git add daily_update.md README.md data index.html
git commit -m "docs: 일일 수집 런북 추가 및 첫 데이터 수집"
```

---

### Task 8: 자동 갱신과 웹 게시

여기까지는 사람이 명령을 쳐야 갱신된다. 이 태스크에서 매일 자동으로 돌게 만들고, 웹 링크를 만든다.

설계 문서의 미해결 사항 — 클라우드 예약 에이전트가 로컬 폴더에 접근할 수 있는지 — 을 **먼저** 확인하고, 결과에 따라 갈라진다.

**Files:**
- Modify: `README.md` (Artifact URL 기록)
- Modify: `daily_update.md` (확인된 실행 방식 반영)

**Interfaces:**
- Consumes: `daily_update.md`의 절차, `index.html`
- Produces: 매일 실행되는 예약 작업, 비공개 Artifact URL

- [ ] **Step 1: `index.html`을 Artifact로 게시**

`Artifact` 도구로 `index.html`을 게시한다.
- `favicon`: `📊`
- `description`: `매일 갱신되는 퇴직연금·연금 주요 이슈 일간/주간/월간/연간 요약`

돌려받은 URL을 기록한다. **이후 모든 갱신은 이 URL로 업데이트해야 한다.**

- [ ] **Step 2: URL을 `README.md`와 `daily_update.md`에 적기**

`README.md`의 `(Task 8에서 Artifact URL을 여기에 적는다)`를 실제 URL로 바꾼다.
`daily_update.md` 8단계에도 URL을 명시한다.

- [ ] **Step 3: 클라우드 예약 에이전트의 로컬 접근 가능 여부 확인**

`schedule` 스킬을 호출해, 예약된 클라우드 에이전트가 이 폴더(`C:\Users\박형주\Desktop\퇴직연금 주요 이슈`)의 파일을 읽고 쓸 수 있는지 확인한다.

- [ ] **Step 4: 확인 결과에 따라 예약 설정**

**가능한 경우** — 매일 07:37 KST에 `daily_update.md`를 따르는 예약 에이전트를 등록한다. 프롬프트:

```
C:\Users\박형주\Desktop\퇴직연금 주요 이슈\daily_update.md 를 읽고 그 절차를 처음부터 끝까지 그대로 수행하라. 오늘 날짜(KST) 기준이다.
```

**불가능한 경우** — 설계 문서의 대체안을 따른다.

1. 클라우드 예약 에이전트는 웹 검색·요약을 수행하고 결과를 **Artifact URL 갱신**까지만 한다 (로컬 파일 대신 Artifact의 데이터베이스나 게시 내용으로 상태를 유지).
2. 로컬 파일은 사용자가 PC에서 Claude Code를 열고 `오늘 이슈 갱신해줘`라고 하면 `daily_update.md`대로 실행해 동기화한다.
3. 이 두 경로를 `daily_update.md`에 명시적으로 나눠 적는다.

어느 쪽이든 **사용자가 매일 아침 보는 웹 링크는 자동 갱신되어야 한다.**

- [ ] **Step 5: 예약이 등록됐는지 확인**

등록된 예약 목록을 조회해 매일 실행 항목이 있는지 확인하고, 다음 실행 예정 시각을 사용자에게 보고한다.

- [ ] **Step 6: 커밋**

```bash
git add README.md daily_update.md
git commit -m "feat: 매일 자동 갱신 예약과 웹 게시 연결"
```

- [ ] **Step 7: 사용자에게 인계**

다음을 보고한다:
- 로컬 파일 경로 (`index.html`)
- 웹 링크 (Artifact URL)
- 매일 자동 실행 시각과 그 방식
- 수동으로 갱신하려면 무엇을 하면 되는지
