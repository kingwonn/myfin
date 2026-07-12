#!/usr/bin/env python3
"""GitHub Pages builder — 看盘台 (index) + 学习中心 (learn) + 渲染报告.

Usage: python3 site/build_pages.py   (from repo root)
Output: site/pages-dist/  → push contents to the gh-pages branch.

Deps: pyyaml, markdown. Quotes/charts use free TradingView embeds
(client-side; no keys). Everything else is baked at build time from the
repo's YAML/Markdown so the page can never disagree with the repo.
"""
import datetime
import html
import pathlib
import subprocess
import json

import markdown
import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "site" / "pages-dist"
REPO_URL = "https://github.com/kingwonn/myfin"
MAIN_BRANCH = "claude/ai-native-dev-research-2dves3"
BUILD_DATE = datetime.date.today().isoformat()

# ---------------------------------------------------------------- data

CHECKPOINTS = [
    ("2026-07-22", "GEV Q2 财报", "系统第一张前向成绩单：预注册判分卡 A/B/C/D（见 GEV 论点）"),
    ("2026-Q3", "CPO 出货裁决", "光模块窗口期是否关闭的触发器（旭创/新易盛证伪条件）"),
    ("2026-Q3", "Bloom 10-Q RPO 复核", "公司口径 backlog vs 审计口径的对账"),
    ("待定", "宇树挂牌首日", "拥挤度现场教学：首日成交结构"),
    ("2026-12", "GEV 2030 槽位售罄确认", "燃机论点久期假设的年度审计点"),
]

TV_EXCH = {"SHSE": "SSE", "SZSE": "SZSE", "NASDAQ": "NASDAQ", "NYSE": "NYSE",
           "HKEX": "HKEX", "TSE": "TSE", "KRX": "KRX"}

REPORTS = [  # (源, 输出slug, 标题, 一句话)
    ("docs/research/2026-07-11-advice-compute-chain.md", "advice-compute-chain",
     "投资建议书① AI 算力产业链", "钱押在算力的输血管上：电力与光互连的供给瓶颈"),
    ("docs/research/2026-07-11-advice-physical-ai.md", "advice-physical-ai",
     "投资建议书② Physical AI", "方向确定×时间表未证×定价极端拥挤：零仓位等发令枪"),
    ("commodities:commodities/research/2026-07-11-advice-commodities.md", "advice-commodities",
     "投资建议书③ 大宗商品线", "AI 电力化的分母钱 + 国家兜底的政策钱"),
    ("docs/research/2026-07-12-system-review.md", "system-review",
     "系统全面评审（独立代理）", "研究层真材实料；定价与拥挤度量化是真钱决策前的欠账"),
    ("docs/research/2026-07-12-p1-gev-pricing.md", "p1-gev-pricing",
     "P1 定价裁决：GEV 隐含预期反推", "好公司贵价格：市场已把久期买到 2030——估值闸门 ~$800"),
    ("theses/2026-07-07-gas-turbine-narrow-gate.md", "gev-thesis",
     "GEV 燃机论点（含 7/22 预注册判分卡）", "先写答案卡再考试——禁止事后挪门柱"),
    ("docs/research/2026-07-12-intake-03-k2ai.md", "intake-03-k2ai",
     "吸收 #03：k2ai.dev 批判性拆解", "同一张发票的两端：钱流镜头吸收为领先下车指标"),
    ("journal/beliefs.md", "beliefs", "信念条目库（17 条）", "从尸体和事故上抄来的生存法则"),
]

