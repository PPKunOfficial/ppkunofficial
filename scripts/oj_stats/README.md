# OJ Stats

把洛谷 / Codeforces / 力扣的刷题数据渲染成两张图的 SVG 卡片：

- 左图：近 180 天累积量（面积图）
- 右图：近 30 天每日新增（柱状图 + 7 日均线）

## 数据源

| 平台 | 来源 | 统计口径 |
| --- | --- | --- |
| 洛谷 | 公开用户页内嵌的 `lentille-context` JSON | 每天去重通过的题目数 |
| Codeforces | 官方 API `user.info` / `user.status` / `user.rating` | 每题首次 AC 的时间 |
| 力扣（CN） | GraphQL `userProfilePublicProfile` + `userCalendar` | 公开接口只有提交日历，因此曲线按提交次数统计 |

力扣的通过题数与难度分布来自 `userProfileUserQuestionProgressV2`，显示在卡片头部。

## 配置

账号都在 `config.json` 里：

```json
{
  "luogu": { "enabled": true, "uid": 311493 },
  "codeforces": { "enabled": true, "handle": "PPyyk." },
  "leetcode": { "enabled": true, "user_slug": "pp-kun" },
  "nowcoder": { "enabled": false, "uid": null }
}
```

## 本地运行

```bash
python3 scripts/oj_stats/main.py
```

输出写入 `assets/oj/*.svg`。脚本只用 Python 标准库，无需安装依赖。

## 定时任务

`.github/workflows/oj-stats.yml` 每天 19:17 UTC（北京时间 03:17）运行，也可以手动
`workflow_dispatch`。渲染成功后由 bot 自动提交 `assets/oj/`。

## 后续接牛客

在 `fetch_nowcoder.py` 中实现 `fetch(config, tz, today) -> PlatformStats`，然后在
`main.py` 的 `FETCHERS` 里注册并打开 `config.json` 的开关即可。卡片布局和渲染会自动复用。
