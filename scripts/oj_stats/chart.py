"""Render a compact OJ activity card (three can sit side by side)."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path

from common import PlatformStats, iter_days, logical_date, svg_escape, text_width

WIDTH = 300
HEIGHT = 212

FONT = (
    "system-ui,-apple-system,'Segoe UI','Noto Sans SC','PingFang SC',"
    "'Microsoft YaHei',sans-serif"
)

LEFT = 16.0
RIGHT = 284.0
PLOT_TOP = 158.0
PLOT_BOTTOM = 190.0

# (accent for small text on white, accent on dark, accent text on dark)
PALETTE = {
    "luogu": ("#2563eb", "#60a5fa", "#93c5fd"),
    "codeforces": ("#be123c", "#fb7185", "#fda4af"),
    "leetcode": ("#b45309", "#fbbf24", "#fcd34d"),
    "nowcoder": ("#047857", "#34d399", "#6ee7b7"),
}


def _esc(value: str) -> str:
    return svg_escape(str(value))


def _palette(stats: PlatformStats) -> tuple[str, str, str]:
    light_text, dark_accent, dark_text = PALETTE.get(
        stats.key, (stats.accent, stats.accent, stats.accent)
    )
    return light_text, dark_accent, dark_text


def _rules(stats: PlatformStats, dark: bool) -> str:
    light_text, dark_accent, dark_text = _palette(stats)
    if dark:
        colors = {
            "bg": ("#0d1117", "#30363d"),
            "t1": "#e6edf3",
            "t2": "#8b949e",
            "t3": "#8b949e",
            "t4": "#6e7681",
            "hr": "#21262d",
            "accent": dark_accent,
            "accent_text": dark_text,
            "ring": "#0d1117",
        }
    else:
        colors = {
            "bg": ("#ffffff", "#e6ebf2"),
            "t1": "#0f172a",
            "t2": "#64748b",
            "t3": "#94a3b8",
            "t4": "#a8b3c4",
            "hr": "#eef2f7",
            "accent": stats.accent,
            "accent_text": light_text,
            "ring": "#ffffff",
        }
    bg_fill, bg_stroke = colors["bg"]
    return f"""
    .bg {{ fill: {bg_fill}; stroke: {bg_stroke}; }}
    .t1 {{ fill: {colors['t1']}; }}
    .t2 {{ fill: {colors['t2']}; }}
    .t3 {{ fill: {colors['t3']}; }}
    .t4 {{ fill: {colors['t4']}; }}
    .hr {{ stroke: {colors['hr']}; }}
    .accent {{ fill: {colors['accent']}; }}
    .accent-text {{ fill: {colors['accent_text']}; }}
    .accent-stroke {{ stroke: {colors['accent']}; }}
    .ring {{ stroke: {colors['ring']}; }}
    .stop {{ stop-color: {colors['accent']}; }}
