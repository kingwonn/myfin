# -*- coding: utf-8 -*-
"""
test_reward_invariants.py — 交易奖励函数不变量测试（规格派生）

声明：本套件从 reward-function.md v1.0 + event-risk-layer.md v1.0 派生，
撰写者未阅读实现代码（尤其未读 reward_function.py）。
测试描述"设计说应该怎样"，不描述"代码现在怎样"。

运行方式：与 reward_function.py 同目录执行
    python test_reward_invariants.py
依赖：numpy（不用 pytest）。全部随机化使用固定种子，可复现。失败时退出码非 0。

规格模糊之处的判定（撰写时的裁量）：
 J1 parts 存"原始分量"（契约给定 r_vol = weights_new·asset_forward_scores），
    配权 w_r/w_d/w_c 只作用于 total。因此 λ 单次计费用 total 差分验证，
    不依赖 parts['event'] 的存储口径（乘 λ 前还是乘 λ 后均可通过）。
 J2 w=None 的默认配权未给数值：假定 w_r、w_d、w_c > 0
    （"满仓 vs 空仓显著分化"阈值取 0.05，隐含 w_r >= 0.05/CLIP ≈ 0.017）。
 J3 换手率口径（sum|Δw| 还是 sum|Δw|/2）未定：换手差值按两种口径各算一个
    候选期望值，total 之差命中其一即可。
 J4 事件超帽罚分口径 = over/cap（接口契约给定，"按超出比例罚分"）。
 J5 成本"冲击项"随 trade_value 呈 √ 次线性（契约明示），
    即冲击项 ∝ sqrt(x/V)，不是 Almgren 总冲击成本的 x^1.5。
 J6 回撤口径（当前回撤 vs 历史最大回撤）有歧义：所有测试权益曲线一律以
    谷底收尾，两种口径数值一致，测试对口径不敏感。
 J7 "零交易零成本"：固定费只对实际发生的交易收取，trade_value=0 时成本为 0。
 J8 "分档跳升"幅度未量化：判据取"跨阶梯增量 > 2×相邻同宽平滑增量"
    （光滑凸函数的相邻增量比约 1.06，>2 只能来自跳升）。
 J9 turnover <= TURNOVER_CAP 时罚分为 0（"换手率超帽→罚分"的反面推定）。
 J10 近零波动/极端输入不得产生 NaN/Inf（由"各分量有界 clip 防单项刷分"推定）。
"""

import sys
import traceback

import numpy as np

try:
    import reward_function as rf
except Exception:
    print("[FATAL] 无法 import reward_function（需与实现同目录运行）：")
    traceback.print_exc()
    sys.exit(2)

# ---------------------------------------------------------------- 框架

_RESULTS = []


def check(name, cond, detail=""):
    ok = bool(cond)
    _RESULTS.append((name, ok))
    line = ("[PASS] " if ok else "[FAIL] ") + name
    if not ok and detail:
        line += "\n        <- " + str(detail)
    print(line)
    return ok


def section(title):
    print("\n== " + title + " ==")


def run(fn):
    try:
        fn()
    except Exception:
        check(fn.__name__ + ": 执行过程无未捕获异常", False,
              traceback.format_exc(limit=6))


def fpart(res, key):
    return float(res.parts[key])


# ---------------------------------------------------------------- 工具

def geom_path(rng, T, mu, sigma, n=None):
    """几何随机游走价格路径，起点 100。n=None 给一维 (T,)。"""
    shape = (T,) if n is None else (T, n)
    lr = mu + sigma * rng.standard_normal(shape)
    lp = np.cumsum(lr, axis=0)
    lp = lp - lp[0]
    return 100.0 * np.exp(lp)


def eq_for_dd(dd, peak=1.25, n_up=12, n_dn=14):
    """先涨到 peak 再单调跌到 peak*(1-dd)，以谷底收尾（见 J6）。
    peak=1.25 与 (1-dd) 取二进制可精确表示的值时，回撤计算无浮点越界风险。"""
    up = np.linspace(1.0, peak, n_up)
    dn = np.linspace(peak, peak * (1.0 - dd), n_dn)
    return np.concatenate([up, dn[1:]])


def scores_of(prices, t):
    return np.ravel(np.asarray(rf.asset_forward_scores(prices, t), dtype=float))


EQ_FLAT = np.linspace(1.0, 1.02, 30)   # 无回撤权益曲线（单调不降，dd=0）
SIG0, ADV0 = 0.02, 1.0e6               # 无关紧要处的缺省市场参数


# ---------------------------------------------------------------- 0. 契约常量