CSS = """
:root{--bg:#FAF9F6;--surface:#fff;--ink:#1C2128;--muted:#5F6B68;--line:#E3E1DA;
--accent:#0E7C66;--accent-soft:#E2F0EC;--warn:#B07C24;--warn-soft:#F5EDDD;
--bad:#B4433A;--bad-soft:#F6E7E5;--chip:#F0EEE8}
@media (prefers-color-scheme: dark){:root{--bg:#101418;--surface:#171C22;--ink:#E8E6E1;
--muted:#96A09D;--line:#2A313A;--accent:#3FB394;--accent-soft:#15302A;--warn:#D0A050;
--warn-soft:#32291A;--bad:#D4756C;--bad-soft:#33201E;--chip:#222831}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
font:15px/1.75 -apple-system,"PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif}
.wrap{max-width:1080px;margin:0 auto;padding:28px 20px 70px}
header.site{display:flex;flex-wrap:wrap;align-items:baseline;gap:14px;margin-bottom:6px}
header.site h1{font-family:"Noto Serif SC","Songti SC",serif;font-size:26px;margin:0}
header.site .date{color:var(--muted);font-size:13px}
nav.top{margin-left:auto;display:flex;gap:14px;font-size:14px}
a{color:var(--accent);text-decoration:none}a:hover{text-decoration:underline}
h2{font-family:"Noto Serif SC","Songti SC",serif;font-size:20px;margin:36px 0 10px;text-wrap:balance}
h3{font-size:16px;margin:22px 0 8px}
.sub{color:var(--muted);font-size:13.5px;margin:0 0 14px}
.card{background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:16px 18px;margin:12px 0}
.tablewrap{overflow-x:auto;border:1px solid var(--line);border-radius:8px;margin:12px 0;background:var(--surface)}
table{border-collapse:collapse;width:100%;font-size:13.5px}
th{font-size:12px;color:var(--muted);text-align:left;background:var(--chip);white-space:nowrap}
th,td{padding:8px 12px;border-bottom:1px solid var(--line);vertical-align:top}
tr:last-child td{border-bottom:none}
.t1,.t2,.t3{display:inline-block;font:600 11px/1 ui-monospace,Menlo,monospace;padding:3px 7px;border-radius:999px;white-space:nowrap}
.t1{background:var(--accent-soft);color:var(--accent)}
.t2{background:var(--warn-soft);color:var(--warn)}
.t3{background:var(--chip);color:var(--muted)}
.chip{display:inline-block;font:600 11.5px/1.6 ui-monospace,Menlo,monospace;padding:1px 8px;border-radius:999px;background:var(--chip)}
.chip.kill{background:var(--bad-soft);color:var(--bad)}
.chip.warn{background:var(--warn-soft);color:var(--warn)}
.chk{display:flex;gap:12px;flex-wrap:wrap}
.chk .card{flex:1 1 240px;margin:0}
.chk .d{font:700 13px ui-monospace,Menlo,monospace;color:var(--accent)}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:12px}
@media(max-width:860px){.grid2{grid-template-columns:1fr}}
.tv{background:var(--surface);border:1px solid var(--line);border-radius:10px;overflow:hidden;min-height:60px}
.md{max-width:820px}
.md table{font-size:13.5px}
.md h1{font-family:"Noto Serif SC","Songti SC",serif;font-size:24px}
.md h2{font-size:19px}.md blockquote{border-left:3px solid var(--accent);margin:12px 0;padding:4px 16px;color:var(--muted)}
.md code{background:var(--chip);padding:1px 5px;border-radius:4px;font-size:12.5px}
.md pre{background:var(--chip);padding:12px;border-radius:8px;overflow-x:auto}
footer{margin-top:50px;padding-top:14px;border-top:1px solid var(--line);color:var(--muted);font-size:12.5px;max-width:76ch}
.lessons .card p{margin:4px 0}
.note{background:var(--warn-soft);border-left:3px solid var(--warn);border-radius:0 8px 8px 0;padding:10px 16px;font-size:13.5px}
"""

SHELL = """<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title><style>{css}</style></head><body><div class="wrap">
<header class="site"><h1>{h1}</h1><span class="date">构建 {date} · 数据截至构建日</span>
<nav class="top"><a href="{home}index.html">看盘台</a><a href="{home}learn.html">学习中心</a>
<a href="{repo}" target="_blank">GitHub 仓库</a></nav></header>
{body}
<footer>言出法随 · AI-native 投研系统 ｜ 本站由 <code>site/build_pages.py</code> 从仓库数据自动生成，
行情组件来自 TradingView（免费嵌入，实时性以其为准）。个人研究笔记，不构成投资建议；
系统不执行任何真实交易。<br>关键结论均经 3 票对抗验证，票数标注见各报告原文。</footer>
</div>{scripts}</body></html>"""


