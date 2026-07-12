#!/usr/bin/env python3
"""纸面账本每日盯市 — 跑在 GitHub Actions（见 portfolio/paper-ledger.yaml 规则）.

首次运行：把每个符号的最近收盘写入 data/ledger/baseline.json（此后不可变）。
每次运行：计算各篮子等权累计收益 vs 基准，写 data/ledger/latest.json 并追加 history.csv。
篮子成绩是"排序判断"的前向证据，不代表任何真实仓位。
"""
import datetime
import json
import pathlib
import sys

import yaml
import yfinance as yf

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
LEDGER = yaml.safe_load((ROOT / "portfolio" / "paper-ledger.yaml").read_text())
OUTDIR = ROOT / "data" / "ledger"
BASELINE = OUTDIR / "baseline.json"


def last_close(sym):
    h = yf.Ticker(sym).history(period="10d", auto_adjust=True)
    if h is None or h.empty:
        return None
    return float(h["Close"].iloc[-1])


def main():
    today = datetime.date.today().isoformat()
    syms = set(LEDGER.get("benchmarks", []))
    for b in LEDGER.get("baskets", []):
        syms |= set(b["symbols"])
    for p in LEDGER.get("positions", []):
        syms.add(p["symbol"])

    prices, failed = {}, []
    for s in sorted(syms):
        px = last_close(s)
        if px:
            prices[s] = round(px, 4)
        else:
            failed.append(s)

    OUTDIR.mkdir(parents=True, exist_ok=True)
    if BASELINE.exists():
        base = json.loads(BASELINE.read_text())
        # 基线不可变；新符号（新篮子）首见时补录基线
        added = {s: p for s, p in prices.items() if s not in base}
        if added:
            base.update(added)
            BASELINE.write_text(json.dumps(base, indent=1, sort_keys=True))
    else:
        base = dict(prices)
        BASELINE.write_text(json.dumps(base, indent=1, sort_keys=True))
        print(f"baseline initialized with {len(base)} symbols")

    def ret(s):
        if s not in prices or s not in base or not base[s]:
            return None
        return prices[s] / base[s] - 1.0

    bench = {b: ret(b) for b in LEDGER.get("benchmarks", [])}
    baskets_out = []
    for b in LEDGER.get("baskets", []):
        rs = [ret(s) for s in b["symbols"]]
        valid = [r for r in rs if r is not None]
        if not valid:
            continue
        br = sum(valid) / len(valid)
        row = {"id": b["id"], "name": b["name"], "inception": b["inception"],
               "ret": round(br * 100, 2),
               "detail": {s: (round(r * 100, 2) if r is not None else None)
                          for s, r in zip(b["symbols"], rs)}}
        for k, v in bench.items():
            if v is not None:
                row[f"vs_{k}"] = round((br - v) * 100, 2)
        baskets_out.append(row)

    out = {"date": today, "prices": prices, "failed": failed,
           "benchmarks": {k: (round(v * 100, 2) if v is not None else None)
                          for k, v in bench.items()},
           "baskets": baskets_out,
           "positions": LEDGER.get("positions", []),
           "note": "累计收益%自各符号基线价起算；篮子=等权观察对象，非仓位。"}
    (OUTDIR / "latest.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))

    hist = OUTDIR / "history.csv"
    if not hist.exists():
        hist.write_text("date," + ",".join(b["id"] for b in baskets_out)
                        + "," + ",".join(f"bench_{k}" for k in bench) + "\n")
    hist.open("a").write(
        today + "," + ",".join(str(b["ret"]) for b in baskets_out)
        + "," + ",".join(str(out["benchmarks"][k]) for k in bench) + "\n")

    for b in baskets_out:
        vs = " ".join(f"vs{k[3:]}:{b.get(k, '—'):+}" if isinstance(b.get(k), float)
                      else "" for k in b if k.startswith("vs_"))
        print(f"  {b['id']:22s} {b['ret']:+6.2f}% {vs}")
    if failed:
        print("  failed:", failed)
    return 0 if baskets_out else 1


if __name__ == "__main__":
    sys.exit(main())