def inv0_constants():
    check("常量: HORIZONS == (3,7,15)", tuple(rf.HORIZONS) == (3, 7, 15))
    check("常量: HORIZON_WEIGHTS == (0.3,0.5,0.2) 且和为 1",
          np.allclose(rf.HORIZON_WEIGHTS, (0.3, 0.5, 0.2))
          and abs(float(np.sum(rf.HORIZON_WEIGHTS)) - 1.0) < 1e-12)
    check("常量: VOL_WINDOW == 20", rf.VOL_WINDOW == 20)
    check("常量: ASYMMETRY == 1.5", float(rf.ASYMMETRY) == 1.5)
    check("常量: COMPONENT_CLIP == 3.0", float(rf.COMPONENT_CLIP) == 3.0)
    check("常量: DD_LADDER == (0.10,0.15,0.20)",
          np.allclose(rf.DD_LADDER, (0.10, 0.15, 0.20)))
    check("常量: DD_TERMINAL_PENALTY == -10.0",
          float(rf.DD_TERMINAL_PENALTY) == -10.0)
    check("常量: EVENT_EXPOSURE_CAP == {N:1.0,E:0.75,S:0.50}",
          rf.EVENT_EXPOSURE_CAP == {"NEUTRAL": 1.0, "ELEVATED": 0.75, "SHOCK": 0.50})
    check("常量: EVENT_LAMBDA == {N:0.0,E:1.0,S:2.0}",
          rf.EVENT_LAMBDA == {"NEUTRAL": 0.0, "ELEVATED": 1.0, "SHOCK": 2.0})
    check("常量: HARD_RULE_PENALTY == -5.0", float(rf.HARD_RULE_PENALTY) == -5.0)
    check("常量: TURNOVER_CAP == 0.20", float(rf.TURNOVER_CAP) == 0.20)


# ---------------------------------------------------------------- 1. 单纯形投影

def inv1_simplex():
    """规格：动作空间物理排除杠杆与做空（GIFT 式多头单纯形+现金）。
    任意提案投影后必须 w>=0 且 sum(w)<=1。"""
    rng = np.random.default_rng(101)
    cases = []
    for i in range(100):
        n = int(rng.integers(1, 9))
        kind = i % 5
        if kind == 0:
            raw = rng.normal(0.0, 5.0, n)                 # 正负混合
        elif kind == 1:
            raw = -np.abs(rng.normal(1.0, 3.0, n))        # 全负（做空提案）
        elif kind == 2:
            raw = np.abs(rng.normal(2.0, 3.0, n)) + 0.5   # 全正超1（杠杆提案）
        elif kind == 3:
            raw = rng.normal(0.0, 1.0, n) * 1e6           # 极端量级
        else:
            raw = np.zeros(n)                             # 全零
        cases.append(raw)

    viol = []
    for i, raw in enumerate(cases):
        w = np.asarray(rf.project_to_simplex_with_cash(np.asarray(raw, dtype=float)))
        if w.shape != np.asarray(raw).shape:
            viol.append("case %d: 形状改变 %s -> %s" % (i, np.asarray(raw).shape, w.shape))
            continue
        if not np.all(np.isfinite(w)):
            viol.append("case %d: 非有限值" % i)
        if float(np.min(w)) < -1e-10:
            viol.append("case %d: 存在负权重 min=%.3e（做空可表达=违规）" % (i, float(np.min(w))))
        if float(np.sum(w)) > 1.0 + 1e-9:
            viol.append("case %d: sum=%.12f > 1（杠杆可表达=违规）" % (i, float(np.sum(w))))
    check("单纯形: 100 组随机提案（含全负/超1/极端/全零）投影后 w>=0 且 sum<=1",
          not viol, "; ".join(viol[:5]))


# ---------------------------------------------------------------- 2. 持仓耦合

