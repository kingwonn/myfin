# 深度研究 QS-1：量化/二级市场投研 SOTA 平台全景（开源 + 闭源）

- 日期：2026-07-15 ｜ 方法：两条 deep-research 管线（开源侧 104 代理 + 闭源侧 105 代理，模型分层：Sonnet 5 搜索/抓取，每主张 3 票对抗验证 1×Opus 4.8 + 2×Sonnet 5）+ 3 个 Sonnet 5 并行数据代理（GitHub 健康度/中国平台/全球定价）；综合 Fable 5
- 数据截止 2026-07-15。不构成投资建议。
- **验证标记约定**：〔3票〕= 通过 3 票对抗验证；〔单源〕= Sonnet 代理单源采集、未经对抗验证，引用前建议二次核实；[事实]/[推断] 按仓库纪律标注。

## 小白版重点（五句话）

1. **这是什么**：把市面上"帮人做量化投资/二级市场研究"的工具全查了一遍——免费开源的代码框架和收钱的商业平台各查一轮，共覆盖约 40 个平台/项目，关键说法经过了"三个 AI 互相挑刺"的对抗验证。
2. **最大的发现**：整个行业的重心正在从"回测引擎"（用历史数据模拟策略表现的工具）转向"AI 智能体自动做研究"——开源侧的现象级项目 TradingAgents（约 9.3 万 GitHub 星标，相当于开源圈的顶流）和商业侧估值一年翻近三倍的 Rogo（20 亿美元）、AlphaSense（75 亿美元）都是这个方向。**我们这套"言出法随"系统撞上的是行业主航道。**
3. **开源侧结论**：经典框架在分化——vn.py、NautilusTrader、freqtrade、Qlib 活得很好，而老牌的 backtrader 已停滞三年、zipline 接近停摆；选工具先看"最近一次提交是什么时候"。
4. **闭源侧结论**：机构终端（彭博等）一席一年几万美元、对个人性价比极低且网传价格数字大多不可靠（本轮验证全部否决）；真正值得个人关注的是量化云平台的免费档和众包阿尔法平台（把全球业余研究者的预测收集起来做基金——摩根大通刚给这个模式背书了 5 亿美元容量）。
5. **对我们意味着什么**：现有技术栈选型（vectorbt/OpenBB/akshare）再次被印证；backtrader 应从备选剔除；若未来开 quant 副线实验，vn.py 4.x 新增的 AI 因子模块和 FinRL-X 的"前向模拟盘验证"做法是两个新参考；所有 LLM 量化项目的业绩都是自报未审计的——**别信宣传页，信我们自己的前向验证纪律**。

---

## 一、全景分类框架

先给一张地图。市面上所有平台可以按"开源/闭源"ד在链条中的位置"分成八格：

| 层 | 开源代表 | 闭源代表 |
|----|---------|---------|
| **数据层**（拿到行情/财报/另类数据） | OpenBB、akshare、Tushare、baostock | Bloomberg、FactSet、LSEG、Wind、iFinD、Choice |
| **研究/回测层**（验证策略想法） | Qlib、vectorbt、backtesting.py、zipline-reloaded、backtrader | 聚宽、米筐、BigQuant、果仁、优矿、QuantConnect 云 |
| **执行层**（把信号变成真实订单） | vn.py、NautilusTrader、LEAN、freqtrade | QMT、PTrade、掘金、Alpaca、IBKR API |
| **AI 研究自动化层**（AI 智能体替代人做研究，2025-26 新物种） | TradingAgents 系、RD-Agent、FinRL-X、FinGPT、QRAFTI/FundaPod（学术） | AlphaSense、Hebbia、Rogo、Perplexity Finance；Bridgewater AIA、Man AlphaGPT（自用不外卖） |

