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
    "개인투자용 국채 청약 경쟁 과열",
    "사외적립 의무화 단계 시행안 공개",
    "채권혼합 ETF 편입 비중 논란",
    "수탁법인 지배구조 설계 초안",
    "임금피크제 퇴직급여 산정 판결",
    "중소기업퇴직연금기금 가입 확대",
    "연금계좌 세액공제 한도 상향 검토",
    "외국계 운용사 국내 연금시장 진출",
    "퇴직급여 체불 사업장 특별근로감독",
    "가상자산 편입 허용 여부 검토",
]

assert len(DISTINCT_TITLES) > rollup.TOP_N, "상한 테스트를 하려면 제목이 TOP_N보다 많아야 한다"


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
        self.assertEqual(
            merged["related"],
            [
                {
                    "title": "디폴트옵션 수익률 공시 후속",
                    "source": "테스트일보",
                    "url": "https://b.com/2",
                }
            ],
        )

    def test_single_article_gets_empty_related(self):
        merged = rollup.merge([item("혼자", "https://a.com/1")])
        self.assertEqual(merged["related"], [])

    def test_same_article_collected_twice_is_not_its_own_related(self):
        # 일간이 전일 기사까지 담으므로 같은 기사가 이틀치 파일에 들어온다.
        same = item("퇴직연금 적립금 400조 돌파", "https://a.com/1")
        merged = rollup.merge([same, dict(same)])
        self.assertEqual(merged["related"], [])

    def test_related_drops_repeats_of_the_same_url(self):
        group = [
            item("원 기사", "https://a.com/1", importance=5),
            item("다른 매체 기사", "https://b.com/2", importance=3),
            item("다른 매체 기사", "https://www.b.com/2?utm_source=x", importance=3),
        ]
        merged = rollup.merge(group)
        self.assertEqual([rel["url"] for rel in merged["related"]], ["https://b.com/2"])


class BuildPeriodTest(unittest.TestCase):
    def test_duplicate_stories_across_days_collapse_into_one(self):
        dailies = [
            daily_doc(
                "2026-09-08",
                [
                    item(
                        "퇴직연금 디폴트옵션 수익률 공시, 원리금보장형 3%대",
                        "https://a.com/1",
                        importance=4,
                        published="2026-09-08",
                    )
                ],
            ),
            daily_doc(
                "2026-09-10",
                [
                    item(
                        "[속보] 디폴트옵션 수익률 공시…원리금보장형 3%대 기록",
                        "https://b.com/2",
                        importance=5,
                        published="2026-09-10",
                    )
                ],
            ),
        ]
        doc = rollup.build_period("weekly", "2026-W37", dailies, now=FIXED_NOW)
        self.assertEqual(doc["item_count"], 1)
        self.assertEqual(len(doc["items"][0]["related"]), 1)

    def test_items_are_ordered_by_score(self):
        dailies = [
            daily_doc(
                "2026-09-10",
                [
                    item("은행권 IRP 수수료 인하 경쟁", "https://a.com/1", importance=2),
                    item("국민연금 개혁안 국회 통과", "https://b.com/2", importance=5),
                    item("TDF 순자산 사상 최대", "https://c.com/3", importance=3),
                ],
            )
        ]
        doc = rollup.build_period("weekly", "2026-W37", dailies, now=FIXED_NOW)
        self.assertEqual(
            [i["title"] for i in doc["items"]],
            ["국민연금 개혁안 국회 통과", "TDF 순자산 사상 최대", "은행권 IRP 수수료 인하 경쟁"],
        )

    def test_selection_is_capped_at_top_n(self):
        # 주간은 분산 상한이 없으므로 TOP_N만으로 잘린다.
        items = [
            item(title, f"https://a.com/{n}", importance=3)
            for n, title in enumerate(DISTINCT_TITLES)
        ]
        doc = rollup.build_period(
            "weekly", "2026-W37", [daily_doc("2026-09-10", items)], now=FIXED_NOW
        )
        self.assertEqual(doc["item_count"], rollup.TOP_N)
        self.assertIsNone(doc["shortfall_note"])

    def test_shortfall_note_is_set_when_below_top_n(self):
        doc = rollup.build_period(
            "weekly",
            "2026-W37",
            [daily_doc("2026-09-10", [item("하나", "https://a.com/1")])],
            now=FIXED_NOW,
        )
        self.assertIn("1건", doc["shortfall_note"])

    def test_empty_input_produces_empty_document(self):
        doc = rollup.build_period("yearly", "2026", [], now=FIXED_NOW)
        self.assertEqual(doc["items"], [])
        self.assertEqual(doc["label"], "2026년")
        self.assertEqual(doc["generated_at"], "2026-09-10T07:40:00+09:00")


class PeriodScoringTest(unittest.TestCase):
    """주간은 최신·중요도, 월간·연간은 오래 이어진 이슈를 위로 올린다."""

    def dailies(self):
        # A: 하루짜리 큰 뉴스. B: 사흘에 걸쳐 이어진 이슈.
        return [
            daily_doc("2026-09-07", [
                item("기금형 퇴직연금 도입 논의 재점화", "https://b.com/1", importance=3, published="2026-09-07"),
            ]),
            daily_doc("2026-09-08", [
                item("기금형 퇴직연금 도입 논의 재점화 후속", "https://b.com/2", importance=3, published="2026-09-08"),
            ]),
            daily_doc("2026-09-09", [
                item("기금형 퇴직연금 도입 논의 또 재점화", "https://b.com/3", importance=3, published="2026-09-09"),
                item("퇴직연금 적립금 400조 돌파", "https://a.com/1", importance=5, published="2026-09-09"),
            ]),
        ]

    def test_weekly_puts_the_single_big_story_first(self):
        doc = rollup.build_period("weekly", "2026-W37", self.dailies(), now=FIXED_NOW)
        self.assertEqual(doc["items"][0]["url"], "https://a.com/1")

    def test_monthly_puts_the_sustained_story_first(self):
        doc = rollup.build_period("monthly", "2026-09", self.dailies(), now=FIXED_NOW)
        self.assertEqual(doc["items"][0]["url"], "https://b.com/3")

    def test_yearly_puts_the_sustained_story_first(self):
        doc = rollup.build_period("yearly", "2026", self.dailies(), now=FIXED_NOW)
        self.assertEqual(doc["items"][0]["url"], "https://b.com/3")