def inv2_position_coupling():
    """规格核心：赚钱加分按组合实际敞口计——r_vol = weights_new·scores，
    现金贡献 0。满仓与空仓的 total 必须显著分化，且随敞口单调。"""
    rng = np.random.default_rng(102)
    t = 30
    prices_up = geom_path(rng, 60, +0.02, 0.004, n=2)   # 确定性强上涨
    prices_dn = geom_path(rng, 60, -0.02, 0.004, n=2)   # 确定性强下跌
    base = np.array([0.5, 0.5])
    ladder = [0.0, 0.25, 0.5, 0.75, 1.0]

    s_up = scores_of(prices_up, t)
    s_dn = scores_of(prices_dn, t)
    check("持仓耦合: 上涨路径各资产前向分数 > 0", bool(np.all(s_up > 0)),
          "scores=%s" % s_up)
    check("持仓耦合: 下跌路径各资产前向分数 < 0", bool(np.all(s_dn < 0)),
          "scores=%s" % s_dn)

    def ladder_run(prices):
        totals, rvols = [], []
        for a in ladder:
            w = a * base
            res = rf.step_reward(prices, t, EQ_FLAT, w, w, "NEUTRAL", SIG0, ADV0)
            totals.append(float(res.total))
            rvols.append(fpart(res, "r_vol"))
        return np.array(totals), np.array(rvols)

    tot_up, rv_up = ladder_run(prices_up)
    tot_dn, rv_dn = ladder_run(prices_dn)

    check("持仓耦合: 空仓时 r_vol 分量恒为 0（上涨/下跌路径均然）",
          abs(rv_up[0]) < 1e-12 and abs(rv_dn[0]) < 1e-12,
          "rv_up[0]=%.3e rv_dn[0]=%.3e" % (rv_up[0], rv_dn[0]))
    check("持仓耦合: 上涨路径 r_vol 随敞口严格单调增",
          bool(np.all(np.diff(rv_up) > 1e-9)), "rv_up=%s" % rv_up)
    check("持仓耦合: 上涨路径 total 随敞口严格单调增（假定 w_r>0, J2）",
          bool(np.all(np.diff(tot_up) > 1e-9)), "tot_up=%s" % tot_up)
    check("持仓耦合: 下跌路径 r_vol 随敞口严格单调减",
          bool(np.all(np.diff(rv_dn) < -1e-9)), "rv_dn=%s" % rv_dn)
    check("持仓耦合: 上涨路径 满仓 total - 空仓 total > 0.05（显著分化）",
          tot_up[-1] - tot_up[0] > 0.05,
          "diff=%.6f" % (tot_up[-1] - tot_up[0]))
    check("持仓耦合: 下跌路径 满仓 total - 空仓 total < -0.05（显著分化）",
          tot_dn[-1] - tot_dn[0] < -0.05,
          "diff=%.6f" % (tot_dn[-1] - tot_dn[0]))

    # 契约公式：parts['r_vol'] == weights_new · asset_forward_scores（随机权重抽查）
    viol = []
    for i in range(5):
        w = np.asarray(rf.project_to_simplex_with_cash(rng.normal(0.0, 1.0, 2)))
        res = rf.step_reward(prices_up, t, EQ_FLAT, w, w, "NEUTRAL", SIG0, ADV0)
        expect = float(np.dot(w, s_up))
        got = fpart(res, "r_vol")
        if abs(got - expect) > 1e-6 * max(1.0, abs(expect)):
            viol.append("case %d: got=%.9f expect=%.9f w=%s" % (i, got, expect, w))
    check("持仓耦合: parts['r_vol'] == weights_new·asset_forward_scores（5 组随机权重）",
          not viol, "; ".join(viol))


# ---------------------------------------------------------------- 3. λ 单次计费

def inv3_lambda_single_billing():
    """规格：λ_event(N=0/E=1/S=2) 只在 step_reward 汇总时乘一次；
    event_penalty 返回的是未乘 λ 的超帽比例罚分 over/cap（J1/J4）。
    验证法：prev==new（无交易、无 gross 增加），三个状态下 total 之差只来自
    λ·event，两个不同 gross × 两个不同 λ 交叉验证不存在双重相乘。"""
    rng = np.random.default_rng(103)
    t = 30
    prices = geom_path(rng, 60, 0.005, 0.01, n=3)

    # 权重和取二进制精确值，避免 gross 浮点边界误触"加仓"硬罚
    for wv, gross in [
        (np.array([0.5, 0.25, 0.125]), 0.875),
        (np.array([0.5, 0.25, 0.25]), 1.0),
    ]:
        totals = {}
        for st in ("NEUTRAL", "ELEVATED", "SHOCK"):
            res = rf.step_reward(prices, t, EQ_FLAT, wv, wv, st, SIG0, ADV0)
            check("λ 单次: gross=%.3f %s 态 prev==new 时 hard==0" % (gross, st),
                  abs(fpart(res, "hard")) < 1e-12,
                  "hard=%r" % res.parts["hard"])
            totals[st] = float(res.total)

        pen_s = (gross - 0.50) / 0.50           # J4: over/cap，均 < CLIP
        pen_e = max(gross - 0.75, 0.0) / 0.75
        d_s = totals["NEUTRAL"] - totals["SHOCK"]
        d_e = totals["NEUTRAL"] - totals["ELEVATED"]
        check("λ 单次: gross=%.3f SHOCK 对 total 的事件贡献 ≈ 2.0×(over/0.5)=%.4f" % (gross, 2.0 * pen_s),
              abs(d_s - 2.0 * pen_s) < 1e-6, "diff=%.9f expect=%.9f" % (d_s, 2.0 * pen_s))
        check("λ 单次: gross=%.3f ELEVATED 对 total 的事件贡献 ≈ 1.0×(over/0.75)=%.4f" % (gross, 1.0 * pen_e),
              abs(d_e - 1.0 * pen_e) < 1e-6, "diff=%.9f expect=%.9f" % (d_e, 1.0 * pen_e))

        # event_penalty 返回值必须是未乘 λ 的原始罚分
        raw_s, hard_s = rf.event_penalty("SHOCK", gross, gross)
        raw_e, hard_e = rf.event_penalty("ELEVATED", gross, gross)
        check("λ 单次: gross=%.3f event_penalty('SHOCK') 原始罚分 == over/cap（未乘 λ）" % gross,
              abs(float(raw_s) - pen_s) < 1e-9 and abs(float(hard_s)) < 1e-12,
              "raw=%.9f expect=%.9f（若 ≈2×expect 则 λ 被提前乘入=双重计费）" % (float(raw_s), pen_s))
        check("λ 单次: gross=%.3f event_penalty('ELEVATED') 原始罚分 == over/cap（未乘 λ）" % gross,
              abs(float(raw_e) - pen_e) < 1e-9 and abs(float(hard_e)) < 1e-12,
              "raw=%.9f expect=%.9f" % (float(raw_e), pen_e))
        # 交叉闭环：total 差分 == λ × event_penalty 返回值（各恰好一次）
        check("λ 单次: gross=%.3f total 差分 == EVENT_LAMBDA × event_penalty 原始值（无双重相乘）" % gross,
              abs(d_s - rf.EVENT_LAMBDA["SHOCK"] * float(raw_s)) < 1e-6
              and abs(d_e - rf.EVENT_LAMBDA["ELEVATED"] * float(raw_e)) < 1e-6,
              "d_s=%.9f λs*raw=%.9f; d_e=%.9f λe*raw=%.9f"
              % (d_s, 2.0 * float(raw_s), d_e, 1.0 * float(raw_e)))


