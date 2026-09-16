"""새 기사가 있을 때만 수집을 돌리기 위한 게이트.

check_new.js가 긁어 온 오늘 기사 URL을 이미 담긴 URL과 견줘, 수집을 돌릴지
건너뛸지 판단한다. 비싼 단계(claude -p 수집 세션)를 실제로 새 기사가 있을 때만
부르려고 둔 장치다.
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

COLLECT = "수집"
SKIP = "건너뜀"
BROKEN = "셀렉터_파손"


def known_urls(path) -> set[str]:
    """오늘 일간 파일에 이미 담긴 기사 URL. 파일이 없으면 빈 집합."""
    path = Path(path)
    if not path.is_file():
        return set()
    doc = json.loads(path.read_text(encoding="utf-8"))
    return {item["url"] for item in doc.get("items", [])}


def decide(scraped: dict, known: set[str]) -> tuple[str, list[str]]:
    """게이트 판단과 새로 찾은 URL 목록을 돌려준다.

    오늘 기사도 이전 기사도 한 건도 안 잡혔으면 네이버가 클래스명을 바꿔
    셀렉터가 깨진 쪽을 의심한다. 이땐 조용히 넘기지 않고 수집을 돌려
    사람이 볼 수 있는 자리까지 문제를 밀어 올린다.
    """
    today = scraped.get("오늘", [])
    새_기사 = [url for url in today if url not in known]
    if 새_기사:
        return COLLECT, 새_기사
    if not today and not scraped.get("이전", 0):
        return BROKEN, []
    return SKIP, []


def seen_urls(path, day: str) -> set[str]:
    """게이트가 그날 이미 수집으로 넘긴 URL."""
    path = Path(path)
    if not path.is_file():
        return set()
    doc = json.loads(path.read_text(encoding="utf-8"))
    if doc.get("date") != day:
        return set()
    return set(doc.get("urls", []))


def remember(path, day: str, urls) -> None:
    """수집으로 넘긴 URL을 그날치로 기록한다. 날이 바뀌면 어제 것은 버린다."""
    path = Path(path)
    기존 = seen_urls(path, day)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"date": day, "urls": sorted(기존 | set(urls))}
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


# ── CLI ──────────────────────────────────────────────────────────────────
# run_gate.ps1이 종료 코드로 갈림길을 판단한다.
#   0  수집이 필요하다 (새 기사가 있거나 셀렉터가 깨진 듯하다)
#   10 건너뛴다 (새 기사 없음)

EXIT_COLLECT = 0
EXIT_SKIP = 10

KST = timezone(timedelta(hours=9))
SEEN_PATH = "data/gate-seen.json"


def scrape(root: Path) -> dict:
    """check_new.js를 돌려 오늘 기사 URL 목록을 받는다."""
    try:
        done = subprocess.run(
            ["node", str(root / "check_new.js")],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=180,
            cwd=root,
        )
        return json.loads(done.stdout)
    except (subprocess.SubprocessError, json.JSONDecodeError, OSError) as error:
        # 긁지 못했으면 판단할 근거가 없다. 0건으로 넘겨 셀렉터 파손과 같은
        # 취급을 받게 한다 — 즉 수집이 돌고 로그에 흔적이 남는다.
        return {"오늘": [], "이전": 0, "오류": str(error)[:200]}


def main() -> int:
    root = Path(__file__).parent
    today = datetime.now(KST).date().isoformat()

    scraped = scrape(root)
    known = known_urls(root / "data" / "daily" / f"{today}.json") | seen_urls(
        root / SEEN_PATH, today
    )
    결정, 새_기사 = decide(scraped, known)

    if 결정 == COLLECT:
        # 기억해 두지 않으면, 수집이 이 기사를 선별에서 떨어뜨렸을 때
        # 다음 실행이 같은 URL로 또 수집을 부른다.
        remember(root / SEEN_PATH, today, 새_기사)
        print(f"{결정}: 새 기사 {len(새_기사)}건")
    elif 결정 == BROKEN:
        print(f"{결정}: 오늘·이전 모두 0건 — {scraped.get('오류', '셀렉터 확인 필요')}")
    else:
        print(f"{결정}: 오늘 {len(scraped.get('오늘', []))}건 모두 이미 담김")

    return EXIT_SKIP if 결정 == SKIP else EXIT_COLLECT


if __name__ == "__main__":
    raise SystemExit(main())
