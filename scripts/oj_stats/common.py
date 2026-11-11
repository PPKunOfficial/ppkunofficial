"""Shared helpers for the OJ stats fetchers."""

from __future__ import annotations

import http.cookiejar
import json
import math
import random
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

PLATFORM_META = {
    "luogu": {"name": "洛谷", "accent": "#3b82f6", "url": "https://www.luogu.com.cn"},
    "codeforces": {"name": "Codeforces", "accent": "#e11d48", "url": "https://codeforces.com"},
    "leetcode": {"name": "力扣", "accent": "#f59e0b", "url": "https://leetcode.cn"},
    "nowcoder": {"name": "牛客", "accent": "#10b981", "url": "https://www.nowcoder.com"},
}


def log(platform: str, message: str) -> None:
    print(f"[{platform}] {message}", file=sys.stderr)


@dataclass
class PlatformStats:
    key: str
    handle: str
    stats: list[tuple[str, str, str | None]]
    daily: dict[date, int]
    total: int
    cumulative_label: str
    daily_label: str
    accent: str
    updated_at: datetime
    note: str = ""


class HttpClient:
    """Tiny urllib client with a cookie jar and retry/backoff."""

    def __init__(self) -> None:
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.jar)
        )

    def request(
        self,
        url: str,
        *,
        method: str = "GET",
        data: bytes | None = None,
        headers: dict[str, str] | None = None,
        timeout: int = 30,
        tries: int = 4,
    ) -> bytes:
        merged = {
            "User-Agent": USER_AGENT,
            "Accept": "*/*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }
        if headers:
            merged.update(headers)

        last_error: Exception | None = None
        for attempt in range(1, tries + 1):
            req = urllib.request.Request(url, data=data, headers=merged, method=method)
            try:
                with self.opener.open(req, timeout=timeout) as response:
                    body = response.read()
                    if response.status == 200 and body:
                        return body
                    last_error = RuntimeError(f"HTTP {response.status} with empty body")
            except urllib.error.HTTPError as exc:
                last_error = exc
                if exc.code not in (302, 403, 408, 425, 429, 500, 502, 503, 504):
                    raise
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                last_error = exc
            if attempt < tries:
                time.sleep(min(8.0, 1.2 * attempt + random.random()))
        raise RuntimeError(f"request failed: {url}: {last_error}")

    def get(self, url: str, **kwargs: Any) -> bytes:
        return self.request(url, **kwargs)

    def get_json(self, url: str, **kwargs: Any) -> Any:
        return json.loads(self.get(url, **kwargs).decode("utf-8", "replace"))

    def post_json(self, url: str, payload: Any, **kwargs: Any) -> Any:
        body = json.dumps(payload).encode("utf-8")
        headers = kwargs.pop("headers", {})
        headers.setdefault("Content-Type", "application/json")
        raw = self.request(url, method="POST", data=body, headers=headers, **kwargs)
        return json.loads(raw.decode("utf-8", "replace"))


LENTILLE_RE = re.compile(
    r'<script id="lentille-context" type="application/json">(.*?)</script>', re.S
)


def parse_lentille(html: str, context: str = "") -> dict[str, Any]:
    match = LENTILLE_RE.search(html)
    if not match:
        raise RuntimeError(f"lentille-context not found{context}")
    payload = json.loads(match.group(1))
    if payload.get("status") not in (None, 200):
        raise RuntimeError(f"luogu returned status {payload.get('status')}")
    return payload.get("data") or {}


def week_window(today: date, days: int) -> tuple[date, date]:
    """Return (start, today) where start is `days` days before today."""
    return today - timedelta(days=days), today


def iter_days(start: date, end: date) -> list[date]:
    return [start + timedelta(days=i) for i in range((end - start).days + 1)]


def nice_ceil(value: float) -> int:
    if value <= 0:
        return 0
    if value <= 10:
        return max(1, math.ceil(value))
    exponent = 10 ** math.floor(math.log10(value))
    for multiplier in (1, 1.2, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10):
        candidate = multiplier * exponent
        if candidate >= value:
            return int(round(candidate))
    return int(round(10 * exponent))


def fmt_int(value: int | None) -> str:
    if value is None:
        return "—"
    return f"{value:,}"


def char_width(ch: str) -> float:
    if ord(ch) >= 0x2E80:
        return 1.0
    if ch.isupper():
        return 0.66
    if ch.isdigit():
        return 0.56
    if ch in "il.,:;!|'":
        return 0.3
    if ch == " ":
        return 0.3
    return 0.55


def text_width(text: str, size: float) -> float:
    return sum(char_width(ch) for ch in text) * size


def svg_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