# ---------------------------------------------------------------- 4. 非对称映射

def inv4_asymmetry():
    """规格：f(r_vol) 负端更陡，系数 ASYMMETRY=1.5。
    用镜像小幅路径（对数收益 ±ε·k，历史段完全相同故滚动波动率相同）验证：
    |score(负)| ≈ ASYMMETRY × |score(正)|。先断言两侧都远离 ±CLIP。"""
    rng = np.random.default_rng(104)
    t = 25
    clip = float(rf.COMPONENT_CLIP)
    pre_viol, ratio_viol = [], []
    n_cases = 0
    for rep in range(5):
        hist_lr = 0.01 * rng.standard_normal(t)      # 共享历史（决定滚动波动率）
        lp_hist = np.concatenate([[0.0], np.cumsum(hist_lr)])
        for eps in (0.0005, 0.001):
            n_cases += 1
            k = np.arange(1, 16)                     # 未来 15 期，覆盖 3/7/15 周期
            p_up = 100.0 * np.exp(np.concatenate([lp_hist, lp_hist[-1] + eps * k]))
            p_dn = 100.0 * np.exp(np.concatenate([lp_hist, lp_hist[-1] - eps * k]))
            su = float(scores_of(p_up, t)[0])
            sd = float(scores_of(p_dn, t)[0])
            tag = "rep=%d eps=%g" % (rep, eps)
            # 前置：两侧都不在 clip 上，且量级足以测比值
            if not (0.02 < su < 0.9 * clip and -0.9 * clip < sd < -0.02):
                pre_viol.append("%s: su=%.4f sd=%.4f 触界或量级过小" % (tag, su, sd))
                continue
            ratio = abs(sd) / abs(su)
            if abs(ratio - float(rf.ASYMMETRY)) > 0.12:
                ratio_viol.append("%s: ratio=%.4f (期望≈1.5)" % (tag, ratio))
    check("非对称: %d 组镜像小幅路径两侧分数均远离 ±CLIP（前置条件）" % n_cases,
          not pre_viol, "; ".join(pre_viol[:4]))
    check("非对称: |负向分数| ≈ ASYMMETRY×|正向分数|（容差 ±0.12）",
          not ratio_viol, "; ".join(ratio_viol[:4]))


# ---------------------------------------------------------------- 5. 回撤阶梯

