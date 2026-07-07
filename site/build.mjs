// myfin 可视化站点构建脚本
// 读取 watchlist/*.yaml + docs/**/*.md + theses/*.md，产出 dist/ 静态站点。
// 用法: cd site && npm install && npm run build
import { readFileSync, writeFileSync, mkdirSync, readdirSync, existsSync, cpSync } from 'node:fs';
import { join, basename } from 'node:path';
import YAML from 'yaml';
import { marked } from 'marked';

const ROOT = join(import.meta.dirname, '..');
const DIST = join(import.meta.dirname, 'dist');
mkdirSync(join(DIST, 'r'), { recursive: true });

// ---------- 数据装载 ----------
const loadYaml = (p) => YAML.parse(readFileSync(join(ROOT, p), 'utf8'));
const compute = loadYaml('watchlist/compute-chain.yaml');
const physical = loadYaml('watchlist/physical-ai.yaml');
const privates = loadYaml('watchlist/private-chokepoints.yaml');

const chains = [
  { id: 'compute', label: 'AI 算力链', segments: compute.segments ?? [] },
  { id: 'physical', label: 'Physical AI', segments: physical.segments ?? [] },
];

// 上市公司拍平
const listed = [];
for (const chain of chains)
  for (const seg of chain.segments)
    for (const c of seg.companies ?? [])
      listed.push({ ...c, chain: chain.id, chainLabel: chain.label, segment: seg.segment });

