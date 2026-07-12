#!/usr/bin/env python3
"""R-4 拥挤度评分 v0.1 — 一票否决项的第一把刻度尺.

跑在 GitHub Actions（本仓库开发容器出口封锁行情 API，Actions runner 不受限）。
输出 data/crowding/latest.json + 按日存档，由 Action 提交回仓库；会话端只读。

v0.1 范围（诚实声明）：
- 仅美股（yfinance）；A股/H股/日股待 akshare 接入（v0.2）
- 四个价格行为信号的自身历史分位（0-100），等权合成：
    turnover  20日均美元成交额/市值 —— 交易拥挤
    vol       20日已实现波动率     —— 关注度/博弈热度
    ext200    价格相对200日均线伸展 —— 趋势拥挤
    ret60     60日涨幅            —— 动量拥挤
- 缺 MSCI 五信号法里的持仓重叠/做空比例维度（需付费数据，缺口开放）
- 分位基准=该标的自身两年历史：度量"它相对自己有多热"，跨标的比较需谨慎

阈值（docs/03-methodology 对齐）：score>=85 极端(候选池一票否决)；70-85 偏高。
"""
import datetime
import json
import pathlib
import sys

import pandas as pd
import yaml
import yfinance as yf

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
OUTDIR = ROOT / "data" / "crowding"
US_EXCH = {"NYSE", "NASDAQ"}
VETO, ELEVATED = 85, 70


def us_tickers():
    rows = []
    for f in ["compute-chain.yaml", "physical-ai.yaml"]:
        data = yaml.safe_load((ROOT / "watchlist" / f).read_text())
        for seg in data.get("segments", []):
            for c in seg.get("companies", []):
                t = str(c.get("ticker") or "")
                if ":" in t and t.split(":")[0] in US_EXCH:
                    rows.append({"symbol": t.split(":")[1], "name": c.get("name"),
                                 "tier": c.get("tier"), "chain": f.split(".")[0]})
    seen, out = set(), []
    for r in rows:
        if r["symbol"] not in seen:
            seen.add(r["symbol"]); out.append(r)
    return out


def pct_rank(series: pd.Series) -> float:
    s = series.dropna()
    if len(s) < 60:
        return float("nan")
    return float(round((s < s.iloc[-1]).mean() * 100, 1))


def score_one(sym: str):
    h = yf.Ticker(sym).history(period="2y", auto_adjust=True)
    if h is None or len(h) < 260:
        return None
    close, volu = h["Close"], h["Volume"]
    dollar20 = (close * volu).rolling(20).mean()
    try:
        mcap = yf.Ticker(sym).fast_info.get("marketCap")
    except Exception:
        mcap = None
    turnover = dollar20 / mcap if mcap else dollar20  # 无市值时退化为美元成交额分位
    vol20 = close.pct_change().rolling(20).std()
    ext200 = close / close.rolling(200).mean() - 1
    ret60 = close.pct_change(60)
    sig = {"turnover": pct_rank(turnover), "vol": pct_rank(vol20),
           "ext200": pct_rank(ext200), "ret60": pct_rank(ret60)}
    valid = [v for v in sig.values() if v == v]
    if len(valid) < 3:
        return None
    score = round(sum(valid) / len(valid), 1)
    label = "极端" if score >= VETO else "偏高" if score >= ELEVATED else "常态"
    return {"score": score, "label": label, "signals": sig,
            "mcap_used": bool(mcap), "bars": len(h)}


def main():
    today = datetime.date.today().isoformat()
    results, failed = [], []
    for r in us_tickers():
        try:
            s = score_one(r["symbol"])
        except Exception as e:
            s = None
            failed.append({"symbol": r["symbol"], "err": str(e)[:120]})
        if s:
            results.append({**r, **s})
        elif not any(f["symbol"] == r["symbol"] for f in failed):
            failed.append({"symbol": r["symbol"], "err": "insufficient history"})
    results.sort(key=lambda x: -x["score"])
    out = {"date": today, "version": "v0.1", "coverage": "US-listed only",
           "thresholds": {"veto": VETO, "elevated": ELEVATED},
           "results": results, "failed": failed,
           "note": "score = 自身2年历史分位的等权合成；>=85 候选池一票否决。"
                   "缺持仓重叠/做空比例维度（付费数据缺口）。"}
    OUTDIR.mkdir(parents=True, exist_ok=True)
    (OUTDIR / "latest.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    (OUTDIR / f"{today}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(f"scored {len(results)}, failed {len(failed)}")
    for x in results[:8]:
        print(f"  {x['score']:5.1f} {x['label']} {x['symbol']:6s} {x['name']}")
    if failed:
        print("  failed:", ", ".join(f["symbol"] for f in failed))
    return 0 if results else 1


if __name__ == "__main__":
    sys.exit(main())