def inv5_drawdown_ladder():
    """规格：g(DD) 凸增；触 0.10/0.15 分档跳升；dd>=0.20 回合终止，
    total = DD_TERMINAL_PENALTY。曲线一律以谷底收尾（J6）。"""
    def g_of(dd):
        g, term = rf.drawdown_penalty(eq_for_dd(dd))
        return float(g), bool(term)

    g_flat, term_flat = rf.drawdown_penalty(np.linspace(1.0, 1.3, 25))
    check("回撤: 单调上行曲线 g==0 且非 terminal",
          float(g_flat) <= 1e-9 and not bool(term_flat),
          "g=%r term=%r" % (g_flat, term_flat))

    # 凸性：阶梯下方等距三点二阶差分 > 0
    g02, _ = g_of(0.02)
    g05, _ = g_of(0.05)
    g08, _ = g_of(0.08)
    d1, d2 = g05 - g02, g08 - g05
    check("回撤: g>=0 且随 dd 递增（0.02/0.05/0.08）",
          g02 >= 0 and g05 >= g02 - 1e-12 and g08 >= g05 - 1e-12,
          "g=%.6f/%.6f/%.6f" % (g02, g05, g08))
    check("回撤: 凸性——等距三点二阶差分 > 0（0.02/0.05/0.08）",
          d2 > d1 + 1e-12, "d1=%.9f d2=%.9f" % (d1, d2))

    # 阶梯跳升（J8：跨阶增量 > 2×相邻同宽平滑增量）
    for rung in (0.10, 0.15):
        a, b, c = rung - 0.009, rung - 0.003, rung + 0.003
        ga, _ = g_of(a)
        gb, _ = g_of(b)
        gc, _ = g_of(c)
        smooth, cross = gb - ga, gc - gb
        check("回撤: 跨 %.2f 阶梯有跳升（跨阶增量 %.6f > 2×平滑增量 %.6f）"
              % (rung, cross, smooth),
              cross > 2.0 * smooth + 1e-9 and cross > 1e-9,
              "smooth=%.9f cross=%.9f" % (smooth, cross))

    # terminal 分界（dd 值取二进制精确数，避免浮点边界误判）
    for dd, expect_term in [(0.05, False), (0.19, False),
                            (0.203125, True), (0.25, True), (0.35, True)]:
        _, term = g_of(dd)
        check("回撤: dd=%.6f -> terminal == %s" % (dd, expect_term),
              term == expect_term)

    # terminal 时 step_reward.total == DD_TERMINAL_PENALTY
    rng = np.random.default_rng(105)
    prices = geom_path(rng, 60, 0.0, 0.01, n=2)
    w = np.array([0.25, 0.25])
    res = rf.step_reward(prices, 30, eq_for_dd(0.25), w, w, "NEUTRAL", SIG0, ADV0)
    check("回撤: dd=0.25 时 step_reward.terminal==True 且 total==DD_TERMINAL_PENALTY",
          bool(res.terminal) and abs(float(res.total) - float(rf.DD_TERMINAL_PENALTY)) < 1e-9,
          "terminal=%r total=%r" % (res.terminal, res.total))


# ---------------------------------------------------------------- 6. 交易成本

def inv6_transaction_cost():
    """规格：固定费 + 点差下限 + 平方根冲击 σ·√(x/V)；非负、随规模单调、
    次线性（J5）；零交易零成本（J7）。冲击项用 σ 差分隔离（冲击 ∝ σ）。"""
    book = 1.0e6
    check("成本: 零交易零成本 transaction_cost(0,...) == 0",
          abs(float(rf.transaction_cost(0.0, book, 0.3, 1.0e5))) <= 1e-12)

    rng = np.random.default_rng(106)
    viol = []
    for i in range(50):
        x = 10.0 ** rng.uniform(0, 6)
        sig = 10.0 ** rng.uniform(-4, 0.3)
        adv = 10.0 ** rng.uniform(2, 9)
        c = float(rf.transaction_cost(x, book, sig, adv))
        if not np.isfinite(c) or c < -1e-12:
            viol.append("case %d: cost=%r (x=%.3g sig=%.3g adv=%.3g)" % (i, c, x, sig, adv))
    check("成本: 50 组随机参数成本非负且有限", not viol, "; ".join(viol[:4]))

    xs = [1e2, 1e3, 1e4, 1e5, 1e6]
    cs = [float(rf.transaction_cost(x, book, 0.2, 1.0e5)) for x in xs]
    check("成本: 随 trade_value 单调不减",
          all(cs[i + 1] >= cs[i] - 1e-12 for i in range(len(cs) - 1)),
          "costs=%s" % cs)

    # 冲击项 √ 次线性：trade_value ×4 -> 冲击项 ≈ ×2（容差放宽 [1.4, 2.9]）
    for x, adv, sig in [(1.0e4, 1.0e5, 0.30), (5.0e3, 2.0e5, 0.50)]:
        imp1 = (float(rf.transaction_cost(x, book, sig, adv))
                - float(rf.transaction_cost(x, book, 1e-12, adv)))
        imp4 = (float(rf.transaction_cost(4 * x, book, sig, adv))
                - float(rf.transaction_cost(4 * x, book, 1e-12, adv)))
        ok_pos = imp1 > 1e-12
        ratio = imp4 / imp1 if ok_pos else float("nan")
        check("成本: 冲击项(σ差分隔离) x=%.0f ×4 后比值 %.3f ∈ [1.4, 2.9]（√ 次线性）"
              % (x, ratio),
              ok_pos and 1.4 <= ratio <= 2.9,
              "imp1=%.6g imp4=%.6g ratio=%r（若≈8 则实现为 x^1.5 总冲击，违反契约次线性）"
              % (imp1, imp4, ratio))
        c1 = float(rf.transaction_cost(x, book, sig, adv))
        c4 = float(rf.transaction_cost(4 * x, book, sig, adv))
        check("成本: 总成本次线性 cost(4x) < 4×cost(x)（x=%.0f）" % x,
              c4 < 4.0 * c1 - 1e-12, "c1=%.6g c4=%.6g" % (c1, c4))


