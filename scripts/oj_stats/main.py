"""Entry point: fetch every enabled platform and render SVG cards."""

from __future__ import annotations

import json
import sys
import traceback
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from chart import write_chart
from common import log
from fetch_codeforces import fetch as fetch_codeforces
from fetch_leetcode import fetch as fetch_leetcode
from fetch_luogu import fetch as fetch_luogu

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUT_DIR = ROOT / "assets" / "oj"

FETCHERS = {
    "luogu": fetch_luogu,
    "codeforces": fetch_codeforces,
    "leetcode": fetch_leetcode,
}


def main() -> int:
    config = json.loads((HERE / "config.json").read_text(encoding="utf-8"))
    tz = ZoneInfo(config.get("timezone", "Asia/Shanghai"))
    window_days = int(config.get("window_days", 180))
    daily_days = int(config.get("daily_days", 30))
    now = datetime.now(tz)

    rendered: list[str] = []
    failed: list[str] = []
    skipped: list[str] = []

    for key, platform_config in (config.get("platforms") or {}).items():
        if not platform_config.get("enabled", False):
            skipped.append(key)
            continue
        fetcher = FETCHERS.get(key)
        if fetcher is None:
            log(key, "fetcher not implemented yet — keeping the previous chart")
            skipped.append(key)
            continue
        try:
            stats = fetcher(platform_config, tz, now.date())
            out_path = OUT_DIR / f"{key}.svg"
            write_chart(stats, out_path, window_days, daily_days)
            rendered.append(key)
            log(key, f"wrote {out_path.relative_to(ROOT)}")
        except Exception as exc:  # noqa: BLE001 - keep other platforms alive
            failed.append(key)
            log(key, f"FAILED: {exc}")
            traceback.print_exc(file=sys.stderr)

    print()
    print(f"rendered: {', '.join(rendered) or '-'}")
    print(f"failed:   {', '.join(failed) or '-'}")
    print(f"skipped:  {', '.join(skipped) or '-'}")

    for key in failed:
        print(f"::warning title=OJ stats::{key} update failed; previous chart kept")

    if not rendered and failed:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