// 研究报告与文档页
const mdPages = [];
const addMd = (dir, kind) => {
  const abs = join(ROOT, dir);
  if (!existsSync(abs)) return;
  for (const f of readdirSync(abs).filter((f) => f.endsWith('.md') && f !== 'TEMPLATE.md').sort().reverse()) {
    const raw = readFileSync(join(abs, f), 'utf8');
    const title = (raw.match(/^#\s+(.+)$/m)?.[1] ?? f).replace(/^\d+\s*·\s*/, '');
    mdPages.push({ kind, slug: `${kind}-${basename(f, '.md')}`, title, raw });
  }
};
addMd('docs/research', 'research');
addMd('docs', 'doc');
addMd('theses', 'thesis');

// ---------- 主题（dataviz 参考调色板） ----------
const CSS = `
:root{--surface:#fcfcfb;--plane:#f9f9f7;--ink:#0b0b0b;--ink2:#52514e;--muted:#898781;
--grid:#e1e0d9;--border:rgba(11,11,11,.10);--s1:#2a78d6;--s2:#1baf7a;--s3:#eda100;
--good:#0ca30c;--warn:#fab219;--crit:#d03b3b;--chip:#f0efec}
:root[data-theme=dark],:root.dark{--surface:#1a1a19;--plane:#0d0d0d;--ink:#fff;--ink2:#c3c2b7;
--grid:#2c2c2a;--border:rgba(255,255,255,.10);--s1:#3987e5;--s2:#199e70;--s3:#c98500;--chip:#383835}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--surface:#1a1a19;--plane:#0d0d0d;
--ink:#fff;--ink2:#c3c2b7;--grid:#2c2c2a;--border:rgba(255,255,255,.10);--s1:#3987e5;--s2:#199e70;--s3:#c98500;--chip:#383835}}
*{box-sizing:border-box;margin:0}
body{background:var(--plane);color:var(--ink);font:15px/1.65 system-ui,-apple-system,"Segoe UI",sans-serif;padding-bottom:64px}
a{color:var(--s1);text-decoration:none}a:hover{text-decoration:underline}
.wrap{max-width:1080px;margin:0 auto;padding:0 20px}
header.top{padding:28px 0 10px}
h1{font-size:22px;letter-spacing:.3px}
.sub{color:var(--ink2);font-size:13px;margin-top:4px}
nav.tabs{display:flex;gap:6px;margin:18px 0 14px;flex-wrap:wrap}
nav.tabs button,nav.tabs a{border:1px solid var(--border);background:var(--surface);color:var(--ink2);
padding:6px 14px;border-radius:20px;font-size:13px;cursor:pointer}
nav.tabs .on{color:var(--ink);border-color:var(--ink2);font-weight:600}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin:6px 0 20px}
.tile{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:14px 16px}
.tile .v{font-size:26px;font-weight:700}
.tile .k{font-size:12px;color:var(--ink2);margin-top:2px}
.filters{display:flex;gap:8px;flex-wrap:wrap;margin:0 0 14px;align-items:center}
.filters select,.filters input{background:var(--surface);color:var(--ink);border:1px solid var(--border);
border-radius:8px;padding:6px 10px;font-size:13px}
.filters input{flex:1;min-width:160px}
.seg{margin:22px 0 10px;font-size:13px;color:var(--muted);text-transform:none;letter-spacing:.4px;
border-bottom:1px solid var(--grid);padding-bottom:6px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:10px}
.card{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:14px 16px;cursor:pointer}
.card:hover{border-color:var(--ink2)}
.card .hd{display:flex;justify-content:space-between;gap:8px;align-items:baseline}
.card .nm{font-weight:650;font-size:14.5px}
.card .tk{font-size:12px;color:var(--muted);font-variant-numeric:tabular-nums}
.card .role{color:var(--ink2);font-size:13px;margin-top:6px}
.badges{display:flex;gap:6px;margin-top:8px;flex-wrap:wrap}
.b{font-size:11px;padding:2px 8px;border-radius:10px;background:var(--chip);color:var(--ink2)}
.b.t1{color:var(--good);font-weight:700}
.b.t3{color:var(--muted)}
.detail{display:none;margin-top:10px;border-top:1px dashed var(--grid);padding-top:10px;font-size:13px}
.card.open .detail{display:block}
.detail dt{color:var(--muted);font-size:11px;margin-top:6px}
.detail dd{margin:1px 0 0}
.mdbody{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:28px 32px;margin-top:14px;overflow-x:auto}
.mdbody h1{font-size:20px;margin:0 0 12px}.mdbody h2{font-size:17px;margin:22px 0 8px}
.mdbody h3{font-size:15px;margin:16px 0 6px}.mdbody p{margin:8px 0}.mdbody li{margin:3px 0 3px 0}
.mdbody ul,.mdbody ol{padding-left:22px}
.mdbody table{border-collapse:collapse;font-size:13px;margin:10px 0;min-width:50%}
.mdbody th,.mdbody td{border:1px solid var(--grid);padding:6px 10px;text-align:left}
.mdbody code{background:var(--chip);padding:1px 5px;border-radius:4px;font-size:12.5px}
.mdbody pre{background:var(--chip);padding:12px;border-radius:8px;overflow-x:auto}
.mdbody pre code{background:none;padding:0}
.mdbody blockquote{border-left:3px solid var(--grid);padding-left:12px;color:var(--ink2)}
.list a.row{display:flex;justify-content:space-between;background:var(--surface);border:1px solid var(--border);
border-radius:10px;padding:12px 16px;margin-bottom:8px;color:var(--ink)}
.list a.row:hover{border-color:var(--ink2);text-decoration:none}
.list .kind{color:var(--muted);font-size:12px}
.foot{margin-top:40px;color:var(--muted);font-size:12px}
.empty{color:var(--muted);padding:30px 0;text-align:center}
`;

const esc = (s) => String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
const page = (title, body, root = '') => `<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex"><title>${esc(title)}</title><style>${CSS}</style></head><body>
<div class="wrap"><header class="top"><h1>言出法随 · myfin</h1>
<div class="sub">AI 算力链 × Physical AI 投研系统 — 个人研究笔记，不构成投资建议</div></header>${body}
<div class="foot">生成于 ${new Date().toISOString().slice(0, 10)} · 数据源:仓库 watchlist/docs/theses · <a href="${root}index.html">总览</a></div>
</div></body></html>`;

// ---------- 首页 ----------
const t1 = listed.filter((c) => c.tier === 1).length;
const segsN = chains.reduce((n, ch) => n + ch.segments.length, 0);
const researchN = mdPages.filter((p) => p.kind === 'research').length;
const thesisN = mdPages.filter((p) => p.kind === 'thesis').length;

const tierBadge = (t) => `<span class="b t${t}">${t === 1 ? '★ 核心' : t === 2 ? '◐ 观察' : '○ 背景'}</span>`;

const cardHtml = (c) => `<div class="card" data-chain="${c.chain}" data-tier="${c.tier}" data-market="${esc(c.market)}"
 data-q="${esc((c.name + ' ' + (c.ticker ?? '') + ' ' + c.segment).toLowerCase())}" onclick="this.classList.toggle('open')">
<div class="hd"><span class="nm">${esc(c.name)}</span><span class="tk">${esc(c.ticker ?? '')}</span></div>
<div class="role">${esc(c.role)}</div>
<div class="badges">${tierBadge(c.tier)}<span class="b">${esc(c.market)}</span><span class="b">${esc(c.chainLabel)}</span></div>
<dl class="detail"><dt>护城河</dt><dd>${esc(c.moat)}</dd><dt>证伪条件 / 风险</dt><dd>${esc(c.risk)}</dd>
${c.notes ? `<dt>备注</dt><dd>${esc(c.notes)}</dd>` : ''}</dl></div>`;

let listedHtml = '';
for (const chain of chains)
  for (const seg of chain.segments) {
    const cards = (seg.companies ?? []).map((c) => cardHtml({ ...c, chain: chain.id, chainLabel: chain.label, segment: seg.segment })).join('');
    listedHtml += `<div class="segblock" data-chain="${chain.id}"><div class="seg">${esc(chain.label)} ｜ ${esc(seg.segment)}</div><div class="grid">${cards}</div></div>`;
  }

const privHtml = (privates.companies ?? []).map((c) => `<div class="card" data-chain="private" data-tier="${c.tier}"
 data-market="PRIVATE" data-q="${esc(c.name.toLowerCase())}" onclick="this.classList.toggle('open')">
<div class="hd"><span class="nm">${esc(c.name)}</span><span class="tk">未上市</span></div>
<div class="role">${esc(c.position)}</div>
<div class="badges">${tierBadge(c.tier)}<span class="b">IPO: ${esc(String(c.ipo_status).slice(0, 24))}${String(c.ipo_status).length > 24 ? '…' : ''}</span></div>
<dl class="detail"><dt>IPO 状态</dt><dd>${esc(c.ipo_status)}</dd>
<dt>间接敞口</dt><dd>${esc(Array.isArray(c.indirect_exposure) ? c.indirect_exposure.join('；') : c.indirect_exposure)}</dd>
<dt>信号价值</dt><dd>${esc(c.signal_value)}</dd></dl></div>`).join('');

const reportsHtml = mdPages.length
  ? `<div class="list">${mdPages.map((p) => `<a class="row" href="r/${p.slug}.html"><span>${esc(p.title)}</span>
<span class="kind">${p.kind === 'research' ? '深度研究' : p.kind === 'thesis' ? '论点' : '文档'}</span></a>`).join('')}</div>`
  : '<div class="empty">暂无报告</div>';

const indexBody = `
<div class="tiles">
<div class="tile"><div class="v">${t1}</div><div class="k">核心跟踪标的 (Tier 1)</div></div>
<div class="tile"><div class="v">${listed.length}</div><div class="k">上市公司总数</div></div>
<div class="tile"><div class="v">${(privates.companies ?? []).length}</div><div class="k">未上市咽喉公司</div></div>
<div class="tile"><div class="v">${segsN}</div><div class="k">产业链环节</div></div>
<div class="tile"><div class="v">${researchN} / ${thesisN}</div><div class="k">研究报告 / 论点</div></div>
</div>
<nav class="tabs">
<button class="on" data-f="all">全部</button>
<button data-f="compute">AI 算力链</button>
<button data-f="physical">Physical AI</button>
<button data-f="private">未上市咽喉</button>
<a href="#reports">报告与论点 ↓</a>
</nav>
<div class="filters">
<select id="tier"><option value="">全部层级</option><option value="1">★ 核心</option><option value="2">◐ 观察</option><option value="3">○ 背景</option></select>
<input id="q" placeholder="搜索名称 / 代码 / 环节…">
</div>
<div id="cards">${listedHtml}
<div class="segblock" data-chain="private"><div class="seg">未上市 ｜ 咽喉卡位公司（跟踪其技术路线与 IPO 进展）</div><div class="grid">${privHtml}</div></div>
</div>
<h2 id="reports" style="font-size:17px;margin:34px 0 10px">报告与论点</h2>
${reportsHtml}
<script>
const tabs=[...document.querySelectorAll('nav.tabs button')];
let chain='all';
const apply=()=>{const t=document.getElementById('tier').value,q=document.getElementById('q').value.toLowerCase().trim();
document.querySelectorAll('#cards .card').forEach(c=>{
const ok=(chain==='all'||c.dataset.chain===chain)&&(!t||c.dataset.tier===t)&&(!q||c.dataset.q.includes(q));
c.style.display=ok?'':'none'});
document.querySelectorAll('.segblock').forEach(b=>{
b.style.display=[...b.querySelectorAll('.card')].some(c=>c.style.display!=='none')?'':'none'})};
tabs.forEach(b=>b.onclick=()=>{tabs.forEach(x=>x.classList.remove('on'));b.classList.add('on');chain=b.dataset.f;apply()});
document.getElementById('tier').onchange=apply;document.getElementById('q').oninput=apply;
</script>`;

writeFileSync(join(DIST, 'index.html'), page('言出法随 · myfin 投研总览', indexBody));

// ---------- Markdown 子页 ----------
for (const p of mdPages)
  writeFileSync(join(DIST, 'r', `${p.slug}.html`), page(p.title, `<nav class="tabs"><a href="../index.html">← 返回总览</a></nav><article class="mdbody">${marked.parse(p.raw)}</article>`, '../'));

// ---------- 单文件版（Artifact/离线预览：报告内联为可展开块） ----------
const inlineReports = mdPages.length
  ? mdPages.map((p) => `<details style="margin-bottom:8px"><summary style="cursor:pointer;padding:12px 16px;background:var(--surface);border:1px solid var(--border);border-radius:10px">${esc(p.title)} <span class="kind" style="color:var(--muted);font-size:12px">（${p.kind === 'research' ? '深度研究' : p.kind === 'thesis' ? '论点' : '文档'}）</span></summary><article class="mdbody">${marked.parse(p.raw)}</article></details>`).join('')
  : '<div class="empty">暂无报告</div>';
const singleBody = indexBody.replace(reportsHtml, inlineReports);
writeFileSync(join(DIST, 'single.html'), page('言出法随 · myfin 投研总览', singleBody));

console.log(`built: ${listed.length} listed + ${(privates.companies ?? []).length} private, ${mdPages.length} md pages -> dist/ (+single.html)`);