# ---------------------------------------------------------------- 7. 硬罚

def inv7_hard_rule():
    """规格：ELEVATED/SHOCK 中 gross 增加 -> HARD_RULE_PENALTY=-5；
    减仓与持平不罚；NEUTRAL 加仓不罚。"""
    hp = float(rf.HARD_RULE_PENALTY)

    # 随机化直测 event_penalty 的硬罚端
    rng = np.random.default_rng(107)
    viol = []
    for i in range(30):
        st = ("NEUTRAL", "ELEVATED", "SHOCK")[int(rng.integers(0, 3))]
        gp = float(rng.uniform(0.10, 0.90))
        move = i % 3            # 0=加仓 1=减仓 2=持平
        if move == 0:
            g = gp + float(rng.uniform(0.02, 0.30))
        elif move == 1:
            g = max(gp - float(rng.uniform(0.02, 0.30)), 0.0)
        else:
            g = gp
        expect = hp if (st in ("ELEVATED", "SHOCK") and g > gp) else 0.0
        _, hard = rf.event_penalty(st, g, gp)
        if abs(float(hard) - expect) > 1e-9:
            viol.append("case %d: st=%s gp=%.3f g=%.3f hard=%r expect=%r"
                        % (i, st, gp, g, hard, expect))
    check("硬罚: 30 组随机 (状态×加/减/平) event_penalty 硬罚端符合规则",
          not viol, "; ".join(viol[:4]))

    # step_reward 端到端（权重和取二进制精确值，杜绝浮点边界误触）
    rng2 = np.random.default_rng(1071)
    prices = geom_path(rng2, 60, 0.0, 0.01, n=2)
    lo = np.array([0.125, 0.125])       # gross 0.25
    hi = np.array([0.25, 0.25])         # gross 0.50
    reb = np.array([0.375, 0.125])      # gross 0.50，仅调结构
    cases = [
        ("ELEVATED 加仓", lo, hi, "ELEVATED", hp),
        ("SHOCK 加仓", lo, hi, "SHOCK", hp),
        ("ELEVATED 减仓", hi, lo, "ELEVATED", 0.0),
        ("SHOCK 减仓", hi, lo, "SHOCK", 0.0),
        ("SHOCK 持平(等 gross 调仓)", hi, reb, "SHOCK", 0.0),
        ("NEUTRAL 加仓", lo, hi, "NEUTRAL", 0.0),
    ]
    for name, wp, wn, st, expect in cases:
        res = rf.step_reward(prices, 30, EQ_FLAT, wp, wn, st, SIG0, ADV0)
        check("硬罚: %s -> parts['hard'] == %s" % (name, expect),
              abs(fpart(res, "hard") - expect) < 1e-9,
              "hard=%r" % res.parts["hard"])


# ---------------------------------------------------------------- 8. 分量有界

