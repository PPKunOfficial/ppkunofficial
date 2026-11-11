"""Fetch Codeforces submission statistics from the official API."""

from __future__ import annotations

import time
import urllib.parse
from collections import defaultdict
from datetime import date, datetime
from zoneinfo import ZoneInfo

from common import HttpClient, PlatformStats, log

BASE = "https://codeforces.com/api"


def _rank_color(rating: int | None) -> str:
    if rating is None:
        return "#64748b"
    if rating < 1200:
        return "#808080"
    if rating < 1400:
        return "#008000"
    if rating < 1600:
        return "#03a89e"
    if rating < 1900:
        return "#2f6fdb"
    if rating < 2100:
        return "#a855f7"
    if rating < 2300:
        return "#f59e0b"
    if rating < 2400:
        return "#f97316"
    if rating < 2600:
        return "#ef4444"
    if rating < 3000:
        return "#dc2626"
    return "#7f1d1d"


def _api(client: HttpClient, method: str, **params: str):
    query = urllib.parse.urlencode(params)
    payload = client.get_json(f"{BASE}/{method}?{query}", tries=4)
    if payload.get("status") != "OK":
        raise RuntimeError(payload.get("comment") or f"{method} failed")
    return payload.get("result")


def fetch(config: dict, tz: ZoneInfo, today: date) -> PlatformStats:
    handle = str(config["handle"])
    client = HttpClient()

    info = _api(client, "user.info", handles=handle)[0]
    time.sleep(1.1)
    status = _api(client, "user.status", handle=handle)
    time.sleep(1.1)
    try:
        rating_history = _api(client, "user.rating", handle=handle)
    except RuntimeError:
        rating_history = []

    first_ac: dict[tuple, int] = {}
    for submission in status:
        if submission.get("verdict") != "OK":
            continue
        problem = submission.get("problem") or {}
        key = (
            problem.get("contestId"),
            problem.get("problemsetName"),
            problem.get("index"),
            problem.get("name"),
        )
        timestamp = int(submission.get("creationTimeSeconds") or 0)
        if not timestamp:
            continue
        if key not in first_ac or timestamp < first_ac[key]:
            first_ac[key] = timestamp

    daily: dict[date, int] = defaultdict(int)
    for timestamp in first_ac.values():
        day = datetime.fromtimestamp(timestamp, tz).date()
        daily[day] += 1

    rating = info.get("rating")
    max_rating = info.get("maxRating")
    rank = info.get("rank") or ("unrated" if rating is None else None)

    stats = [
        ("通过", str(len(first_ac)), None),
        ("Rating", str(rating) if rating is not None else "Unrated", _rank_color(rating)),
        ("最高", str(max_rating) if max_rating is not None else "—", _rank_color(max_rating)),
        ("比赛", str(len(rating_history)), None),
    ]

    log(
        "codeforces",
        f"{info.get('handle', handle)}: {len(first_ac)} solved, "
        f"rating={rating}, contests={len(rating_history)}, rank={rank}",
    )

    return PlatformStats(
        key="codeforces",
        handle=str(info.get("handle") or handle),
        stats=stats,
        daily=dict(daily),
        total=len(first_ac),
        cumulative_label="累积通过",
        daily_label="新通过",
        accent="#e11d48",
        updated_at=datetime.now(tz),
    )
