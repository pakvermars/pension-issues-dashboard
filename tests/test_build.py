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
    "<!doctype html><html><body>"
    '<script id="payload" type="application/json">/*__DATA__*/</script>'
    "</body></html>"
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
        store.save(
            self.root / "daily" / "2026-09-10.json", daily_doc("2026-09-10", [item()])
        )
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
        text = (Path(__file__).resolve().parent.parent / "template.html").read_text(
            encoding="utf-8"
        )
        self.assertIn(build.PLACEHOLDER, text)
        self.assertNotIn("http://", text)
        self.assertNotIn("https://", text)


if __name__ == "__main__":
    unittest.main()
