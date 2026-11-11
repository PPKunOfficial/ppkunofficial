"""Fetch LeetCode CN progress/calendar data from the public GraphQL endpoints."""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from common import HttpClient, PlatformStats, fmt_int, log

BASE = "https://leetcode.cn"
GRAPHQL = f"{BASE}/graphql/"
GRAPHQL_NOJ = f"{BASE}/graphql/noj-go/"


def _data(client: HttpClient, url: str, query: str, variables: dict, referer: str):
    payload = client.post_json(
        url,
        {"query": query, "variables": variables},
        headers={"Referer": referer, "Origin": BASE},
        tries=4,
    )
    if payload.get("errors"):
        messages = "; ".join(str(err.get("message")) for err in payload["errors"])
        raise RuntimeError(messages)
    return payload.get("data") or {}


def fetch(config: dict, tz: ZoneInfo, today: date) -> PlatformStats:
    slug = str(config["user_slug"])
    referer = f"{BASE}/u/{slug}/"
    client = HttpClient()

    profile_data = _data(
        client,
        GRAPHQL,
        """
        query userProfilePublicProfile($userSlug: String!) {
          userProfilePublicProfile(userSlug: $userSlug) {
            username
            submissionProgress { acSubmissions totalSubmissions }
          }
        }
        """,
        {"userSlug": slug},
        referer,
    )
    profile = profile_data.get("userProfilePublicProfile")
    if not profile:
        raise RuntimeError(f"力扣用户 {slug} 不存在")

    progress_data = _data(
        client,
        GRAPHQL,
        """
        query userProfileUserQuestionProgressV2($userSlug: String!) {
          userProfileUserQuestionProgressV2(userSlug: $userSlug) {
            numAcceptedQuestions { difficulty count }
          }
        }
        """,
        {"userSlug": slug},
        referer,
    )
    progress = progress_data.get("userProfileUserQuestionProgressV2") or {}
    accepted = {"EASY": 0, "MEDIUM": 0, "HARD": 0}
    for item in progress.get("numAcceptedQuestions") or []:
        key = str(item.get("difficulty") or "").upper()
        if key in accepted:
            accepted[key] = int(item.get("count") or 0)
    accepted_total = sum(accepted.values())

    calendar_data = _data(
        client,
        GRAPHQL_NOJ,
        """
        query userProfileCalendar($userSlug: String!, $year: Int) {
          userCalendar(userSlug: $userSlug, year: $year) {
            submissionCalendar
            activeYears
          }
        }
        """,
        {"userSlug": slug, "year": today.year},
        referer,
    )
    calendar = calendar_data.get("userCalendar") or {}
    active_years = set(calendar.get("activeYears") or [])
    active_years.add(today.year)

    calendars = [calendar.get("submissionCalendar") or "{}"]
    for year in sorted(active_years - {today.year}):
        extra = _data(
            client,
            GRAPHQL_NOJ,
            """
            query userProfileCalendar($userSlug: String!, $year: Int) {
              userCalendar(userSlug: $userSlug, year: $year) {
                submissionCalendar
              }
            }
            """,
            {"userSlug": slug, "year": year},
            referer,
        ).get("userCalendar") or {}
        calendars.append(extra.get("submissionCalendar") or "{}")

    daily: dict[date, int] = defaultdict(int)
    for raw in calendars:
        try:
            parsed = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            continue
        for timestamp, count in parsed.items():
            try:
                day = datetime.fromtimestamp(int(timestamp), timezone.utc).date()
            except (ValueError, OSError, TypeError):
                continue
            daily[day] += int(count or 0)

    total_submissions = int((profile.get("submissionProgress") or {}).get("totalSubmissions") or 0)
    total_submissions = max(total_submissions, sum(daily.values()))

    stats = [
        ("通过", str(accepted_total), None),
        ("提交", fmt_int(total_submissions), None),
        ("易/中/难", f"{accepted['EASY']}/{accepted['MEDIUM']}/{accepted['HARD']}", None),
        ("今日", f"+{daily.get(today, 0)}", None),
    ]

    log(
        "leetcode",
        f"{profile.get('username', slug)}: {accepted_total} accepted, "
        f"{total_submissions} submissions, {len(daily)} active days",
    )

    return PlatformStats(
        key="leetcode",
        handle=str(profile.get("username") or slug),
        stats=stats,
        daily=dict(daily),
        total=total_submissions,
        cumulative_label="累积提交",
        daily_label="每日提交",
        accent="#f59e0b",
        updated_at=datetime.now(tz),
        note="力扣公开接口只提供提交日历，曲线按提交次数统计",
    )