def esc(s):
    return html.escape(str(s or ""))


def tv_symbol(ticker):
    if not ticker or ":" not in str(ticker):
        return None
    exch, code = str(ticker).split(":", 1)
    exch = TV_EXCH.get(exch)
    return f"{exch}:{code}" if exch else None


def load_crowding():
    f = ROOT / "data" / "crowding" / "latest.json"
    if not f.exists():
        return {}, None
    d = json.loads(f.read_text())
    return {r["symbol"]: r for r in d.get("results", [])}, d.get("date")


def load_ledger():
    f = ROOT / "data" / "ledger" / "latest.json"
    return json.loads(f.read_text()) if f.exists() else None


def load_watchlists():
    chains = []
    for f, label in [("compute-chain.yaml", "AI 算力链"), ("physical-ai.yaml", "Physical AI")]:
        data = yaml.safe_load((ROOT / "watchlist" / f).read_text())
        rows = []
        for seg in data.get("segments", []):
            for c in seg.get("companies", []):
                c["segment"] = seg.get("segment", "")
                rows.append(c)
        rows.sort(key=lambda c: (c.get("tier", 9), c.get("segment", "")))
        chains.append((label, f, rows))
    priv = yaml.safe_load((ROOT / "watchlist" / "private-chokepoints.yaml").read_text())
    return chains, priv.get("companies", [])


def watch_table(rows, crowd=None):
    crowd = crowd or {}
    tr = []
    for c in rows:
        tier = c.get("tier", "")
        sym = str(c.get("ticker") or "").split(":")[-1]
        cr = crowd.get(sym)
        if cr:
            cls = "kill" if cr["label"] == "极端" else "warn" if cr["label"] == "偏高" else ""
            crowd_cell = f"<span class='chip {cls}'>{cr['score']:.0f} {cr['label']}</span>"
        else:
            crowd_cell = "<span class='sub'>—</span>"
        tr.append(
            f"<tr><td><span class='t{tier}'>T{tier}</span></td>"
            f"<td><b>{esc(c.get('name'))}</b><br><span class='chip'>{esc(c.get('ticker', '—'))}</span></td>"
            f"<td>{esc(c.get('segment'))}</td><td>{esc(c.get('role'))}</td>"
            f"<td>{esc(c.get('moat'))}</td><td>{esc(c.get('risk'))}</td>"
            f"<td>{crowd_cell}</td>"
            f"<td>{esc(c.get('last_checked') or '未扫')}</td>"
            f"<td>{esc((c.get('notes') or '')[:160])}</td></tr>")
    head = ("<tr><th>层</th><th>标的</th><th>环节</th><th>卡位</th>"
            "<th>护城河</th><th>证伪条件</th><th>拥挤度</th><th>末检</th><th>笔记(截断)</th></tr>")
    return f"<div class='tablewrap'><table>{head}{''.join(tr)}</table></div>"


