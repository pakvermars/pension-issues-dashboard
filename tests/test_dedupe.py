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
        self.assertEqual(
            dedupe.normalize_url("https://example.com/"), "https://example.com/"
        )


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
            article(
                "퇴직연금 디폴트옵션 수익률 공시, 원리금보장형 3%대", "https://a.com/1"
            ),
            article(
                "[속보] 디폴트옵션 수익률 공시…원리금보장형 3%대 기록",
                "https://b.com/2",
            ),
            article("국민연금 개혁안 국회 통과", "https://c.com/3"),
        ]
        groups = dedupe.cluster(items)
        self.assertEqual(sorted(len(group) for group in groups), [1, 2])

    def test_same_url_is_grouped_even_with_different_titles(self):
        items = [
            article("퇴직연금 적립금 400조 돌파", "https://a.com/news/9"),
            article(
                "전혀 다른 제목이 붙은 같은 기사", "https://www.a.com/news/9?utm_source=x"
            ),
        ]
        self.assertEqual(len(dedupe.cluster(items)), 1)

    def test_group_leader_is_the_most_important_article(self):
        items = [
            article(
                "퇴직연금 디폴트옵션 수익률 공시, 원리금보장형 3%대",
                "https://a.com/1",
                importance=2,
            ),
            article(
                "[속보] 디폴트옵션 수익률 공시…원리금보장형 3%대 기록",
                "https://b.com/2",
                importance=5,
            ),
        ]
        group = dedupe.cluster(items)[0]
        self.assertEqual(group[0]["url"], "https://b.com/2")

    def test_empty_input_returns_empty_list(self):
        self.assertEqual(dedupe.cluster([]), [])


if __name__ == "__main__":
    unittest.main()
