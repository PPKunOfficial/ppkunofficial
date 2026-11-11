"""Fetch Luogu practice statistics from the public user page."""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from common import (
    HttpClient,
    PlatformStats,
    fmt_int,
    log,
    parse_lentille,
)

BASE = "https://www.luogu.com.cn"


def fetch(config: dict, tz: ZoneInfo, today: date) -> PlatformStats:
    uid = int(config["uid"])
    client = HttpClient()
    url = f"{BASE}/user/{uid}"
    raw = client.get(
        url,
        headers={"Referer": f"{BASE}/user/{uid}"},
        tries=5,
    )
    data = parse_lentille(raw.decode("utf-8", "replace"), f" (uid={uid})")
    user = data.get("user") or {}

    total = user.get("passedProblemCount")
    if total is None:
        raise RuntimeError("用户开启了完全隐私保护，无法读取练习数据")

    daily: dict[date, int] = {}
    for raw_day, values in (data.get("dailyCounts") or {}).items():
        try:
            day = date.fromisoformat(str(raw_day))
        except ValueError:
            continue
        if isinstance(values, list) and values:
            daily[day] = int(values[0] or 0)

    name = str(user.get("name") or config.get("display_name") or f"uid {uid}")
    log("luogu", f"{name}: {total} passed, {len(daily)} active days in heatmap")

    stats = [
        ("通过", str(total), None),
        ("提交", fmt_int(user.get("submittedProblemCount")), None),
        ("排名", fmt_int(user.get("ranking")), None),
        ("今日", f"+{daily.get(today, 0)}", None),
    ]

    return PlatformStats(
        key="luogu",
        handle=name,
        stats=stats,
        daily=daily,
        total=int(total),
        cumulative_label="累积通过",
        daily_label="新通过",
        accent="#3b82f6",
        updated_at=datetime.now(tz),
    )
