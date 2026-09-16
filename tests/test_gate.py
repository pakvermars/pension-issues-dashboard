"""새 기사 유무를 판단하는 게이트 테스트."""

import json
import tempfile
import unittest
from pathlib import Path

import gate


def scraped(today=(), older=0):
    """check_new.js가 돌려주는 모양."""
    return {"오늘": list(today), "이전": older}


class DecideTest(unittest.TestCase):
    def test_담기지_않은_기사가_있으면_수집한다(self):
        결과, 새_기사 = gate.decide(
            scraped(today=["https://a.com/1", "https://a.com/2"]),
            known={"https://a.com/1"},
        )
        self.assertEqual(결과, gate.COLLECT)
        self.assertEqual(새_기사, ["https://a.com/2"])

    def test_모두_이미_담긴_기사면_건너뛴다(self):
        결과, 새_기사 = gate.decide(
            scraped(today=["https://a.com/1"]),
            known={"https://a.com/1"},
        )
        self.assertEqual(결과, gate.SKIP)
        self.assertEqual(새_기사, [])

    def test_오늘도_이전도_0건이면_셀렉터_파손으로_본다(self):
        결과, 새_기사 = gate.decide(scraped(today=[], older=0), known=set())
        self.assertEqual(결과, gate.BROKEN)
        self.assertEqual(새_기사, [])

    def test_오늘만_0건이면_그냥_새_기사가_없는_것이다(self):
        결과, _ = gate.decide(scraped(today=[], older=12), known=set())
        self.assertEqual(결과, gate.SKIP)


class KnownUrlsTest(unittest.TestCase):
    def test_오늘_파일이_없으면_빈_집합이다(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(gate.known_urls(Path(tmp) / "없는파일.json"), set())

    def test_오늘_파일에_담긴_url을_읽는다(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "2026-09-17.json"
            path.write_text(
                json.dumps({"items": [{"url": "https://a.com/1"}, {"url": "https://a.com/2"}]}),
                encoding="utf-8",
            )
            self.assertEqual(gate.known_urls(path), {"https://a.com/1", "https://a.com/2"})


class SeenTest(unittest.TestCase):
    """게이트가 한 번 제시한 URL은 다시 수집을 부르지 않는다.

    수집이 그 기사를 선별에서 떨어뜨리면 일간 파일에는 안 들어간다.
    기억해 두지 않으면 15분 뒤 같은 URL로 또 수집이 돈다.
    """

    def test_기억한_적_없으면_빈_집합이다(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(gate.seen_urls(Path(tmp) / "seen.json", "2026-09-17"), set())

    def test_기억한_url을_돌려준다(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "seen.json"
            gate.remember(path, "2026-09-17", ["https://a.com/1"])
            self.assertEqual(gate.seen_urls(path, "2026-09-17"), {"https://a.com/1"})

    def test_같은_날_기억은_쌓인다(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "seen.json"
            gate.remember(path, "2026-09-17", ["https://a.com/1"])
            gate.remember(path, "2026-09-17", ["https://a.com/2"])
            self.assertEqual(
                gate.seen_urls(path, "2026-09-17"),
                {"https://a.com/1", "https://a.com/2"},
            )

    def test_날이_바뀌면_어제_기억은_버린다(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "seen.json"
            gate.remember(path, "2026-09-16", ["https://a.com/1"])
            gate.remember(path, "2026-09-17", ["https://a.com/2"])
            self.assertEqual(gate.seen_urls(path, "2026-09-16"), set())


if __name__ == "__main__":
    unittest.main()
