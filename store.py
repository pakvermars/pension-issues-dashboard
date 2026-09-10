"""기간 파일(JSON)의 검증과 입출력을 담당한다."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

CATEGORIES = ("제도·규제", "업계·경쟁사", "가입자·사회", "법인·자금운용")

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