"""


def _styles(stats: PlatformStats, theme: str) -> str:
    if theme == "dark":
        return _rules(stats, True)
    styles = _rules(stats, False)
    if theme == "auto":
        styles += "@media (prefers-color-scheme: dark) {" + _rules(stats, True) + "}"
    return styles


def _month_labels(days: list[date], x_of, right_limit: float) -> str:
    chunks: list[str] = []
    last_x = -1e9
    for index, day in enumerate(days):
        if index != 0 and day.day != 1:
            continue
        x = x_of(index)
        if index != 0 and x - last_x < 44:
            continue
        label = f"{day.month}月"
        label_width = text_width(label, 8.5)
        if index != 0 and x + label_width / 2 > right_limit:
            continue
        anchor = "start" if index == 0 else "middle"
        if anchor == "middle" and x + label_width / 2 > RIGHT:
            anchor = "end"
            x = RIGHT
        chunks.append(
            f'<text x="{x:.1f}" y="203" font-size="8.5" class="t4" '
            f'text-anchor="{anchor}">{label}</text>'
        )
        last_x = x
    return "".join(chunks)


def _sparkline(values: list[int]) -> tuple[str, str, tuple[float, float]]:
    low = float(min(values))
    high = float(max(values))
    if high - low < 1:
        high = low + 1
    span = high - low
    low = max(0.0, low - span * 0.15)
    high += span * 0.15

    count = len(values)
    points = [
        (
            LEFT + (RIGHT - LEFT) * index / max(1, count - 1),
            PLOT_BOTTOM - (value - low) / (high - low) * (PLOT_BOTTOM - PLOT_TOP),
        )
        for index, value in enumerate(values)
    ]
    line = "M " + " L ".join(f"{x:.2f},{y:.2f}" for x, y in points)
    area = (
        f"M {LEFT:.2f},{PLOT_BOTTOM:.2f} L "
        + " L ".join(f"{x:.2f},{y:.2f}" for x, y in points)
        + f" L {RIGHT:.2f},{PLOT_BOTTOM:.2f} Z"
    )
    return line, area, points[-1]


def _stat_columns(items: list[tuple[str, str, str | None]]) -> str:
    coords = (16.0, 109.0, 202.0)
    chunks: list[str] = []
    for index, (label, value, _color) in enumerate(items[:3]):
        x = coords[index]
        chunks.append(
            f'<text x="{x}" y="115" font-size="9" class="t3">{_esc(label)}</text>'
            f'<text x="{x}" y="131" font-size="12.5" font-weight="600" class="t1">'
            f"{_esc(value)}</text>"
        )
    return "".join(chunks)


def _utc_offset(moment: datetime) -> str:
    offset = moment.utcoffset()
    if offset is None:
        return ""
    minutes = int(offset.total_seconds() // 60)
    sign = "+" if minutes >= 0 else "-"
    hours, mins = divmod(abs(minutes), 60)
    return f"UTC{sign}{hours}" + (f":{mins:02d}" if mins else "")


def build_svg(
    stats: PlatformStats,
    window_days: int = 60,
    daily_days: int = 30,
    theme: str = "auto",
) -> str:
    today = logical_date(stats.updated_at, stats.day_start_hour)
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

    line_path, area_path, end_point = _sparkline(cumulative)
    active_days = sum(1 for value in values if value > 0)

    def cum_x(index: int) -> float:
        if len(days) <= 1:
            return LEFT
        return LEFT + (RIGHT - LEFT) * index / (len(days) - 1)

    hero_label, hero_value = (
        (stats.stats[0][0], stats.stats[0][1])
        if stats.stats
        else ("通过", f"{stats.total:,}")
    )
    side_stats = list(stats.stats[1:4])
    while len(side_stats) < 3:
        side_stats.append(("", "", None))

    platform_name = PLATFORM_NAME(stats.key)
    footer_time = f"{stats.updated_at:%m-%d %H:%M} {_utc_offset(stats.updated_at)}"
    footer_label = f"更新 {footer_time}"
    aria = (
        f"{platform_name} {stats.handle} 最近 {window_days} 天"
        f"{stats.cumulative_label}，更新于 {footer_time}"
    )

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-label="{_esc(aria)}">
  <title>{_esc(aria)}</title>
  <style>{_styles(stats, theme)}</style>
  <defs>
    <linearGradient id="area-{stats.key}" x1="0" y1="{PLOT_TOP}" x2="0" y2="{PLOT_BOTTOM}" gradientUnits="userSpaceOnUse">
      <stop offset="0%" class="stop" stop-opacity="0.34"/>
      <stop offset="72%" class="stop" stop-opacity="0.10"/>
      <stop offset="100%" class="stop" stop-opacity="0.02"/>
    </linearGradient>
  </defs>
  <g font-family="{FONT}">
    <rect x="0.5" y="0.5" width="{WIDTH - 1}" height="{HEIGHT - 1}" rx="14" class="bg"/>
    <rect x="16" y="14" width="3" height="18" rx="1.5" class="accent"/>
    <text x="27" y="29" font-size="15.5" font-weight="700" class="t1">{_esc(platform_name)}</text>
    <text x="{RIGHT}" y="28.5" font-size="10" class="t3" text-anchor="end">{_esc(stats.handle)}</text>
    <text x="{LEFT}" y="50" font-size="10" class="t3">{_esc(hero_label)}</text>
    <text x="{LEFT}" y="83" font-size="34" font-weight="700" class="t1" letter-spacing="-.5">{_esc(hero_value)}</text>
    <line x1="{LEFT}" y1="97" x2="{RIGHT}" y2="97" class="hr"/>
    {_stat_columns(side_stats)}
    <text x="{LEFT}" y="150" font-size="9.5" class="t2">{_esc(stats.cumulative_label)} · 近 {window_days} 天</text>
    <text x="{RIGHT}" y="150" font-size="10.5" font-weight="700" class="accent-text" text-anchor="end">+{window_sum:,}</text>
    {'' if active_days <= 3 else f'<path d="{area_path}" fill="url(#area-{stats.key})"/>'}
    <path d="{line_path}" fill="none" class="accent-stroke" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/>
    <circle cx="{end_point[0]:.2f}" cy="{end_point[1]:.2f}" r="2.7" class="accent ring" stroke-width="1.5"/>
    {_month_labels(days, cum_x, RIGHT - text_width(footer_label, 8) - 12)}
    <text x="{RIGHT}" y="203" font-size="8" class="t3" text-anchor="end">{_esc(footer_label)}</text>
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
    out_path.write_text(
        build_svg(stats, window_days, daily_days, theme="auto"), encoding="utf-8"
    )
    dark_path = out_path.with_name(f"{out_path.stem}-dark{out_path.suffix}")
    dark_path.write_text(
        build_svg(stats, window_days, daily_days, theme="dark"), encoding="utf-8"
    )