class YearlySpreadTest(unittest.TestCase):
    """연간은 한 달이 목록을 독차지하지 않게 월별 상한을 둔다."""

    def crowded_month(self):
        items = [
            item(title, f"https://a.com/{n}", importance=5, published="2026-09-09")
            for n, title in enumerate(DISTINCT_TITLES)
        ]
        # DISTINCT_TITLES와 겹치지 않아야 9월 기사와 묶이지 않는다.
        older = [
            item("근로복지공단 푸른씨앗 가입 사업장 3만 곳", "https://old.com/1", importance=2, published="2026-03-11"),
            item("자본시장연구원 다층 노후소득 보고서", "https://old.com/2", importance=2, published="2026-05-20"),
        ]
        return [daily_doc("2026-09-09", items), daily_doc("2026-03-11", [older[0]]), daily_doc("2026-05-20", [older[1]])]

    def test_yearly_caps_items_per_month(self):
        doc = rollup.build_period("yearly", "2026", self.crowded_month(), now=FIXED_NOW)
        september = [i for i in doc["items"] if i["published"].startswith("2026-09")]
        self.assertEqual(len(september), rollup.YEARLY_MONTH_CAP)

    def test_yearly_keeps_the_thin_months(self):
        doc = rollup.build_period("yearly", "2026", self.crowded_month(), now=FIXED_NOW)
        months = {i["published"][:7] for i in doc["items"]}
        self.assertIn("2026-03", months)
        self.assertIn("2026-05", months)

    def test_monthly_is_not_capped_by_month(self):
        doc = rollup.build_period("monthly", "2026-09", self.crowded_month(), now=FIXED_NOW)
        september = [i for i in doc["items"] if i["published"].startswith("2026-09")]
        self.assertGreater(len(september), rollup.YEARLY_MONTH_CAP)

    def test_monthly_caps_items_per_week(self):
        # 한 주에 몰린 기사와 다른 주 기사를 섞어 둔다.
        crowded = [
            item(title, f"https://a.com/{n}", importance=5, published="2026-09-09")
            for n, title in enumerate(DISTINCT_TITLES)
        ]
        other_week = [
            item("근로복지공단 푸른씨앗 가입 사업장 3만 곳", "https://w36.com/1", importance=2, published="2026-09-02"),
            item("자본시장연구원 다층 노후소득 보고서", "https://w36.com/2", importance=2, published="2026-09-03"),
        ]
        dailies = [
            daily_doc("2026-09-09", crowded),
            daily_doc("2026-09-02", [other_week[0]]),
            daily_doc("2026-09-03", [other_week[1]]),
        ]
        doc = rollup.build_period("monthly", "2026-09", dailies, now=FIXED_NOW)
        big_week = [i for i in doc["items"] if i["published"] == "2026-09-09"]
        self.assertEqual(len(big_week), rollup.MONTHLY_WEEK_CAP)
        self.assertTrue(any(i["url"].startswith("https://w36.com/") for i in doc["items"]))


class MergeMapTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_missing_file_gives_empty_corrections(self):
        self.assertEqual(rollup.load_corrections(self.root), {"same": [], "different": []})

    def test_corrections_are_read(self):
        (self.root / "merges.json").write_text(
            '{"same": [["https://a.com/1", "https://b.com/2"]], "different": []}',
            encoding="utf-8",
        )
        self.assertEqual(
            rollup.load_corrections(self.root)["same"],
            [["https://a.com/1", "https://b.com/2"]],
        )

    def test_corrections_survive_regeneration(self):
        store.save(self.root / "daily" / "2026-09-09.json", daily_doc("2026-09-09", [
            item("퇴직연금 적립금 400조 돌파", "https://a.com/1", published="2026-09-09"),
            item("국민연금 개혁안 국회 통과", "https://b.com/2", published="2026-09-09"),
        ]))
        (self.root / "merges.json").write_text(
            '{"same": [["https://a.com/1", "https://b.com/2"]]}', encoding="utf-8"
        )
        rollup.rollup(self.root, date(2026, 9, 9), now=FIXED_NOW)
        weekly = store.load(self.root / "weekly" / "2026-W37.json")
        self.assertEqual(weekly["item_count"], 1)
        self.assertEqual(len(weekly["items"][0]["related"]), 1)


class RollupTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        store.save(
            self.root / "daily" / "2026-09-08.json",
            daily_doc(
                "2026-09-08",
                [
                    item(
                        "퇴직연금 적립금 400조 돌파",
                        "https://a.com/1",
                        published="2026-09-08",
                    )
                ],
            ),
        )
        store.save(
            self.root / "daily" / "2026-09-10.json",
            daily_doc(
                "2026-09-10",
                [
                    item(
                        "국민연금 개혁안 국회 통과",
                        "https://b.com/2",
                        published="2026-09-10",
                    )
                ],
            ),
        )
        store.save(
            self.root / "daily" / "2026-08-20.json",
            daily_doc(
                "2026-08-20",
                [
                    item(
                        "디폴트옵션 수익률 공시",
                        "https://c.com/3",
                        published="2026-08-20",
                    )
                ],
            ),
        )

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
