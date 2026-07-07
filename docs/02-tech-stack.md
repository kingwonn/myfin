# 02 · 技术栈选型：站在谁的肩膀上

原则：**尽量不造轮子**。每个需求先问"GitHub 上最好的现成方案是什么"，只有当现成方案与我们的 AI-native 架构冲突时才自建。

状态: DRAFT——待深度研究报告（第4条线）交叉验证后定稿。

## 选型总表

| 需求 | 首选 | 备选 | 自建? | 说明 |
|------|------|------|-------|------|
| Agent 运行时/编排 | Claude Code（技能 + Workflow + Routines） | LangGraph, OpenHands | 否 | 我们的编排需求（并行研究、定时扫描）Claude Code 原生覆盖，少一层抽象就少一层维护 |
| 深度研究 | Claude Code deep-research workflow | GPT-Researcher | 否 | 已内置多路搜索+对抗验证 |
| 美股/全球数据 | OpenBB Platform | yfinance | 否 | OpenBB 聚合多数据源，CLI/Python 双接口，AI 友好 |
| A股数据 | akshare | tushare(需积分), baostock | 否 | akshare 免费全面，社区活跃 |
| 港股/日韩数据 | OpenBB + yfinance | 交易所公开数据 | 部分 | 覆盖度需验证 |
| 公告/新闻流 | WebSearch + RSS | 巨潮资讯爬虫 | 后期小轮子 | 交易所公告结构化抓取可能需要自建薄层 |
| 回测/量化研究 | qlib (微软) | vectorbt, backtrader | 否 | Phase 2 再引入；qlib 偏 A股研究生态 |
| 组合跟踪 | 自建轻量(YAML+脚本) | ghostfolio | 小轮子 | 我们的"论点驱动组合"模型市面上没有现成对应物——这是值得造的轮子 |
| 知识库/留痕 | git + Markdown/YAML | Obsidian, Notion | 否 | 仓库即系统的根基 |
| 定时调度 | Claude Code Routines / GitHub Actions | cron + 自托管 | 否 | 无人值守扫描 |

## 值得深入评估的项目清单（待研究报告补充验证）

- **OpenBB**（openbb-finance/OpenBB）：开源投研平台，数据聚合层。评估点：中国市场覆盖、API 稳定性。
- **qlib**（microsoft/qlib）：AI 量化框架。评估点：与论点驱动流程的嫁接成本。
- **akshare**（akfamily/akshare）：A股全品类数据。评估点：接口变动频率（历史上较频繁，需要薄封装隔离）。
- **vectorbt**：轻量高速回测，若 qlib 太重则降级到此。
- **GPT-Researcher / STORM**：研究 agent 的提示词与流程设计值得借鉴（即使不用其框架）。

## 自建部分（"必须造的轮子"）

1. **论点-标的-事件关联层**：thesis 文件、watchlist YAML、事件流之间的引用与一致性检查脚本（很薄，几百行以内）。
2. **交易所公告监听薄层**：巨潮/HKEX/EDGAR 关键公告的定向抓取与结构化（Phase 1 后期）。
3. **`/scan` 的行情异动通道**：基于 akshare/OpenBB 的价格/成交量异动检测（Phase 1）。

## 明确不做

- 不自建行情数据库/K线存储（用现成 API，缓存即弃）。
- 不做交易执行对接（本系统止步于决策支持）。
- 不引入重型工作流引擎（Airflow 之类）——git + Routines 足够。