**结构性判断〔3票〕[事实+推断]**：开源社区认知层面"经典引擎"与"LLM-native 投研"两条线已正式分家——经典框架归 [awesome-quant](https://github.com/wilsonfreitas/awesome-quant) 索引，LLM 智能体量化已有专门精选列表 [awesome-trading-agents](https://github.com/LLMQuant/awesome-trading-agents)（其 README 明确排除经典量化库和纯强化学习机器人）。SOTA 的重心在第四层。

---

## 二、开源侧：经典引擎分化，LLM 智能体成为新前沿

### 2.1 经典框架生死簿（健康度硬数据）

〔单源，GitHub 页面直读，查看日 2026-07-15〕，维护状态结论中 vn.py/NautilusTrader/zipline-reloaded 三项另有〔3票〕一手验证：

| 项目 | Stars | 最近提交 | 许可证 | 定位 | 状态判定 |
|------|-------|---------|--------|------|---------|
| [OpenBB](https://github.com/OpenBB-finance/OpenBB) | 70.6k | 2026-05-27 | **AGPLv3**（2025 年从 MIT 类切换） | 数据聚合平台 | 活跃，但已商业化转向（下述） |
| [freqtrade](https://github.com/freqtrade/freqtrade) | 52.3k | 2026-07-14 | GPL-3.0 | 加密货币交易机器人 | 非常活跃（月度发版） |
| [Qlib](https://github.com/microsoft/qlib)（微软） | 46.3k | 2026-04-22 | MIT | AI 量化研究平台 | 活跃 |
| [vn.py](https://github.com/vnpy/vnpy) | 43.0k | 2026-05-17 | MIT | 国内量化全栈框架 | 活跃〔3票，GitHub API 核验〕 |
| [NautilusTrader](https://github.com/nautechsystems/nautilus_trader) | ~24.7k* | 2026-06-29 | LGPL-3.0 | Rust 内核高性能交易系统 | 非常活跃（双周发版）〔3票〕 |
| [backtrader](https://github.com/mementum/backtrader) | 22.5k | **2023-04-19** | GPL-3.0 | 经典回测框架 | **停滞三年，事实弃维护**（二次核实确认） |
| [akshare](https://github.com/akfamily/akshare) | 21.3k | 2026-05-27 | MIT | A股全品类数据接口 | 活跃 |
| [LEAN](https://github.com/QuantConnect/Lean)（QuantConnect） | 20.5k | 2026-07-14 | Apache-2.0 | 事件驱动算法交易平台 | 非常活跃（当日多次提交） |
| [backtesting.py](https://github.com/kernc/backtesting.py) | 8.7k | 2025-12-20 | AGPL-3.0 | 轻量回测入门 | 慢速但在维护 |
| [vectorbt](https://github.com/polakowo/vectorbt) | 8.3k | 2026-07-14 | Apache-2.0 + Commons Clause | 向量化高速回测 | 活跃（v1.1.0，2026-07-05） |
| [zipline-reloaded](https://github.com/stefan-jansen/zipline-reloaded) | 1.8k | 2025-11-13（仅依赖升级） | Apache-2.0 | 原 Quantopian 引擎续命版 | **趋停滞**〔3票：一年无新版，2026 零功能提交〕 |

\* NautilusTrader 精确 star 数在对抗验证中未通过（1-2），24.7k 为单源页面读数，量级可信、精确值存疑。

**三个要点：**

1. **backtrader 已死，别再进新人推荐名单**〔单源，双重核实〕[事实]：master 分支最后一次真实代码提交是 2023-04-19，此后无 release 无提交。它仍有 22.5k stars 和大量中文教程，这正是坑——星标是历史荣誉，不是健康证明。zipline-reloaded 是半个同类案例〔3票〕：v3.1.1（2025-07）后一年无新版，作者 Stefan Jansen 基本只为配合自己的教科书做依赖维护。**"awesome 列表在列 ≠ 项目健康"是本轮验证出的通用教训。**
2. **OpenBB 变身了**〔单源，官方博客佐证〕[事实]：2025 年许可证从 MIT 类改为 AGPL（传染性开源协议——基于它构建对外服务需开源自己的代码），定位从"开源彭博终端"转为"面向分析师/量化/AI agent 的开放数据平台"，赚钱靠闭源的 OpenBB Workspace 企业版（[许可变更公告](https://openbb.co/blog/license-change-openbb-platform-goes-agpl/)）。对我们这种内部自用场景 AGPL 无实际影响，但需知道它不再是"纯公益"项目。
3. **vn.py 正在从执行框架长出研究能力**〔3票，GitHub API + 代码目录实证〕[事实]：4.0 起新增 `vnpy.alpha` 多因子机器学习模块——内置 LightGBM/Lasso/MLP 模型和源自微软 Qlib 的 Alpha158 特征集（158 个经典量价因子的标准实现），v4.4.0（2026-05-14）加了 QuestDB 时序数据库支持。注意：网传"集成 CTP/易盛/XTP 等 30+ 券商网关"的具体清单在验证中被 0-3 否决，接口数量待官方文档核实。

### 2.2 LLM 智能体量化：2025-2026 最热的新物种

**术语解释**：LLM 多智能体（multi-agent）= 让多个大语言模型分别扮演分析师、研究员、风控、基金经理等角色，像一家微型投研机构一样协作产出决策。

**格局〔3票+单源交叉〕**：

- **TradingAgents（TauricResearch）是事实上的基础架构** [事实]：约 93k stars（验证者 2026-07-15 一手核对 GitHub 为 93,084；不同时点快照 84k-93k，系星标持续暴涨），2026-04-30 曾登 GitHub Trending 第一〔单源〕。架构是"多头分析师 vs 空头分析师辩论 + Research Manager 仲裁"。已衍生出 90+ 仓库的生态：**TradingAgents-CN（约 30.2k stars，中文增强版，覆盖 A/港/美股）**、TradingAgents-AShare（2026-03 创建）、TradingAgents-astock 等——**A股的 LLM 投研适配目前主要由中文衍生生态承担**〔3票中 2-1 通过，GitHub 数据一手确认〕。
- **微软 RD-Agent（13.9k stars）+ Qlib 是"自动化因子工厂"路线** [事实]：R&D-Agent-Quant（CMU + 微软亚洲研究院，NeurIPS 2025）做"数据中心的因子与模型联合优化"〔3票〕；Qlib 本体覆盖 alpha 挖掘→风险建模→组合优化→订单执行全链条（订单执行含强化学习版 TWAP 等，为真实代码模块非宣传）〔3票〕。这条线是本仓库 02-tech-stack 已收录的"言出法随官方先例"，本轮确认其前沿仍在推进（FT-Agent 被 ICML 2026 接收〔单源〕）。
- **FinRL-X（AI4Finance/FinRL-Trading 仓库）是"AI 原生全栈"路线**〔3票，论文+仓库互证〕[事实]：FinRL 官方演进后继（原 FinRL 转定位教育/研究），核心设计"权重中心接口"——所有策略（规则型/强化学习型/LLM 情绪型）统一输出目标持仓权重，保证回测与实盘语义一致。**自报业绩必须打引号**〔2-1〕：2025-10~2026-03 Alpaca 模拟盘 +19.76%（Sharpe 1.96）vs 同期 SPY -3%，是自报、模拟盘、六个月窗口、无第三方审计，且其单组件变体回撤达 -21.46%——结果对组件拼装高度敏感 [事实+推断]。
- **学术圈三个月冒出一批新框架**〔各 3票/2-1〕[事实]：QuantAgent（自称首个"高频"多智能体框架，但实验只是 1 小时/4 小时 K 线，"高频"有营销水分）、QRAFTI（用 MCP——让 AI 直接调用数据和工具的标准协议——做因子研究自动化，能复现 Fama-French 价值因子）、FundaPod（机构基本面投研智能体，**刻意让各智能体隔离推理、互不可见，分歧交人类裁决**——与 TradingAgents 的辩论式收敛形成两种设计哲学）。

**防污染声明** [事实]：上述所有 LLM 量化项目的业绩数字均为作者自报，多数论文未完成同行评审；部分实验让模型回看历史行情打分——存在 LLM 预训练记忆污染（模型"背过"历史行情，回测成绩天然虚高）。这正是我们 CLAUDE.md 前向验证纪律禁止的做法，本轮外部证据再次印证该纪律的必要性。

---

## 三、闭源/商业侧：终端贵而不透明，AI-native 在爆发

### 3.1 机构终端：本轮最重要的结论是"网传数字不可靠"

**对抗验证结果** [事实]：所有关于 Bloomberg/FactSet/LSEG/Capital IQ 的席位定价、用户数、公司覆盖数对比主张**全部未通过验证**（多为 0-3 票否决）——wallstreetprep 等流传甚广的比较页数字（"彭博 32.5 万用户 vs LSEG 19 万"、"CapIQ 覆盖 5200 万家公司"等）经不起推敲。**本报告对终端定价只给量级不给精确数**：

| 终端 | 定价量级〔单源，第三方比价站，官方均不公开挂牌价〕 | 2025-26 AI 动态（官方来源） |
|------|------|------|
| Bloomberg Terminal | ~$3 万+/席/年量级 | BloombergGPT（50.6B 参数）已内嵌终端工作流，2023 后无重大公开更新；BQuant Desktop/Enterprise 提供 Python 量化环境 |
| FactSet | ~$1-5 万/席/年量级（模块化） | [Intelligent Platform 战略](https://investor.factset.com/news-releases/news-release-details/factset-unveils-intelligent-platform-initiative-supercharge)（2024-11 官宣）、Mercury 对话引擎、Pitch Creator（2025-01）；2026-06 与 Google Cloud 共建 AI agent〔单源〕 |
| LSEG Workspace | ~$1.2-3 万/席/年量级 | [微软合作深化](https://news.microsoft.com/source/2025/10/12/lseg-and-microsoft-transform-access-to-ai-ready-financial-data-in-customer-workflows/)（2025-10，MCP 服务器接入 Copilot）；[OpenAI 合作](https://www.lseg.com/en/media-centre/press-releases/2025/lseg-announces-new-collaboration-with-openai)（ChatGPT 经 MCP 接入 LSEG 数据，2025-12） |
| 万得 Wind | 历史口径 ~4 万元/终端/年，区间 2-5 万元〔单源，2023-09 报道，2026 价未核实〕 | 机构市占率口径 90%+；2024-01 宕机 8 小时信任危机；2024-09 对部分客户增购降价报道 |
| 同花顺 iFinD | ~1.4 万元/年〔单源〕 | 问财 HithinkGPT：首家网信办备案金融对话大模型，2025 上线深度思考模式 |
| 东方财富 Choice | ~5,800 元/年（团购可至 ~3,160）〔单源〕 | 主打个人/中小机构性价比 |

**判断 [推断]**：机构终端对个人投资者性价比极低，其真实价值在机构工作流绑定（合规、协作、IB 聊天网络效应）。个人可用"开源数据栈 + 单点付费数据"以两个数量级更低的成本覆盖 80% 需求——这正是我们已走的路线。值得注意的战略信号是：**三大终端都在把数据通过 MCP 开放给 LLM**（LSEG×OpenAI/微软最激进），"终端垄断数据入口"的商业模式正在被 AI 入口松动。

### 3.2 量化云平台：中国存活名单 + 一个死亡案例

**中国平台现状**〔聚宽运营状态为 3票验证，其余为单源采集〕：

| 平台 | 状态（2026-07） | 关键事实 |
|------|------|---------|
| 聚宽 JoinQuant | **正常运营**〔3票，中基协公示佐证〕 | 回测免费；2025-01 会员涨价（VIP 年费 999 元）；**2026-08-01 起仅限中国大陆 IP 访问**〔单源，官网公告〕；私募主体聚宽投资（[中基协 P1066435](https://gs.amac.org.cn/amac-infodisc/res/pof/manager/1705160857106326.html)）2025 年仍列百亿量化榜单；注意"一创聚宽"实盘通道 2023 年底已关停（网传"聚宽停用"实为此事）；"AUM 回升至近 200 亿"被 0-3 否决，不采信 |
| 米筐 RiceQuant | 运营中〔单源〕 | rqalpha 开源框架未归档、2026-07 仍有 release 活动；产品线 RQData/RQAlpha-Plus/RQFactor/RQOptimizer；现行价格未能核实 |
| BigQuant | 运营中〔单源〕 | AI 因子挖掘定位（自然语言→因子）；标准版 129 元/月；2026 推 "Cowork" 智能体平台，宣称 AI 生成 90-100% 策略代码（营销口径） |
| 果仁网 | 运营中〔单源〕 | 非编程向导式；FAQ 更新至 2026-03 |
| 优矿 Uqer | 收缩〔单源，需二次核实〕 | **实盘对接 2024-12-29 已终止**，只剩研究/回测 |
| Quantopian（美，案例） | **已死**〔单源，Bloomberg/维基佐证〕 | 2017 停实盘→2019 停模拟→2020-10 关闭，运营 9 年；全球最大众包量化社区说没就没 |

**QuantConnect（LEAN 的云端商业版）**：免费档提供全资产无限回测但不可实盘〔单源，官方文档〕；付费档具体价格在对抗验证中被否决（$10/月、$60/月两说均未通过），引用需查官网现价；Alpha Streams 众包策略市场 v1.0 已终止、v2.0 重构中〔单源，官方论坛〕。

**中国监管背景**〔单源，官方文件锚定〕[事实]：证监会《程序化交易管理规定（试行）》2024-10-08 施行，三大交易所实施细则 **2025-07-07 正式实施**——程序化交易全面报备制（须经券商报备申报速率、单日笔数、软件信息），高频认定线为单账户每秒 300 笔申报/撤单或全日 2 万笔。实际执行中触发监管指标的主要是量化私募和券商自营；**低频个人投资者基本不受影响**，也未发现新规导致研究/回测类平台关停的案例。行业整体从"速度竞争"转向"深度竞争"（中低频化）——这对我们"统计规律 + 机械执行"的低频副线定位反而是顺风 [推断]。

### 3.3 众包阿尔法：拿到机构背书的另类模式

**术语解释**：众包阿尔法 = 平台把策略研发外包给全球业余/自由研究者，收集他们的预测信号聚合成基金策略，研究者按贡献分成——相当于"策略界的滴滴"。

- **Numerai**〔3票〕[事实]：全球数万匿名数据科学家用平台加密货币 NMR 质押自己的预测（预测好拿奖励、差则质押被销毁），平台每周聚合数千模型为"元模型"驱动市场中性对冲基金（2019-09 启动）。**2025-08 摩根大通资管承诺最高 $5 亿容量**（[Numerai 官方博客](https://blog.numer.ai/jpmorgan-secures-500m-capacity/) + Bloomberg 2025-08-26 交叉），将 AUM 从约 $4.5 亿推向近 $10 亿——众包量化迄今最重的机构背书。2025-11 完成 $30M C 轮（估值 $5 亿）〔单源〕。注意波动不小：2023 年约 -19%、2024 年约 +25%（后者未经验证）。正在改造系统支持 AI agent 直接提交预测〔单源〕。
- **WorldQuant BRAIN**〔3票，单一官方来源〕[事实]：面向全球开放的因子（alpha）研发平台，10,000 积分 + Gold 等级后"可能获邀"成为研究顾问（非保证）；覆盖含中国大陆在内 17 个地区；2026 国际量化锦标赛进行中。网传薪酬分档（Grandmaster $8,000+/季度等）被验证否决（1-2），不可采信。

### 3.4 AI-native 投研：闭源侧增长最快的赛道

**本轮验证最扎实的一组事实（全部官方新闻稿锚定）：**

| 公司 | 事件 | 验证 |
|------|------|------|
| **AlphaSense** | 2026-06-03 融资 $350M，估值 **$7.5B**（2024-06 为 $4B，接近翻倍）；**ARR 突破 $600M**（2025-10 为 $500M）；企业客户 7,000+；同步发布常驻型 AI 代理 **SuperAnalyst**（自主多步研究+自动约访专家） | 〔3票×多组，[官方新闻稿](https://www.alpha-sense.com/press/alphasense-raises-350m-at-7-5b-valuation-and-surpasses-600m-in-annual-recurring-revenue/) + 8 家独立渠道〕 |
| **Rogo**（投行 AI 分析师） | 2026-04-29 D 轮 $160M，Kleiner Perkins 领投，估值 **$2B**——距 C 轮（$750M 估值）仅三个月；自报 250+ 机构 35,000+ 用户（Moelis、野村、Lazard 等为真实客户）；新品 Felix 自主执行"筛选交易→生成材料→买方外联→尽调"全流程 | 〔3票，[官方](https://rogo.ai/news/series-d)〕客户数为自报〔2-1〕 |
| **Hebbia** | 估值 $700M（2024-07 B 轮，a16z）；产品 Matrix 表格式全文档多步推理；**2025-26 无新融资公开信息**——热度被 Rogo/AlphaSense 反超 [推断] | 〔单源〕 |
| **Perplexity Finance** | 2025-26 连发组合跟踪/财报中心/自然语言选股器；"Computer for Professional Finance"覆盖 10 领域 35 工作流；数据方含 FactSet/S&P/LSEG | 〔单源，官方博客〕 |

**买方自研 AI（不卖给你，但指明方向）**〔单源，官方+主流媒体〕[事实]：

- **Bridgewater AIA Labs**：目标"全 AI 投资者"，旗下基金首个完整运营年（2025）录得约 +11.9%，保留人工监督。
- **Man Group AlphaGPT**：模拟人类量化研究员全流程（挖数据→生成信号→写代码→回测），**已产出数十个获批实盘的信号**（Bloomberg 2025-07-10）；同时与 Anthropic 合作用 Claude Code 提效，文本分析耗时降 80%。
- **Lumenai Innovation Fund**：号称首只全 agentic AI 架构机构对冲基金，2026 年中启动。
- **Robinhood Agentic Trading**（2026-05-27 上线）：AI 代客交易，资金隔离在专门账户。

**判断 [推断]**：AI-native 投研是 2025-2026 融资市场里金融科技最热的细分。共同模式 = "专有数据/文档库 + agent 工作流 + 嵌入机构现有流程"。买方巨头（Bridgewater/Man）的自研进展说明"AI 智能体产出实盘信号"已过概念验证期——但所有公开业绩仍是单年/自报口径，样本远不足以证明持续性。

---

## 四、对本系统的可借鉴点（quant 副线视角）

1. **技术栈选型全部再确认，一处修订** [事实+推断]：vectorbt（回测首选）2026-07 仍高频更新，选型成立；akshare/OpenBB 数据层成立（注意 OpenBB 的 AGPL 对内部使用无碍）；**backtrader 应从 02-tech-stack 的一切备选名单中剔除**（停滞三年）；backtesting.py 保留为入门备选（仍在维护）。
2. **新候选进观察清单**：**vnpy.alpha**（vn.py 4.x 的 ML 因子模块，自带 Qlib Alpha158 因子集）——若 quant 副线做 A 股因子实验，它提供"因子研究+数据管理+执行接口"一体的国产方案，比单独拼 Qlib 更轻；**FinRL-X 的权重中心接口**设计（策略统一输出目标权重，回测/实盘同语义）值得在我们未来的回测脚本中借鉴为约定。
3. **方向验证**：本仓库"AI 运行时 + 自然语言驱动投研"的架构正是行业主航道——微软 RD-Agent、QRAFTI、FundaPod、AlphaSense SuperAnalyst 都在做同构的事。其中 **FundaPod 的"独立性保持"设计（智能体隔离推理防信息级联）与我们 deep-research 管线的独立验证票机制同构**，属于外部印证。
4. **前向验证纪律获双重外部印证**：(a) 开源管线明确指出 LLM 回看历史行情存在预训练记忆污染；(b) FinRL-X 采用的正是"模拟盘前向跟踪"验证法。我们 CLAUDE.md 的禁令（禁止回看式验证）继续作为硬约束。
5. **平台风险课**：Quantopian 关闭（9 年积累归零）、优矿实盘终止、一创聚宽关停、聚宽 2026-08 起封境外 IP——**凡把研究资产沉淀在别人平台上的，都承担平台关停/收缩风险**。我们"本地仓库 + 开源工具栈"的架构对此免疫，此原则不动摇。
6. **若未来开实盘实验（需用户明确点头）**：国内合规通道事实上收敛于券商系 QMT/PTrade（须券商开户开通，门槛传闻已降至 10 万但导流文数字存疑，以券商官方为准〔单源〕）；美股模拟盘 Alpaca 免费。程序化交易新规对低频个人几乎无影响，合规成本低 [事实]。
7. **不建议做的**：现阶段不投入 WorldQuant BRAIN/Numerai 众包平台（时间成本高、与主线论点研究争夺注意力，且薪酬数字被验证否决）；不采纳任何 LLM 量化框架的自报业绩作为开仓依据。

---

## 五、数据可信度总声明

- **高置信〔3票对抗验证 + 官方一手来源〕**：AlphaSense/Rogo 融资与估值、Numerai 模式与 JPM 容量、聚宽运营状态、vn.py/NautilusTrader/zipline-reloaded 维护状态、FinRL-X/QRAFTI/FundaPod 论文内容、生态分家判断。
- **中置信〔单源但来源较硬（官方页面/GitHub 直读）〕**：各项目 stars/commit 数据、中国平台运营细节、监管时间线（官方文件锚定）。
- **低置信（引用前必须二次核实）**：一切终端精确定价、QMT/PTrade 开通门槛、QuantConnect 付费价格、Wind/iFinD 2026 现价。
- **被对抗验证否决、禁止引用的数字**（防污染清单）：彭博 32.5 万用户；CapIQ 5200 万公司覆盖；终端逐家定价对比表；QuantConnect $10/$60 月费；聚宽 AUM 近 200 亿；Numerai 13F 434 持仓/$694M；AlphaSense 73% 增速及 90% S&P100 渗透+$18K 席位价打包说法；Rogo 27× ARR 增速；WorldQuant 顾问薪酬分档；vnpy 30+ 网关清单；NautilusTrader 24.7k 精确星数。
- **覆盖缺口（未覆盖 ≠ 无事发生）**：Bloomberg/FactSet/LSEG AI 功能的实际用户反馈；米筐/BigQuant 的对抗验证级确认（仅单源）；Qlib/RD-Agent 本体 2026 活跃度的 3 票级验证（仅单源 GitHub 读数）。

## 六、运行备注

- 成本：两条管线合计 209 代理 / 761 万 tokens / 各约 75 分钟（并行），另 3 个 Sonnet 数据代理约 19 万 tokens。模型分层纪律（Fable 只做规划与综合）全程执行。
- 两轮各有一个 Opus 验证子代理被安全系统标记（访问本环境的代理状态端点/本地配置）。背景：本环境遇 403 时的官方排障步骤即为查询该端点，且两轮均出现大量 403（arxiv、官网反爬），疑似照文档排障被误报（与 R2a 运行备注先例一致）。受影响的两条主张：一条已被 0-3 否决未入结论（Numerai 13F）；另一条（QRAFTI）即使完全弃用被标记代理的那一票，仍有 2×Sonnet 独立干净票支持，且为低风险描述性主张。均已记录，结论可信度不受影响。
- 后续建议：(a) 把 backtrader 剔除动作落到 02-tech-stack.md（本次未改，等用户点头）；(b) 终端真实定价若确有需要，用 Burton-Taylor 行业报告/上市公司财报重查；(c) TradingAgents-CN 的 A 股适配深度（数据源/券商通道/合规边界）值得单独一轮小调查再决定是否借鉴其提示词。
