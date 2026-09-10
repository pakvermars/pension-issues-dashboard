"""기간 파일 검증과 입출력 테스트."""

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

    def test_every_listed_category_is_accepted(self):
        for category in store.CATEGORIES:
            with self.subTest(category=category):
                self.assertEqual(store.item_errors(sample_item(category=category)), [])

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
        self.assertEqual(
            store.load_dailies(empty, date(2026, 1, 1), date(2026, 12, 31)), []
        )


if __name__ == "__main__":
    unittest.main()
