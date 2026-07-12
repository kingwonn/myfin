export const meta = {
  name: 'sota-methodology-survey',
  description: 'Survey SOTA AI-driven investment research / quant methodologies and their open-source implementations',
  phases: [
    { title: 'Survey', detail: '6 parallel angles: LLM agents, factor/quant, thematic chokepoint, risk sizing, GitHub repos, practitioner frameworks' },
    { title: 'Assess', detail: 'assess integration fit for our repo-as-system design' },
  ],
}

const ANGLES = [
  { key: 'llm-agents', prompt: `调研 2024-2026 年 LLM/Agent 驱动投研的 SOTA 方法论与开源实现。必须覆盖并核实（用 WebSearch/WebFetch）：TauricResearch/TradingAgents（多agent分工:分析师/研究员/交易员/风控辩论结构）、virattt/ai-hedge-fund、microsoft/RD-Agent（自动因子/模型研发循环）、AI4Finance 的 FinGPT/FinRobot、以及其它你发现的高星或高影响项目。对每个:GitHub stars/活跃度、核心方法论一句话、可借鉴的设计、局限。返回结构化中文结果。` },
  { key: 'quant-classic', prompt: `调研经典与现代量化方法论中对"主题/产业链集中投资"最有用的部分:因子投资(动量/质量/拥挤度因子)、事件驱动(财报/订单/产能公告)、供应链图谱投资法(supply-chain mapping alpha)、以及 2024-2026 学术界关于 thematic investing / AI capex cycle 投资的研究。用 WebSearch 核实。输出:每种方法的核心逻辑、适用场景、开源工具(如 qlib/vectorbt/zipline)、对个人投资者的可行性。中文。` },
  { key: 'chokepoint', prompt: `调研"咽喉/卡位"型投资方法论的 SOTA 表述:宽护城河投资(Morningstar moat框架)、瓶颈定价权(bottleneck pricing power)、picks-and-shovels 策略在 AI 周期中的应用、供应链瓶颈轮动(如 2023 CoWoS→2024 HBM→2025 电力/光模块→? 的瓶颈迁移规律)。用 WebSearch 找 2025-2026 卖方/买方对"下一个瓶颈"的框架性讨论。输出:可操作的瓶颈识别 checklist + 轮动时钟草案。中文。` },
  { key: 'risk-sizing', prompt: `调研集中持仓下的仓位管理与风险方法论 SOTA:Kelly准则及分数Kelly实践、barbell策略(Taleb)、drawdown控制、主题投资的退出纪律(动量破位/论点证伪/估值极端)、以及 crypto/科技股高波动环境下 2024-2026 实践者总结。用 WebSearch 核实。输出:适合"高确定性×高弹性窄门组合"的仓位与风控规则草案。中文。` },
  { key: 'github-scan', prompt: `在 GitHub 上系统扫描(用 WebSearch/WebFetch 核实 star 数与活跃度)可直接为个人 AI 投研系统所用的项目,按类别:数据(OpenBB/akshare/tushare/yfinance)、回测(qlib/vectorbt/backtrader/nautilus_trader)、LLM投研agent(见其它角度但补充遗漏)、组合跟踪(ghostfolio)、财报/公告解析(edgartools等)、另类数据。每个:stars、最近提交活跃度、license、与"git仓库即系统+Claude Code运行时"架构的集成难度(低/中/高)。中文结构化输出。` },
  { key: 'practitioner', prompt: `调研知名实践者公开的系统化投研方法论(2024-2026仍活跃的):如 段永平的不为清单、Druckenmiller 的集中+择时、Gavin Baker 关于 AI capex 的框架、半导体分析师(如 SemiAnalysis Dylan Patel)的产业链跟踪方法、以及中文圈高质量的 AI 产业链投研框架。用 WebSearch 核实出处。输出:每个方法论的核心原则、与"窄门"策略的契合点、可固化进系统的纪律规则。中文。` },
]

const RESULT_SCHEMA = {
  type: 'object',
  properties: {
    findings: { type: 'array', items: { type: 'object', properties: {
      name: { type: 'string' }, core_idea: { type: 'string' },
      evidence: { type: 'string' }, integration: { type: 'string' },
      priority: { type: 'string', enum: ['high','medium','low'] },
    }, required: ['name','core_idea','integration','priority'] } },
    summary: { type: 'string' },
  },
  required: ['findings','summary'],
}

phase('Survey')
const results = await parallel(ANGLES.map(a => () =>
  agent(a.prompt + ' 最终以 StructuredOutput 返回:findings[](name/core_idea/evidence含来源链接/integration即如何为我们的系统所用/priority) 和 summary。', { label: `survey:${a.key}`, phase: 'Survey', schema: RESULT_SCHEMA })))

phase('Assess')
const merged = results.filter(Boolean)
const assessment = await agent(`背景:我们在建一个"言出法随"AI-native 投研系统(git仓库即系统,Claude Code为运行时,watchlist YAML+论点文件+技能命令),目标是在 AI 算力链与 Physical AI 链上找到"高确定性×高弹性×低拥挤度"的窄门标的。以下是 6 路方法论调研的结构化结果:\n${JSON.stringify(merged, null, 1).slice(0, 60000)}\n\n请综合成一份中文评估:1) 值得立即整合进系统的方法论要素(具体到:该改哪个文件/该加什么技能/该定什么规则);2) 值得引入的开源项目优先级排序(考虑集成难度);3) 明确不采纳的方法及理由;4) 一页纸的"我们的方法论 v1"草案(融合瓶颈轮动+护城河+论点证伪+仓位纪律)。直接返回 markdown 正文。`, { label: 'assess:integration', phase: 'Assess' })

return { angles: merged, assessment }