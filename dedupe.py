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


def cluster(
    items: list[dict], threshold: float = SIMILARITY_THRESHOLD
) -> list[list[dict]]:
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
