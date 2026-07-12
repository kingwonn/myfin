export const meta = {
  name: 'daily-scan-incremental',
  description: 'Daily incremental scan: last-48h signals on tier-1 names + system-level falsification checks',
  phases: [{ title: 'Scan' }],
}
const GROUPS = [
  { key: 'power', names: 'GE Vernova(GEV), Eaton(ETN), Constellation(CEG), Vertiv(VRT), 台达电子(2308.TW), Bloom Energy(BE)', extra: '系统级信号: 任何超大厂(MSFT/GOOG/META/AMZN)下修capex指引的报道' },
  { key: 'optics', names: 'Coherent(COHR), Lumentum(LITE), 中际旭创300308, 新易盛300502', extra: 'CPO出货新进展、InP激光器扩产公告' },
  { key: 'chips', names: 'Broadcom(AVGO), SK海力士000660.KS, 台积电(TSM), 美光(MU)', extra: 'HBM合约价新闻、CoWoS产能新闻、H100租价异动' },
  { key: 'physical', names: 'NVIDIA(NVDA机器人业务), 恒立液压601100, 柯力传感603662, 特斯拉Optimus', extra: '宇树IPO进展、人形订单公告(只认公告级)' },
  { key: 'private-macro', names: 'OpenAI, Anthropic, 软银9984.T', extra: '大额算力合同/融资公告；美股AI板块昨日异动(暴涨暴跌>5%的T1标的)' },
]
const SCHEMA = { type:'object', required:['events','red_flags'], properties:{
  events:{type:'array',items:{type:'object',required:['name','event','halflife','impact'],properties:{
    name:{type:'string'},event:{type:'string'},halflife:{enum:['day','quarter','year']},impact:{enum:['strengthen','weaken','neutral']},source:{type:'string'}}}},
  red_flags:{type:'array',items:{type:'string'}}}}
phase('Scan')
const results = await parallel(GROUPS.map(g => () =>
  agent(`日环增量扫描(今天2026-07-08)：用WebSearch检索以下标的过去48小时的关键动态——只要"产能/订单/技术路线/估值极端化(±5%以上异动)/物理证据"五类信号，忽略例行噪音。标的：${g.names}。额外检查：${g.extra}。每条事件标注半衰期(day=盘面/quarter=业绩指引/year=格局变化)与方向(强化/削弱我们的窄门判断)。无实质事件就返回空events。red_flags只放：命中系统级证伪信号(capex下修≥2家/循环融资恶化)或已验证事实被推翻的情形。中文,StructuredOutput返回。`,
    { label: `scan:${g.key}`, model: 'sonnet', schema: SCHEMA })))
return { groups: results }