def inv8_boundedness():
    """规格：各分量有界（clip），防单项刷分。随机 200 组输入（含极端值），
    非 terminal 时 parts 中除 hard 外每分量 |x| <= COMPONENT_CLIP；
    terminal 情形豁免分量断言，单独断言 total == DD_TERMINAL_PENALTY。
    任何 NaN/Inf 均违规（J10）。"""
    rng = np.random.default_rng(108)
    clip = float(rf.COMPONENT_CLIP)
    keys = ("r_vol", "g_dd", "cost", "event", "turnover")
    viol_bound, viol_term = [], []
    n_term = 0
    for i in range(200):
        mu = float(rng.uniform(-0.03, 0.03))
        if i % 11 == 0:
            sig = 1e-8                       # 近零波动（"躲低波刷分"路径）
        elif i % 7 == 0:
            sig = 0.3                        # 极端高波动
        else:
            sig = float(rng.uniform(0.002, 0.05))
        prices = geom_path(rng, 60, mu, sig, n=3)
        t = int(rng.integers(22, 44))
        dd = float(rng.uniform(0.0, 0.18)) if i < 140 else float(rng.uniform(0.22, 0.35))
        wp = np.asarray(rf.project_to_simplex_with_cash(rng.normal(0.0, 2.0, 3)))
        wn = np.asarray(rf.project_to_simplex_with_cash(rng.normal(0.0, 2.0, 3)))
        st = ("NEUTRAL", "ELEVATED", "SHOCK")[int(rng.integers(0, 3))]
        sd = 10.0 ** float(rng.uniform(-6, 0.7))     # 至 ~5.0
        adv = 10.0 ** float(rng.uniform(-6, 9))      # 含极小 ADV -> 冲击爆表须被 clip
        res = rf.step_reward(prices, t, eq_for_dd(dd), wp, wn, st, sd, adv)
        if bool(res.terminal):
            n_term += 1
            if abs(float(res.total) - float(rf.DD_TERMINAL_PENALTY)) > 1e-9:
                viol_term.append("case %d: terminal 但 total=%r" % (i, res.total))
            continue
        if not np.isfinite(float(res.total)):
            viol_bound.append("case %d: total 非有限 %r" % (i, res.total))
        for k in keys:
            v = fpart(res, k)
            if not np.isfinite(v) or abs(v) > clip + 1e-6:
                viol_bound.append("case %d: parts['%s']=%r 超出 ±%.1f (st=%s sd=%.3g adv=%.3g)"
                                  % (i, k, v, clip, st, sd, adv))
        if not np.isfinite(fpart(res, "hard")):
            viol_bound.append("case %d: parts['hard'] 非有限" % i)
    check("有界: 200 组随机/极端输入，非 terminal 分量(除 hard)均 |x| <= COMPONENT_CLIP 且有限",
          not viol_bound, "; ".join(viol_bound[:5]))
    check("有界: terminal 情形(%d 例) total == DD_TERMINAL_PENALTY" % n_term,
          n_term >= 30 and not viol_term,
          "n_term=%d; %s" % (n_term, "; ".join(viol_term[:5])))


# ---------------------------------------------------------------- 9. 换手率

def inv9_turnover():
    """规格：换手率超帽 -> 罚分（帽 TURNOVER_CAP=0.20，帽内不罚 J9）。
    断言 total 之差：两个场景 weights_new 相同（r_vol/g_dd/event/hard 全同）、
    仅 weights_prev 不同（帽内 vs 超帽），把 σ、冲击压到可忽略后，
    total 差 ≈ turnover_penalty 之差（换手口径双候选，J3）。"""
    tp = lambda x: float(rf.turnover_penalty(float(x)))

    check("换手: turnover_penalty(0) == 0", abs(tp(0.0)) <= 1e-12)
    check("换手: 帽内不罚 tp(0.10)==0 且 tp(0.19)==0（J9）",
          abs(tp(0.10)) <= 1e-12 and abs(tp(0.19)) <= 1e-12,
          "tp(0.10)=%r tp(0.19)=%r" % (tp(0.10), tp(0.19)))
    check("换手: 超帽有罚 tp(0.25) > 0", tp(0.25) > 1e-9, "tp(0.25)=%r" % tp(0.25))
    seq = [tp(x) for x in (0.25, 0.4, 0.8, 1.5)]
    check("换手: 罚分随换手单调不减", all(seq[i + 1] >= seq[i] - 1e-12 for i in range(3)),
          "seq=%s" % seq)

    rng = np.random.default_rng(109)
    prices = geom_path(rng, 60, 0.005, 0.01, n=3)
    new = np.array([0.3, 0.3, 0.2])
    prev_a = np.array([0.35, 0.25, 0.2])    # sum|Δ| = 0.10（帽内，两种口径均帽内）
    prev_b = np.array([0.7, 0.1, 0.0])      # sum|Δ| = 0.80（超帽，两种口径均超帽）
    to_a = float(np.abs(new - prev_a).sum())
    to_b = float(np.abs(new - prev_b).sum())
    # σ 极小 + ADV 极大 -> 冲击≈0；固定费两场景同额；点差差额受 0.02 容差覆盖
    res_a = rf.step_reward(prices, 30, EQ_FLAT, prev_a, new, "NEUTRAL", 1e-9, 1e12)
    res_b = rf.step_reward(prices, 30, EQ_FLAT, prev_b, new, "NEUTRAL", 1e-9, 1e12)

    check("换手: 帽内场景 parts['turnover'] == 0",
          abs(fpart(res_a, "turnover")) <= 1e-9, "got=%r" % res_a.parts["turnover"])
    check("换手: 超帽场景 parts['turnover'] > 0",
          fpart(res_b, "turnover") > 1e-9, "got=%r" % res_b.parts["turnover"])

    diff = float(res_a.total) - float(res_b.total)
    cand_full = tp(to_b) - tp(to_a)              # 口径 sum|Δw|
    cand_half = tp(to_b / 2) - tp(to_a / 2)      # 口径 sum|Δw|/2
    matched = min(abs(diff - cand_full), abs(diff - cand_half))
    check("换手: 超帽 total 差 = 可计算的 turnover_penalty 差（双口径候选之一，容差 0.02）",
          diff > 1e-6 and matched <= 0.02,
          "diff=%.6f cand_full=%.6f cand_half=%.6f" % (diff, cand_full, cand_half))


