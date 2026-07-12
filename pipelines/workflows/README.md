# pipelines/workflows — 研究引擎脚本（评审 Y-8 整改：仓库即系统闭合）

本目录存放全部多代理研究工作流脚本（Workflow 工具执行），2026-07-12 从会话运行目录整体入库。

- `dr-tiered-*.js`：deep-research 管线（Scope→Search→Fetch→3票对抗验证→Synthesize），按主题分文件；全部含模型分层（search/fetch=Sonnet 5，verify=1×Opus 4.8+2×Sonnet 5，规划/综合=Fable 5）与抓取兜底补丁（WebFetch 403/429 时用搜索快照重建）
- `deep-research-*.js` / `sota-methodology-survey-*.js`：早期版本（R1/R2a 时期，未分层），保留作演进记录
- `daily-scan-incremental-*.js`：日环增量扫描（5 组 Sonnet 并行）

运行方式：Workflow({scriptPath: "pipelines/workflows/<file>.js", args: "<研究问题>"})。
逐条投票记录（journal.jsonl）在会话运行目录，容器回收即失——重要轮次的完整 claims 已固化进各研究报告的票数标注。
