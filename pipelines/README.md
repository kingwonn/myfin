# pipelines — 数据管道（Phase 1 起逐步建设）

规划中的最小集（见 `docs/01-architecture.md` 与 `docs/02-tech-stack.md`）：

- `market/`：行情快照与异动检测（akshare + OpenBB 薄封装）
- `filings/`：交易所公告定向抓取（巨潮 / HKEX / EDGAR）
- `events/`：扫描产出的结构化事件库

约定：所有管道输出可重建（缓存进 `data/cache/`，已 gitignore），结构化结论才入库。