# ---------------------------------------------------------------- 10. NEUTRAL 事件分量恒 0

def inv10_neutral_event_zero():
    """规格：λ_NEUTRAL = 0 且 NEUTRAL 敞口帽 = 1.0（单纯形下 gross<=1 永不超帽），
    NEUTRAL 态 event 分量恒为 0，对 total 无贡献。"""
    rng = np.random.default_rng(110)
    prices = geom_path(rng, 60, 0.0, 0.015, n=3)
    viol = []
    for i in range(10):
        wn = np.asarray(rf.project_to_simplex_with_cash(rng.normal(0.0, 2.0, 3)))
        wp = np.asarray(rf.project_to_simplex_with_cash(rng.normal(0.0, 2.0, 3)))
        res = rf.step_reward(prices, 30, EQ_FLAT, wp, wn, "NEUTRAL", SIG0, ADV0)
        if abs(fpart(res, "event")) > 1e-12:
            viol.append("case %d: parts['event']=%r" % (i, res.parts["event"]))
        if abs(fpart(res, "hard")) > 1e-12:
            viol.append("case %d: NEUTRAL 态 hard=%r != 0" % (i, res.parts["hard"]))
    check("NEUTRAL: 10 组随机权重下 parts['event'] == 0 且 hard == 0",
          not viol, "; ".join(viol[:4]))
    raw, hard = rf.event_penalty("NEUTRAL", 1.0, 0.2)
    check("NEUTRAL: event_penalty('NEUTRAL', gross=1.0, 加仓) == (0, 0)",
          abs(float(raw)) <= 1e-12 and abs(float(hard)) <= 1e-12,
          "raw=%r hard=%r" % (raw, hard))


# ---------------------------------------------------------------- 附: 结果对象契约

def inv11_result_contract():
    rng = np.random.default_rng(111)
    prices = geom_path(rng, 60, 0.0, 0.01, n=2)
    w = np.array([0.25, 0.25])
    res = rf.step_reward(prices, 30, EQ_FLAT, w, w, "NEUTRAL", SIG0, ADV0)
    need = {"r_vol", "g_dd", "cost", "event", "hard", "turnover"}
    check("结果对象: parts 含 r_vol/g_dd/cost/event/hard/turnover 六键",
          need.issubset(set(res.parts.keys())),
          "keys=%s" % sorted(res.parts.keys()))
    check("结果对象: total 为有限 float、terminal 为 bool",
          np.isfinite(float(res.total)) and isinstance(bool(res.terminal), bool))


# ---------------------------------------------------------------- main

def main():
    print("奖励函数不变量测试（规格派生自 reward-function.md v1.0 + event-risk-layer.md v1.0）")
    print("撰写者未阅读实现代码。numpy=%s" % np.__version__)

    section("0. 契约常量")
    run(inv0_constants)
    section("1. 单纯形投影（杠杆/做空不可表达）")
    run(inv1_simplex)
    section("2. 持仓耦合（r_vol = 组合加权，现金贡献 0）")
    run(inv2_position_coupling)
    section("3. λ 单次计费（事件罚分不得双重相乘）")
    run(inv3_lambda_single_billing)
    section("4. 非对称映射（负端 ×1.5，clip 外侧不测）")
    run(inv4_asymmetry)
    section("5. 回撤凸惩罚 + 阶梯跳升 + terminal")
    run(inv5_drawdown_ladder)
    section("6. 交易成本（√ 次线性冲击 / 单调 / 零交易零成本）")
    run(inv6_transaction_cost)
    section("7. 危险状态加仓硬罚")
    run(inv7_hard_rule)
    section("8. 分量有界（clip 防单项刷分）")
    run(inv8_boundedness)
    section("9. 换手率超帽罚分（断言 total 之差）")
    run(inv9_turnover)
    section("10. NEUTRAL 态事件分量恒 0")
    run(inv10_neutral_event_zero)
    section("11. 结果对象契约")
    run(inv11_result_contract)

    n_all = len(_RESULTS)
    n_fail = sum(1 for _, ok in _RESULTS if not ok)
    print("\n---------------------------------------------")
    print("合计 %d 项断言：通过 %d，失败 %d" % (n_all, n_all - n_fail, n_fail))
    if n_fail:
        print("失败清单:")
        for name, ok in _RESULTS:
            if not ok:
                print("  - " + name)
        sys.exit(1)
    print("全部不变量通过。")
    sys.exit(0)


if __name__ == "__main__":
    main()
