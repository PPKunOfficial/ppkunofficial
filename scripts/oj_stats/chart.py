"""Render a two-panel OJ activity chart as a GitHub-friendly SVG."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from common import (
    PlatformStats,
    fmt_int,
    iter_days,
    nice_ceil,
    svg_escape,
    text_width,
)

WIDTH = 900
HEIGHT = 300
FONT = (
    "system-ui,-apple-system,'Segoe UI','Noto Sans SC','PingFang SC',"
    "'Microsoft YaHei',sans-serif"
)

LEFT_X0, LEFT_X1 = 44.0, 556.0
RIGHT_X0, RIGHT_X1 = 596.0, 872.0
CHART_TOP, CHART_BOTTOM = 82.0, 250.0

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


def _stats_row(stats: list[tuple[str, str, str | None]], x_right: float, baseline: float) -> str:
    label_size, value_size, sep_size = 11.5, 13.0, 11.0
    sep = "·"
    widths: list[float] = []
    for label, value, _ in stats:
        widths.append(text_width(label, label_size) + 4 + text_width(value, value_size))
    sep_width = text_width(sep, sep_size) + 12
    total_width = sum(widths) + sep_width * (len(stats) - 1)
    x = x_right - total_width
    chunks: list[str] = []
    for index, (label, value, color) in enumerate(stats):
        chunks.append(
            f'<text x="{x:.1f}" y="{baseline:.1f}" font-size="{label_size}" '
            f'fill="#8a94a6">{_esc(label)}</text>'
        )
        x += text_width(label, label_size) + 4
        chunks.append(
            f'<text x="{x:.1f}" y="{baseline:.1f}" font-size="{value_size}" '
            f'font-weight="600" fill="{color or TEXT}">{_esc(value)}</text>'
        )
        x += text_width(value, value_size)
        if index < len(stats) - 1:
            x += 6
            chunks.append(
                f'<text x="{x:.1f}" y="{baseline:.1f}" font-size="{sep_size}" '
                f'fill="#cbd5e1">{sep}</text>'
            )
            x += text_width(sep, sep_size) + 6
    return "".join(chunks)


def _month_labels(days: list[date], x_of, last_x_threshold: float = 48) -> str:
    chunks: list[str] = []
    last_x = -1e9
    for index, day in enumerate(days):
        if index == 0 or day.day == 1:
            x = x_of(index)
            if index != 0 and x - last_x < last_x_threshold:
                continue
            chunks.append(
                f'<text x="{x:.1f}" y="268" font-size="9.5" fill="{FAINT}" '
                f'text-anchor="middle">{day.month}月</text>'
            )
            last_x = x
    return "".join(chunks)


def _day_labels(days: list[date], x_of, step: int = 7) -> str:
    chunks: list[str] = []
    last_x = -1e9
    for index in range(0, len(days), step):
        x = x_of(index)
        if x - last_x < 44:
            continue
        day = days[index]
        chunks.append(
            f'<text x="{x:.1f}" y="268" font-size="9.5" fill="{FAINT}" '
            f'text-anchor="middle">{day.month}-{day.day:02d}</text>'
        )
        last_x = x
    return "".join(chunks)


def build_svg(stats: PlatformStats, window_days: int = 180, daily_days: int = 30) -> str:
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

    def left_x(index: int) -> float:
        if len(days) <= 1:
            return LEFT_X0
        return LEFT_X0 + (LEFT_X1 - LEFT_X0) * index / (len(days) - 1)

    def left_y(value: float) -> float:
        return CHART_BOTTOM - (value / y_max) * (CHART_BOTTOM - CHART_TOP)

    points = [(left_x(i), left_y(value)) for i, value in enumerate(cumulative)]
    line_path = "M " + " L ".join(f"{x:.2f},{y:.2f}" for x, y in points)
    area_path = (
        f"M {LEFT_X0:.2f},{CHART_BOTTOM:.2f} "
        f"L {points[0][0]:.2f},{points[0][1]:.2f} "
        + " ".join(f"L {x:.2f},{y:.2f}" for x, y in points[1:])
        + f" L {LEFT_X1:.2f},{CHART_BOTTOM:.2f} Z"
    )

    dot_indices = set(range(0, len(points), 7))
    dot_indices.add(len(points) - 1)
    dots = "".join(
        f'<circle cx="{points[i][0]:.2f}" cy="{points[i][1]:.2f}" r="'
        + ("4.2" if i == len(points) - 1 else "2.2")
        + f'" fill="{stats.accent}"'
        + (' stroke="#ffffff" stroke-width="2"' if i == len(points) - 1 else "")
        + ' opacity="0.95"/>'
        for i in sorted(dot_indices)
    )

    # Right panel: last N days of daily activity + 7-day moving average.
    right_days = days[-daily_days:] if len(days) >= daily_days else days
    right_values = values[-daily_days:] if len(values) >= daily_days else values
    max_daily = max(right_values) if right_values else 0
    y_max_daily = nice_ceil(max_daily) or 1
    if y_max_daily % 2:
        y_max_daily += 1
    slot = (RIGHT_X1 - RIGHT_X0) / max(1, len(right_values))
    bar_width = min(6.0, slot * 0.62)

    def right_x(index: int) -> float:
        return RIGHT_X0 + slot * (index + 0.5)

    def right_y(value: float) -> float:
        return CHART_BOTTOM - (value / y_max_daily) * (CHART_BOTTOM - CHART_TOP)

    bars: list[str] = []
    for index, value in enumerate(right_values):
        if value <= 0:
            continue
        height = CHART_BOTTOM - right_y(value)
        fill = stats.accent if index == len(right_values) - 1 else BAR
        opacity = "0.95" if index == len(right_values) - 1 else "0.86"
        bars.append(
            f'<rect x="{right_x(index) - bar_width / 2:.2f}" y="{right_y(value):.2f}" '
            f'width="{bar_width:.2f}" height="{height:.2f}" rx="1.6" '
            f'fill="{fill}" opacity="{opacity}"/>'
        )

    ma_values: list[float] = []
    for index in range(len(right_values)):
        low = max(0, index - 6)
        window = right_values[low : index + 1]
        ma_values.append(sum(window) / len(window))
    ma_points = [(right_x(i), right_y(v)) for i, v in enumerate(ma_values)]
    ma_path = "M " + " L ".join(f"{x:.2f},{y:.2f}" for x, y in ma_points)
    ma_dots = "".join(
        f'<circle cx="{x:.2f}" cy="{y:.2f}" r="1.7" fill="{stats.accent}" opacity="0.9"/>'
        for x, y in ma_points
    )

    left_ticks = [0, y_max / 2, y_max]
    right_ticks = [0, y_max_daily / 2, y_max_daily]

    grid: list[str] = []
    for value in left_ticks:
        y = left_y(value)
        grid.append(
            f'<line x1="{LEFT_X0:.1f}" y1="{y:.1f}" x2="{LEFT_X1:.1f}" y2="{y:.1f}" '
            f'stroke="{"#e2e8f0" if value == 0 else GRID}" stroke-width="1"/>'
        )
        grid.append(
            f'<text x="{LEFT_X0 - 7:.1f}" y="{y + 3.2:.1f}" font-size="9.5" '
            f'fill="{FAINT}" text-anchor="end">{_tick(value)}</text>'
        )
    for value in right_ticks:
        y = right_y(value)
        grid.append(
            f'<line x1="{RIGHT_X0:.1f}" y1="{y:.1f}" x2="{RIGHT_X1:.1f}" y2="{y:.1f}" '
            f'stroke="{"#e2e8f0" if value == 0 else GRID}" stroke-width="1"/>'
        )
        grid.append(
            f'<text x="{RIGHT_X0 - 7:.1f}" y="{y + 3.2:.1f}" font-size="9.5" '
            f'fill="{FAINT}" text-anchor="end">{_tick(value)}</text>'
        )

    has_data = max_cum > 0 or max_daily > 0
    empty_state = ""
    if not has_data:
        empty_state = (
            f'<text x="{(LEFT_X0 + RIGHT_X1) / 2:.1f}" y="{(CHART_TOP + CHART_BOTTOM) / 2:.1f}" '
            f'font-size="12" fill="{FAINT}" text-anchor="middle">暂无公开数据</text>'
        )

    platform_name = PLATFORM_NAME(stats.key)
    name_width = text_width(platform_name, 18)
    handle_svg = (
        f'<text x="{38 + name_width + 10:.1f}" y="37" font-size="12.5" '
        f'fill="{MUTED}">{_esc(stats.handle)}</text>'
    )

    footer = f"更新于 {stats.updated_at:%Y-%m-%d %H:%M} UTC+8"
    if stats.note:
        footer += f" · {stats.note}"

    aria = (
        f"{PLATFORM_NAME(stats.key)} {stats.handle} 最近 {window_days} 天"
        f"{stats.cumulative_label}与最近 {daily_days} 天{stats.daily_label}"
    )

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-label="{_esc(aria)}">
  <title>{_esc(aria)}</title>
  <defs>
    <linearGradient id="area-{stats.key}" x1="0" y1="{CHART_TOP}" x2="0" y2="{CHART_BOTTOM}" gradientUnits="userSpaceOnUse">
      <stop offset="0%" stop-color="{stats.accent}" stop-opacity="0.42"/>
      <stop offset="72%" stop-color="{stats.accent}" stop-opacity="0.10"/>
      <stop offset="100%" stop-color="{stats.accent}" stop-opacity="0.015"/>
    </linearGradient>
  </defs>
  <g font-family="{FONT}">
    <rect x="0.5" y="0.5" width="{WIDTH - 1}" height="{HEIGHT - 1}" rx="18" fill="#ffffff" stroke="#e6ebf2"/>
    <rect x="24" y="20" width="4" height="22" rx="2" fill="{stats.accent}"/>
    <text x="38" y="37" font-size="18" font-weight="700" fill="{TEXT}">{_esc(platform_name)}</text>
    {handle_svg}
    {_stats_row(stats.stats, 872, 36)}
    <text x="{LEFT_X0}" y="66" font-size="11.5" fill="{MUTED}">{_esc(stats.cumulative_label)} · 近 {window_days} 天</text>
    <text x="{RIGHT_X0}" y="66" font-size="11.5" fill="{MUTED}">{_esc(stats.daily_label)} · 近 {daily_days} 天</text>
    <text x="{RIGHT_X1}" y="66" font-size="9" fill="#a8b3c4" text-anchor="end">柱 每日 · 线 7 日均</text>
    <line x1="576" y1="{CHART_TOP}" x2="576" y2="{CHART_BOTTOM}" stroke="#f1f5f9" stroke-width="1"/>
    {''.join(grid)}
    <path d="{area_path}" fill="url(#area-{stats.key})"/>
    <path d="{line_path}" fill="none" stroke="{stats.accent}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>
    {dots}
    {''.join(bars)}
    <path d="{ma_path}" fill="none" stroke="{stats.accent}" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" opacity="0.9"/>
    {ma_dots}
    {empty_state}
    {_month_labels(days, left_x)}
    {_day_labels(right_days, right_x)}
    <text x="{RIGHT_X1}" y="288" font-size="9" fill="{FAINT}" text-anchor="end">{_esc(footer)}</text>
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
