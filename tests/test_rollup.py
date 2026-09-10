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
        items = [
            item(title, f"https://a.com/{n}", importance=3)
            for n, title in enumerate(DISTINCT_TITLES)
        ]
        doc = rollup.build_period(
            "monthly", "2026-09", [daily_doc("2026-09-10", items)], now=FIXED_NOW
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
