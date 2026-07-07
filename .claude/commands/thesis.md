---
description: 新建或评审一个投资论点（强制证伪检查）
---

参数：$ARGUMENTS（论点主题，或已有 thesis 文件名）

**若是新建论点：**

0. 前置 gate：过一遍 CLAUDE.md 不为清单（看不懂商业模式→拒；活跃论点已 ≥8→先关一个）。咽喉类论点强制走 `docs/03-methodology.md` 的八问 checklist。
1. 先做一轮快速研究（WebSearch，必要时用 deep-research workflow）搞清楚：当前市场共识是什么？定价隐含了什么预期？
2. **bull/bear 对抗**（TradingAgents 结构，用两个并行子代理）：bull 代理写最强看多论据，bear 代理写最强反驳，各一轮互相反驳后汇总冲突点——冲突点就是证伪条件的素材。
3. **多风格评审团**（三个并行子代理）：价值型（Graham/Munger 视角）、逆向型（Burry 视角）、尾部风险型（Taleb 视角）各出独立评分与一句话意见。
4. 从 `theses/TEMPLATE.md` 派生新文件 `theses/YYYY-MM-DD-<slug>.md`，填写各章节；检索 `journal/beliefs.md` 中同环节/同标的的信念条目并注入评审。
5. **硬性检查，缺一不过：**
   - 1a"已计入的共识"与 1b"差异化图景"都非空；
   - 每个 claim 挂了具体 evidence，产能/订单数字双源互证；
   - "我错了的情形"至少一条可观测信号；退出三通道全部具体化；
   - 弹性测算有数字；仓位建议按 `docs/risk-rules.md` 算过；
   - 相关标的已在 watchlist（moat/risk 必填）。
6. 检查不通过则状态停留在 `draft`，并告诉用户缺什么。

**若是评审已有论点：**

1. 读取该 thesis 文件，逐条核对证据链是否仍然成立（用 WebSearch 更新关键事实）。
2. 检查证伪条件与触发器是否命中。
3. 输出评审结论：维持 / 加强 / 削弱 / 证伪，并更新文件的状态栏与"最后评审"日期。