def tv_scripts(chains):
    tape, groups = [], []
    for label, _, rows in chains:
        syms = []
        for c in rows:
            s = tv_symbol(c.get("ticker"))
            if s:
                syms.append({"name": s, "displayName": str(c.get("name", ""))[:12]})
                if c.get("tier") == 1 and len(tape) < 12:
                    tape.append({"proName": s, "title": str(c.get("name", ""))[:10]})
        groups.append({"name": label, "symbols": syms[:14]})
    import json
    tape_j, groups_j = json.dumps(tape, ensure_ascii=False), json.dumps(groups, ensure_ascii=False)
    return f"""<script>
(function(){{
  var dark = matchMedia('(prefers-color-scheme: dark)').matches;
  var theme = dark ? 'dark' : 'light';
  function widget(id, src, cfg) {{
    var host = document.getElementById(id); if (!host) return;
    var s = document.createElement('script');
    s.src = 'https://s3.tradingview.com/external-embedding/' + src; s.async = true;
    s.innerHTML = JSON.stringify(cfg);
    var box = document.createElement('div');
    box.className = 'tradingview-widget-container'; box.appendChild(s); host.appendChild(box);
  }}
  widget('tv-tape','embed-widget-ticker-tape.js',{{symbols:{tape_j},showSymbolLogo:true,
    colorTheme:theme,isTransparent:true,displayMode:'adaptive',locale:'zh_CN'}});
  widget('tv-quotes','embed-widget-market-quotes.js',{{width:'100%',height:520,
    symbolsGroups:{groups_j},showSymbolLogo:true,colorTheme:theme,isTransparent:true,locale:'zh_CN'}});
  widget('tv-chart','embed-widget-advanced-chart.js',{{autosize:true,symbol:'NYSE:GEV',
    interval:'D',timezone:'Asia/Shanghai',theme:theme,style:'1',locale:'zh_CN',
    withdateranges:true,allow_symbol_change:true,support_host:'https://www.tradingview.com'}});
}})();
</script>"""


def build_index(chains, priv, crowd, crowd_date, ledger):
    chk = "".join(
        f"<div class='card'><div class='d'>{esc(d)}</div><b>{esc(t)}</b>"
        f"<p class='sub'>{esc(note)}</p></div>" for d, t, note in CHECKPOINTS)
    chain_html = ""
    for label, fname, rows in chains:
        n1 = sum(1 for c in rows if c.get("tier") == 1)
        chain_html += (f"<h2>{esc(label)} <span class='chip'>T1×{n1} / 共{len(rows)}</span></h2>"
                       f"<p class='sub'>源文件 <a href='{REPO_URL}/blob/{MAIN_BRANCH}/watchlist/{fname}' target='_blank'>watchlist/{fname}</a>"
                       f"——moat/risk 为入库必填，证伪条件命中即评审。</p>" + watch_table(rows, crowd))
    pr = "".join(
        f"<tr><td><b>{esc(c.get('name'))}</b></td><td>{esc(c.get('position'))}</td>"
        f"<td>{esc(c.get('ipo_status'))}</td><td>{esc(', '.join(map(str, c.get('indirect_exposure', []))) if isinstance(c.get('indirect_exposure'), list) else c.get('indirect_exposure'))}</td>"
        f"<td>{esc((c.get('notes') or c.get('signal_value') or '')[:180])}</td></tr>" for c in priv)
    ledger_html = ""
    if ledger:
        rows = ""
        for b in ledger.get("baskets", []):
            vs = " · ".join(f"vs {k[3:]} {v:+.2f}pp" for k, v in b.items() if k.startswith("vs_"))
            rows += (f"<div class='card'><b>{esc(b['name'])}</b> "
                     f"<span class='chip'>{b['ret']:+.2f}%</span>"
                     f"<p class='sub'>{vs} ｜ 起算 {esc(b['inception'])} ｜ "
                     f"成分: {esc(', '.join(f'{s2} {v2:+.1f}%' if v2 is not None else s2 for s2, v2 in b['detail'].items()))}</p></div>")
        pos = ledger.get("positions") or []
        ledger_html = (f"<h2>纸面账本 <span class='chip'>盯市 {esc(ledger.get('date'))}</span></h2>"
                       f"<p class='sub'>仓位数：{len(pos)}（空 = 纪律在工作：唯一候选 GEV 被定价闸门挡住）。"
                       f"观察篮子=排序判断的前向成绩单，非仓位建议；每日由 GitHub Actions 自动盯市。</p>"
                       f"<div class='chk'>{rows}</div>")
    crowd_note = (f"拥挤度评分 {esc(crowd_date)}（自身2年分位合成，≥85 一票否决/70-85 预警；美股覆盖，A股待接入）"
                  if crowd_date else "拥挤度数据待管线首跑")
    body = f"""
<div class='note'>看盘纪律：先看<b>检查点日历</b>再看价格——我们交易论点与证据，不交易情绪。任何操作前查对应论点的证伪条件。</div>
<p class='sub'>{crowd_note}</p>
<h2>检查点日历</h2><div class='chk'>{chk}</div>
{ledger_html}
<h2>行情速览</h2><p class='sub'>TradingView 免费组件（15 分钟延迟级别，够用：我们不做日内）。跑马灯=各链 T1 核心。</p>
<div class='tv' id='tv-tape'></div>
<div class='grid2' style='margin-top:12px'>
  <div class='tv' id='tv-chart' style='height:520px'></div>
  <div class='tv' id='tv-quotes'></div>
</div>
<p class='sub'>图表默认 GEV（窄门第 1 位，7/22 判分卡见<a href='reports/gev-thesis.html'>论点页</a>）；可在图内换任意标的。</p>
{chain_html}
<h2>未上市咽喉 <span class='chip'>{len(priv)} 家</span></h2>
<div class='tablewrap'><table><tr><th>公司</th><th>卡住什么</th><th>IPO 状态</th><th>间接敞口</th><th>信号/笔记(截断)</th></tr>{pr}</table></div>
"""
    return SHELL.format(title="看盘台 · 言出法随", h1="看盘台", date=BUILD_DATE,
                        home="", repo=REPO_URL, css=CSS, body=body,
                        scripts=tv_scripts(chains))


