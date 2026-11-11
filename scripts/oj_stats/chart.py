"""Render a compact OJ activity card (three can sit side by side)."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from common import (
    PlatformStats,
    iter_days,
    nice_ceil,
    svg_escape,
    text_width,
)

WIDTH = 280
HEIGHT = 350
FONT = (
    "system-ui,-apple-system,'Segoe UI','Noto Sans SC','PingFang SC',"
    "'Microsoft YaHei',sans-serif"
)

LEFT = 32.0
RIGHT = 272.0
CUM_TOP, CUM_BOTTOM = 104.0, 190.0
DAY_TOP, DAY_BOTTOM = 228.0, 300.0

TEXT = "#0f172a"
MUTED = "#64748b"
FAINT = "#94a3b8"
GRID = "#eef2f7"
BAR = "#1f2937"


def _esc(value: str) -> str:
    return svg_escape(str(value))


def _tick(value: float) -> str:
    if abs(value - round(value)) < 1e-9:
        return str(int(round(value)))
    return f"{value:.1f}".rstrip("0").rstrip(".")


def _stats_grid(items: list[tuple[str, str, str | None]]) -> str:
    coords = [(14, 55), (146, 55), (14, 75), (146, 75)]
    chunks: list[str] = []
    for (label, value, color), (x, y) in zip(items, coords):
        chunks.append(
            f'<text x="{x}" y="{y}" font-size="10.5" fill="#8a94a6">{_esc(label)}</text>'
        )
        value_x = x + text_width(label, 10.5) + 4
        chunks.append(
            f'<text x="{value_x:.1f}" y="{y}" font-size="13.5" font-weight="600" '
            f'fill="{color or TEXT}">{_esc(value)}</text>'
        )
    return "".join(chunks)


def _month_labels(days: list[date], x_of) -> str:
    chunks: list[str] = []
    last_x = -1e9
    for index, day in enumerate(days):
        if index == 0 or day.day == 1:
            x = x_of(index)
            if index != 0 and x - last_x < 44:
                continue
            chunks.append(
                f'<text x="{x:.1f}" y="202" font-size="9" fill="{FAINT}" '
                f'text-anchor="middle">{day.month}月</text>'
            )
            last_x = x
    return "".join(chunks)


def _day_labels(days: list[date], x_of, step: int = 10) -> str:
    indices = list(range(0, len(days), step))
    if indices and indices[-1] != len(days) - 1:
        indices.append(len(days) - 1)
    chunks: list[str] = []
    last_x = -1e9
    for index in indices:
        x = x_of(index)
        if x - last_x < 40:
            continue
        day = days[index]
        chunks.append(
            f'<text x="{x:.1f}" y="314" font-size="9" fill="{FAINT}" '
            f'text-anchor="middle">{day.month}-{day.day:02d}</text>'
        )
        last_x = x
    return "".join(chunks)


def _grid(ticks: list[float], y_of) -> str:
    chunks: list[str] = []
    for value in ticks:
        y = y_of(value)
        chunks.append(
            f'<line x1="{LEFT}" y1="{y:.1f}" x2="{RIGHT}" y2="{y:.1f}" '
            f'stroke="{"#e2e8f0" if value == 0 else GRID}" stroke-width="1"/>'
        )
        chunks.append(
            f'<text x="26" y="{y + 3.0:.1f}" font-size="9.5" fill="{FAINT}" '
            f'text-anchor="end">{_tick(value)}</text>'
        )
    return "".join(chunks)


def build_svg(stats: PlatformStats, window_days: int = 60, daily_days: int = 30) -> str:
    today = stats.updated_at.date()
    window_start = today - timedelta(days=window_days)
    days = iter_days(window_start, today)
    values = [stats.daily.get(day, 0) for day in days]

    window_sum = sum(values)
    baseline = max(0, stats.total - window_sum)

    cumulative: list[int] = []
    running = baseline
    for value in values:
        running += value
        cumulative.append(running)

    max_cum = max(cumulative) if cumulative else 0
    y_max = nice_ceil(max_cum) or 1

    def cum_x(index: int) -> float:
        if len(days) <= 1:
            return LEFT
        return LEFT + (RIGHT - LEFT) * index / (len(days) - 1)

    def cum_y(value: float) -> float:
        return CUM_BOTTOM - (value / y_max) * (CUM_BOTTOM - CUM_TOP)

    points = [(cum_x(i), cum_y(value)) for i, value in enumerate(cumulative)]
    line_path = "M " + " L ".join(f"{x:.2f},{y:.2f}" for x, y in points)
    area_path = (
        f"M {LEFT:.2f},{CUM_BOTTOM:.2f} "
        f"L {points[0][0]:.2f},{points[0][1]:.2f} "
        + " ".join(f"L {x:.2f},{y:.2f}" for x, y in points[1:])
        + f" L {RIGHT:.2f},{CUM_BOTTOM:.2f} Z"
    )

    dot_indices = set(range(0, len(points), 7))
    dot_indices.add(len(points) - 1)
    dots = "".join(
        f'<circle cx="{points[i][0]:.2f}" cy="{points[i][1]:.2f}" r="'
        + ("3.3" if i == len(points) - 1 else "1.8")
        + f'" fill="{stats.accent}"'
        + (' stroke="#ffffff" stroke-width="1.6"' if i == len(points) - 1 else "")
        + ' opacity="0.95"/>'
        for i in sorted(dot_indices)
    )

    right_days = days[-daily_days:] if len(days) >= daily_days else days
    right_values = values[-daily_days:] if len(values) >= daily_days else values
    max_daily = max(right_values) if right_values else 0
    y_max_daily = nice_ceil(max_daily) or 1
    if y_max_daily % 2:
        y_max_daily += 1
    slot = (RIGHT - LEFT) / max(1, len(right_values))
    bar_width = min(5.0, slot * 0.62)

    def day_x(index: int) -> float:
        return LEFT + slot * (index + 0.5)

    def day_y(value: float) -> float:
        return DAY_BOTTOM - (value / y_max_daily) * (DAY_BOTTOM - DAY_TOP)

    bars: list[str] = []
    for index, value in enumerate(right_values):
        if value <= 0:
            continue
        height = DAY_BOTTOM - day_y(value)
        fill = stats.accent if index == len(right_values) - 1 else BAR
        opacity = "0.95" if index == len(right_values) - 1 else "0.86"
        bars.append(
            f'<rect x="{day_x(index) - bar_width / 2:.2f}" y="{day_y(value):.2f}" '
            f'width="{bar_width:.2f}" height="{height:.2f}" rx="1.4" '
            f'fill="{fill}" opacity="{opacity}"/>'
        )

    ma_values: list[float] = []
    for index in range(len(right_values)):
        low = max(0, index - 6)
        window = right_values[low : index + 1]
        ma_values.append(sum(window) / len(window))
    ma_points = [(day_x(i), day_y(v)) for i, v in enumerate(ma_values)]
    ma_path = "M " + " L ".join(f"{x:.2f},{y:.2f}" for x, y in ma_points)
    ma_dots = "".join(
        f'<circle cx="{x:.2f}" cy="{y:.2f}" r="1.35" fill="{stats.accent}" opacity="0.9"/>'
        for x, y in ma_points
    )

    has_data = max_cum > 0 or max_daily > 0
    empty_state = ""
    if not has_data:
        empty_state = (
            f'<text x="{(LEFT + RIGHT) / 2:.1f}" y="{(CUM_TOP + DAY_BOTTOM) / 2:.1f}" '
            f'font-size="10" fill="{FAINT}" text-anchor="middle">暂无公开数据</text>'
        )

    platform_name = PLATFORM_NAME(stats.key)
    name_width = text_width(platform_name, 16)
    handle_svg = (
        f'<text x="{23 + name_width + 6:.1f}" y="31" font-size="11.5" '
        f'fill="{MUTED}">{_esc(stats.handle)}</text>'
    )

    footer_time = f"更新于 {stats.updated_at:%m-%d %H:%M}"

    aria = (
        f"{platform_name} {stats.handle} 最近 {window_days} 天"
        f"{stats.cumulative_label}与最近 {daily_days} 天{stats.daily_label}"
    )

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-label="{_esc(aria)}">
  <title>{_esc(aria)}</title>
  <defs>
    <linearGradient id="area-{stats.key}" x1="0" y1="{CUM_TOP}" x2="0" y2="{CUM_BOTTOM}" gradientUnits="userSpaceOnUse">
      <stop offset="0%" stop-color="{stats.accent}" stop-opacity="0.42"/>
      <stop offset="72%" stop-color="{stats.accent}" stop-opacity="0.10"/>
      <stop offset="100%" stop-color="{stats.accent}" stop-opacity="0.015"/>
    </linearGradient>
  </defs>
  <g font-family="{FONT}">
    <rect x="0.5" y="0.5" width="{WIDTH - 1}" height="{HEIGHT - 1}" rx="14" fill="#ffffff" stroke="#e6ebf2"/>
    <rect x="14" y="16" width="3" height="19" rx="1.5" fill="{stats.accent}"/>
    <text x="25" y="31" font-size="16" font-weight="700" fill="{TEXT}">{_esc(platform_name)}</text>
    {handle_svg}
    {_stats_grid(stats.stats)}
    <text x="16" y="98" font-size="10.5" fill="{MUTED}">{_esc(stats.cumulative_label)} · 近 {window_days} 天</text>
    {_grid([0, y_max / 2, y_max], cum_y)}
    <path d="{area_path}" fill="url(#area-{stats.key})"/>
    <path d="{line_path}" fill="none" stroke="{stats.accent}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
    {dots}
    {_month_labels(days, cum_x)}
    <text x="16" y="222" font-size="10.5" fill="{MUTED}">{_esc(stats.daily_label)} · 近 {daily_days} 天</text>
    {_grid([0, y_max_daily / 2, y_max_daily], day_y)}
    {''.join(bars)}
    <path d="{ma_path}" fill="none" stroke="{stats.accent}" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round" opacity="0.9"/>
    {ma_dots}
    {empty_state}
    {_day_labels(right_days, day_x)}
    <text x="{RIGHT}" y="338" font-size="8.5" fill="{FAINT}" text-anchor="end">{_esc(footer_time)}</text>
  </g>
</svg>
"""


def PLATFORM_NAME(key: str) -> str:
    return {
        "luogu": "洛谷",
        "codeforces": "Codeforces",
        "leetcode": "力扣",
        "nowcoder": "牛客",
    }.get(key, key)


def write_chart(stats: PlatformStats, out_path: Path, window_days: int, daily_days: int) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(build_svg(stats, window_days, daily_days), encoding="utf-8")
