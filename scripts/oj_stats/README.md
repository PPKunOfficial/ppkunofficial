# OJ Stats

把洛谷 / Codeforces / 力扣的刷题数据渲染成紧凑的 SVG 卡片，三张可以并排放在 profile README 的同一行：

- 上半部分：近 60 天累积量（面积图）
- 下半部分：近 30 天每日新增（柱状图 + 7 日均线）

## 数据源

| 平台 | 来源 | 统计口径 |
| --- | --- | --- |
| 洛谷 | 公开用户页内嵌的 `lentille-context` JSON | 每天去重通过的题目数 |
| Codeforces | 官方 API `user.info` / `user.status` / `user.rating` | 每题首次 AC 的时间 |
| 力扣（CN） | GraphQL `userProfilePublicProfile` + `userCalendar` | 公开接口只有提交日历，因此曲线按提交次数统计 |

力扣的通过题数与难度分布来自 `userProfileUserQuestionProgressV2`，显示在卡片头部。

### 统计日分界

每天以 `day_start_hour`（默认 05:00）作为分界：凌晨 05:00 前的提交算到前一天，
夜里刷题不会被拆到两个自然日。Codeforces 有精确时间戳，可以完整重分桶；洛谷和
力扣公开接口只提供按天聚合的数据，因此只有在 05:00 前抓取时，才会把平台当天桶
并入前一天（抓取时已过分界则无法再拆分）。

## 配置

`config.json` 里是账号和统计窗口：

```json
{
  "timezone": "Asia/Shanghai",
  "day_start_hour": 5,
  "window_days": 60,
  "daily_days": 30,
  "platforms": {
    "luogu": { "enabled": true, "uid": 311493 },
    "codeforces": { "enabled": true, "handle": "PPyyk." },
    "leetcode": { "enabled": true, "user_slug": "pp-kun" },
    "nowcoder": { "enabled": false, "uid": null }
  }
}
```

## 本地运行

```bash
python3 scripts/oj_stats/main.py
```

输出写入 `assets/oj/*.svg`。脚本只用 Python 标准库，无需安装依赖。

## 定时任务

`.github/workflows/oj-stats.yml` 每天 19:17 UTC（北京时间 03:17）触发，也可以手动
`workflow_dispatch`。GitHub 的 schedule 不保证准点，实际运行可能延迟；卡片右下角和
bot 提交时间都使用 UTC+8，Actions 日志仍显示 UTC。渲染成功后由 bot 自动提交
`assets/oj/`。

## 后续接牛客

在 `fetch_nowcoder.py` 中实现
`fetch(config, tz, now, day_start_hour) -> PlatformStats`，然后在 `main.py` 的
`FETCHERS` 里注册并打开 `config.json` 的开关即可。`now` 是带时区的当前时间，
分桶时请用 `common.logical_date` / `common.fold_early_morning`。卡片布局和渲染会自动复用。