def render_md(src):
    if src.startswith("commodities:"):
        text = subprocess.run(["git", "show", src], capture_output=True, text=True,
                              cwd=ROOT).stdout
    else:
        text = (ROOT / src).read_text()
    return markdown.markdown(text, extensions=["tables", "fenced_code"])


def build_reports():
    cards = []
    (OUT / "reports").mkdir(parents=True, exist_ok=True)
    for src, slug, title, one in REPORTS:
        try:
            body = f"<div class='md'>{render_md(src)}</div>"
        except Exception as e:  # 缺文件不崩整站
            body = f"<p>渲染失败：{esc(e)}</p>"
        page = SHELL.format(title=f"{title} · 言出法随", h1=title, date=BUILD_DATE,
                            home="../", repo=REPO_URL, css=CSS, body=body, scripts="")
        (OUT / "reports" / f"{slug}.html").write_text(page)
        cards.append(f"<div class='card'><b><a href='reports/{slug}.html'>{esc(title)}</a></b>"
                     f"<p class='sub'>{esc(one)}</p></div>")
    return "".join(cards)


def build_learn(report_cards):
    edu = f"<div class='md'>{render_md('docs/edu-path.md')}</div>"
    body = f"""
<div class='note'>学习纪律：第一阶段（先学会不死）没过关之前，不碰任何真钱决策。每课都有本仓库的实证读物——不是转述别人的教科书，是我们自己验证过的数字。</div>
{edu}
<h2>核心读物（已渲染，随仓库更新重建）</h2>
<div class='lessons'>{report_cards}</div>
<h2>全部研究报告</h2>
<p class='sub'>三条分支的完整研究在 GitHub 仓库（每个关键数字带验证票数）：
<a href='{REPO_URL}/tree/{MAIN_BRANCH}/docs/research' target='_blank'>主线 docs/research</a> ·
<a href='{REPO_URL}/tree/quant/quant' target='_blank'>quant 分支</a> ·
<a href='{REPO_URL}/tree/commodities/commodities' target='_blank'>commodities 分支</a></p>
"""
    return SHELL.format(title="学习中心 · 言出法随", h1="学习中心", date=BUILD_DATE,
                        home="", repo=REPO_URL, css=CSS, body=body, scripts="")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / ".nojekyll").write_text("")
    chains, priv = load_watchlists()
    crowd, crowd_date = load_crowding()
    ledger = load_ledger()
    (OUT / "index.html").write_text(build_index(chains, priv, crowd, crowd_date, ledger))
    cards = build_reports()
    (OUT / "learn.html").write_text(build_learn(cards))
    print(f"built → {OUT}  (index, learn, {len(REPORTS)} reports)")


if __name__ == "__main__":
    main()
