# -*- coding: utf-8 -*-
"""
test_reward_invariants.py — 交易奖励函数不变量测试（规格派生）v1.2

声明：本套件从 reward-function.md v1.2（S1-S6 规格定稿）+ event-risk-layer.md
+ redteam-2026-07-12.md（H1/H2/H3/H5/H6 攻击场景固化为回归不变量）派生，
撰写者未阅读实现代码（尤其未读 reward_function.py）。
测试描述"设计说应该怎样"，不描述"代码现在怎样"。

v1.2 升级（2026-07-12，治理第②步：先规格、再裁判、后实现）：
 - inv0  契约常量：DD_TERMINAL_PENALTY -10 → -25（S4）
 - inv4  非对称映射改用"前向同窗波动"构造（S1 后滞后波动率不再进入 f(r_vol)）
 - inv8  终止值 -25；随机 adv 采样收窄至单位契约带内（见 J16）
 - inv12 S1 波动率同期化（红队 H1 回归：滞后历史平静/喧闹不改分；前向波动加倍→分数减半）
 - inv13 S2 超帽停留累罚 dwell（红队 H2 回归：k=3 罚 2 倍、封顶 4 倍、降帽/离态清零）
 - inv14 S3 成分集中度 HHI 项（红队 H3 回归：SHOCK 帽内全押≠免费；NEUTRAL 不罚集中度）
 - inv15 S4 终止惩罚单调化（红队 H5 回归：跌穿止损不得比 dd=0.19 恶性步更便宜）
 - inv16 S5 RewardEngine 引擎化（红队 H6 回归：截断净值抹不掉高水位；H4 回归：adv/book 单位带宽）
 - inv17 S6 训练模式 h=3 窗口局部性（G-3 前向重叠去重）
 其余 v1.1 不变量按兼容性说明原样保留。

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
 J4 事件超帽罚分口径 = over/cap（接口契约给定）——v1.2 起乘 dwell 修正
    min(1+0.5×(k−1),4) 并加 HHI 集中度项；k=1 且 HHI<=0.5 时退化为 over/cap，
    v1.1 的数值断言因此原样保留（兼容性说明）。
 J5 成本"冲击项"随 trade_value 呈 √ 次线性（契约明示），
    即冲击项 ∝ sqrt(x/V)，不是 Almgren 总冲击成本的 x^1.5。
 J6 回撤口径（当前回撤 vs 历史最大回撤）有歧义：所有测试权益曲线一律以
    谷底收尾，两种口径数值一致，测试对口径不敏感。
 J7 "零交易零成本"：固定费只对实际发生的交易收取，trade_value=0 时成本为 0。
 J8 "分档跳升"幅度未量化：判据取"跨阶梯增量 > 2×相邻同宽平滑增量"
    （光滑凸函数的相邻增量比约 1.06，>2 只能来自跳升）。
 J9 turnover <= TURNOVER_CAP 时罚分为 0（"换手率超帽→罚分"的反面推定）。
 J10 近零波动/极端输入不得产生 NaN/Inf（由"各分量有界 clip 防单项刷分"推定）。
 ---- v1.2 新增判定 ----
 J11 v1.2 起 event ratio 理论上可达 3 量级：inv8 断言 parts['event'] 存
    "乘 λ 前、clip 后"的口径（若存乘 λ 后值将与"各分量有界 <=CLIP"冲突）；
    λ 计费本身仍按 J1 用 total 差分验证。
 J12 fwd_ret 与日收益口径（log 还是简单收益）未定：构造一律用小幅路径
    （|日收益| <= 1%），两种口径一阶一致，比值断言容差已覆盖。
 J13 vol_fwd 的 std 自由度（ddof=0/1）未定：同窗"倍增→减半"与镜像断言
    对 ddof 不敏感，不断言分数绝对量级。
 J14 S6 train 模式"只用 h=3"是否保留 0.3 周期权重未定：只断言窗口局部性、
    符号与 step_reward 透传一致性，不断言量级。
 J15 adv/book 带宽 [1e-4,1e6] 边界开闭未定：只测带内（1e3/1e5）与带外
    （1e8/1e-5），不测边界点。带宽校验按 S5 属引擎职责；功能式 API 不施加
    此校验（inv9 沿用 v1.1 的 adv=1e12 用法，兼容性说明未列 inv9 为受影响项）。
 J16 inv8 的随机 adv 采样由 10^[-6,9] 收窄至 10^[-3,5.5]（与单位契约一致的
    带内），保留"极小 ADV → 冲击爆表须被 clip"的检验力（adv=1e-3 时冲击项
    仍远超 CLIP）。
 J17 S2 的引擎 dwell 断言用 parts['event'] 的步间比值（×1.5/×2/×4），
    对 parts 存储口径（乘 λ 前后）不敏感。
 J18 引擎构造以 API 契约 RewardEngine(w=None) 为准（规格文 S5 的
    (book_currency_unit, adv_unit_check) 形参表述与契约不一致，契约优先）；
    引擎初始高水位 = 首个 equity_point（无先验峰值，首步 dd=0）。
 J19 terminal 边界 dd==0.20 的开闭未定：沿用 v1.1 做法避开精确边界；
    S4 单调性用 0.19 / 0.21 两点。
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


def raises_valueerror(fn):
    """fn() 抛 ValueError -> True；不抛或抛其它异常 -> False。"""
    try:
        fn()
    except ValueError:
        return True
    except Exception:
        return False
    return False


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


def fwd_block(amp, drift):
    """15 期前向对数收益：漂移 drift + 零和摆动 amp×e。
    e 的部分和在 k=3/7/15 处均为 0，故 fwd_ret_h 只由 drift 决定、
    vol_fwd_h 只由 amp 决定——分子分母可独立调节（S1 构造核心）。"""
    e = np.array([1., -1., 0., 1., -1., 1., -1.,
                  1., -1., 1., -1., 1., -1., 1., -1.])
    return drift + amp * e


def path_with_history(hist_lr, block):
    """历史对数收益 hist_lr + 15 期前向块 block -> (prices, t)。
    t = len(hist_lr)，即历史末点下标；prices 长度 t+16。"""
    lp = np.concatenate([[0.0], np.cumsum(np.asarray(hist_lr, float))])
    lp_all = np.concatenate([lp, lp[-1] + np.cumsum(np.asarray(block, float))])
    return 100.0 * np.exp(lp_all), len(np.asarray(hist_lr, float))


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
    check("常量: DD_TERMINAL_PENALTY == -25.0（v1.2/S4，v1.1 为 -10）",
          float(rf.DD_TERMINAL_PENALTY) == -25.0)
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
    λ·event，两个不同 gross × 两个不同 λ 交叉验证不存在双重相乘。
    v1.2 注：两组权重的 HHI 分别为 0.4286/0.375（均 <=0.5，集中度项为 0），
    且功能式 API 的 dwell_k 缺省 1（乘子 1.0），故 v1.1 数值断言原样保留（J4）。"""
    rng = np.random.default_rng(103)
    t = 30
    prices = geom_path(rng, 60, 0.005, 0.01, n=3)

    # 权重和取二进制精确值，避免 gross 浮点边界误触"加仓"硬罚
    for wv, gross in [
        (np.array([0.5, 0.25, 0.125]), 0.875),
        (np.array([0.5, 0.25, 0.25]), 1.0),
    ]:
        # v1.2 设计自检：所选权重的 HHI 必须 <=0.5，保证 S3 集中度项为 0
        hhi = float(np.sum((wv / wv.sum()) ** 2))
        check("λ 单次: gross=%.3f 测试权重 HHI=%.4f <= 0.5（S3 项为 0 的前置）"
              % (gross, hhi), hhi <= 0.5 + 1e-12)
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

        # event_penalty 返回值必须是未乘 λ 的原始罚分（dwell_k/hhi 走缺省）
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
    v1.2 改造（兼容性说明）：S1 后归一化分母 = 前向同窗已实现波动，
    改用 fwd_block 构造——镜像漂移 ±drift + 相同零和摆动 amp×e：
    fwd_ret_h 反号、vol_fwd_h 相同 => |score(负)| ≈ ASYMMETRY×|score(正)|。
    （v1.1 的常数漂移构造在 S1 下前向波动为 0，z 触 clip，不再适用。）
    先断言两侧都远离 ±CLIP。对 fwd_ret/std 口径不敏感（J12/J13）。"""
    rng = np.random.default_rng(104)
    clip = float(rf.COMPONENT_CLIP)
    pre_viol, ratio_viol = [], []
    n_cases = 0
    for rep in range(5):
        hist_lr = 0.01 * rng.standard_normal(25)     # 历史段（S1 后不应影响分数）
        for amp, drift in ((0.004, 0.0004), (0.008, 0.0006)):
            n_cases += 1
            p_up, t = path_with_history(hist_lr, fwd_block(amp, +drift))
            p_dn, _ = path_with_history(hist_lr, fwd_block(amp, -drift))
            su = float(scores_of(p_up, t)[0])
            sd = float(scores_of(p_dn, t)[0])
            tag = "rep=%d amp=%g drift=%g" % (rep, amp, drift)
            # 前置：两侧都不在 clip 上，且量级足以测比值
            if not (0.02 < su < 0.9 * clip and -0.9 * clip < sd < -0.02):
                pre_viol.append("%s: su=%.4f sd=%.4f 触界或量级过小" % (tag, su, sd))
                continue
            ratio = abs(sd) / abs(su)
            if abs(ratio - float(rf.ASYMMETRY)) > 0.12:
                ratio_viol.append("%s: ratio=%.4f (期望≈1.5)" % (tag, ratio))
    check("非对称: %d 组镜像前向块两侧分数均远离 ±CLIP（前置条件）" % n_cases,
          not pre_viol, "; ".join(pre_viol[:4]))
    check("非对称: |负向分数| ≈ ASYMMETRY×|正向分数|（前向同窗构造，容差 ±0.12）",
          not ratio_viol, "; ".join(ratio_viol[:4]))


# ---------------------------------------------------------------- 5. 回撤阶梯

def inv5_drawdown_ladder():
    """规格：g(DD) 凸增；触 0.10/0.15 分档跳升；dd>=0.20 回合终止，
    total = DD_TERMINAL_PENALTY（v1.2 = -25，S4）。曲线一律以谷底收尾（J6）。"""
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

    # terminal 分界（dd 值取二进制精确数，避免浮点边界误判，J19）
    for dd, expect_term in [(0.05, False), (0.19, False),
                            (0.203125, True), (0.25, True), (0.35, True)]:
        _, term = g_of(dd)
        check("回撤: dd=%.6f -> terminal == %s" % (dd, expect_term),
              term == expect_term)

    # terminal 时 step_reward.total == DD_TERMINAL_PENALTY (== -25, v1.2)
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
    terminal 情形豁免分量断言，单独断言 total == DD_TERMINAL_PENALTY (=-25)。
    任何 NaN/Inf 均违规（J10）。
    v1.2 改动：adv 采样收窄至 10^[-3,5.5]（单位契约带内，J16）；
    parts['event'] 的 <=CLIP 断言含义见 J11（存乘 λ 前、clip 后口径）。"""
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
        adv = 10.0 ** float(rng.uniform(-3, 5.5))    # 单位契约带内（J16）；
        #   adv=1e-3 时冲击项仍爆表 -> 必须被 clip（保留原检验力）
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
    check("有界: terminal 情形(%d 例) total == DD_TERMINAL_PENALTY (=-25)" % n_term,
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


# ---------------------------------------------------------------- 12. S1 波动率同期化

def inv12_s1_synchronous_vol():
    """S1（红队 H1 回归）：f(r_vol) 归一化分母 = 前向同窗已实现波动，
    滞后历史波动率不再进入。两条不变量：
    (a) 滞后历史（平静 σ=0.005 vs 喧闹 σ=0.040，即 H1 原始参数）+ 逐位完全
        相同的前向路径 -> 分数必须相同（v1.1 实测为 4.00 倍套利，此处应归零）；
    (b) 同前向收益、前向波动加倍 -> 分数减半（同窗归一化生效；J12/J13 使
        断言对收益/std 口径不敏感）。"""
    rng = np.random.default_rng(112)
    t_hist = 25

    # (a) 历史不变性：末端对齐用 x-x[t]+y[t] 逐元素运算，lp[t] 浮点精确相等，
    #     前向段由同一数组延拓 -> 前向价格逐位相同
    viol_a = []
    hist_pairs = [(0.005, 0.040), (0.001, 0.020), (0.0005, 0.060)]
    for rep, (sig_calm, sig_noisy) in enumerate(hist_pairs):
        block = fwd_block(0.004 * (1 + rep % 2), 0.0005 + 0.0002 * rep)
        lp_calm = np.concatenate([[0.0], np.cumsum(sig_calm * rng.standard_normal(t_hist))])
        lp_noisy = np.concatenate([[0.0], np.cumsum(sig_noisy * rng.standard_normal(t_hist))])
        lp_noisy = lp_noisy - lp_noisy[-1] + lp_calm[-1]     # 末端精确对齐
        fwd_lp = np.cumsum(block)
        p_calm = 100.0 * np.exp(np.concatenate([lp_calm, lp_calm[-1] + fwd_lp]))
        p_noisy = 100.0 * np.exp(np.concatenate([lp_noisy, lp_noisy[-1] + fwd_lp]))
        sc = float(scores_of(p_calm, t_hist)[0])
        sn = float(scores_of(p_noisy, t_hist)[0])
        if abs(sc - sn) > 1e-9:
            viol_a.append("rep=%d(σ_hist %.4g vs %.4g): %.9f vs %.9f 差 %.3e"
                          % (rep, sig_calm, sig_noisy, sc, sn, abs(sc - sn)))
        if rep == 0 and abs(sc) < 1e-9:
            viol_a.append("rep=0: 分数为 0，测试无效")
    check("S1(H1 回归): 3 组平静/喧闹滞后历史 + 相同前向路径 -> 分数相同"
          "（含 H1 原始参数 σ=0.005 vs 0.040，v1.1 为 4.00 倍）",
          not viol_a, "; ".join(viol_a[:3]))

    # (b) 前向波动加倍 -> 分数减半（正负两侧各测；drift/摆动可独立调节）
    viol_b, pre_b = [], []
    for rep in range(3):
        hist_lr = 0.008 * rng.standard_normal(t_hist)
        for sign in (+1.0, -1.0):
            amp, drift = 0.004 * (1 + rep), sign * 0.0004 * (1 + rep)
            p1, t = path_with_history(hist_lr, fwd_block(amp, drift))
            p2, _ = path_with_history(hist_lr, fwd_block(2.0 * amp, drift))
            s1 = float(scores_of(p1, t)[0])
            s2 = float(scores_of(p2, t)[0])
            tag = "rep=%d sign=%+.0f" % (rep, sign)
            if not (0.02 < abs(s1) < 0.9 * float(rf.COMPONENT_CLIP)):
                pre_b.append("%s: s1=%.4f 触界或过小" % (tag, s1))
                continue
            if abs(s2 / s1 - 0.5) > 0.02:
                viol_b.append("%s: s2/s1=%.4f (期望 0.5)" % (tag, s2 / s1))
    check("S1: 倍增构造两侧分数远离 ±CLIP（前置条件）", not pre_b, "; ".join(pre_b[:3]))
    check("S1: 同前向收益、前向波动 ×2 -> 分数 ×0.5（±0.02，正负两侧共 6 组）",
          not viol_b, "; ".join(viol_b[:3]))


# ---------------------------------------------------------------- 13. S2 超帽停留累罚

def inv13_s2_dwell():
    """S2（红队 H2 回归）：dwell 计数 k = 状态∈{E,S} 且 gross>cap 的连续步数。
    event_ratio = (over/cap)×min(1+0.5×(k−1), 4)。
    引擎侧用 parts['event'] 步间比值断言（J17，存储口径不敏感）：
    第 3 步 = 第 1 步 ×2.0；第 7 步起封顶 ×4；降到帽内/离开状态即清零。
    功能式 event_penalty(dwell_k=...) 直接对公式精确断言。"""
    rng = np.random.default_rng(113)
    prices = geom_path(rng, 60, 0.0, 0.01, n=2)
    w_over = np.array([0.275, 0.275])   # gross 0.55 > SHOCK 帽 0.5；HHI=0.5 -> S3 项 0
    w_in = np.array([0.2, 0.2])         # gross 0.40 帽内

    def hold(eng, w, st):
        return eng.step(prices, 30, 1.0, w, w, st, SIG0, 1.0e5, book_value=1.0)

    eng = rf.RewardEngine()
    ev = [fpart(hold(eng, w_over, "SHOCK"), "event") for _ in range(9)]
    r1 = ev[0]
    check("S2: 引擎第 1 步超帽 event ratio > 0（k=1 基准）", r1 > 1e-9, "ev=%s" % ev)
    if r1 > 1e-9:
        check("S2: 第 2 步 = 第 1 步 ×1.5（k=2）", abs(ev[1] / r1 - 1.5) < 1e-6,
              "ev[1]/r1=%.6f" % (ev[1] / r1))
        check("S2(H2 回归): 第 3 步 = 第 1 步 ×2.0（k=3）", abs(ev[2] / r1 - 2.0) < 1e-6,
              "ev[2]/r1=%.6f" % (ev[2] / r1))
        check("S2: 第 7/8/9 步封顶 ×4.0（min(1+0.5(k−1),4)）",
              abs(ev[6] / r1 - 4.0) < 1e-6 and abs(ev[7] - ev[6]) < 1e-9
              and abs(ev[8] - ev[6]) < 1e-9,
              "ev[6..8]/r1=%s" % [e / r1 for e in ev[6:]])
        check("S2: 累罚序列单调不减", all(ev[i + 1] >= ev[i] - 1e-12 for i in range(8)),
              "ev=%s" % ev)

    # 降到帽内 -> 清零；再超帽 -> k 从 1 重计（重加仓触发硬罚是 v1.1 规则，一并断言）
    r_drop = eng.step(prices, 30, 1.0, w_over, w_in, "SHOCK", SIG0, 1.0e5,
                      book_value=1.0)          # 从超帽减到帽内
    check("S2: 合规减仓到帽内 -> event==0 且 hard==0（合规者不再吃亏）",
          abs(fpart(r_drop, "event")) < 1e-12 and abs(fpart(r_drop, "hard")) < 1e-12,
          "event=%r hard=%r" % (r_drop.parts["event"], r_drop.parts["hard"]))
    r_back = eng.step(prices, 30, 1.0, w_in, w_over, "SHOCK", SIG0, 1.0e5,
                      book_value=1.0)          # 帽内再加回超帽
    check("S2: 降帽后再超 -> 计数已清零，event ratio == 第 1 步值",
          abs(fpart(r_back, "event") - r1) < 1e-9,
          "got=%.9f expect=%.9f" % (fpart(r_back, "event"), r1))
    check("S2: 降帽后再超属 SHOCK 加仓 -> hard == HARD_RULE_PENALTY（v1.1 规则不回退）",
          abs(fpart(r_back, "hard") - float(rf.HARD_RULE_PENALTY)) < 1e-9,
          "hard=%r" % r_back.parts["hard"])

    # 离开状态 -> 清零
    hold(eng, w_over, "NEUTRAL")        # NEUTRAL 间奏（gross 不变，无硬罚）
    r_re = hold(eng, w_over, "SHOCK")
    check("S2: 离开状态（NEUTRAL 间奏）后回到 SHOCK -> k 重新从 1 计",
          abs(fpart(r_re, "event") - r1) < 1e-9,
          "got=%.9f expect=%.9f" % (fpart(r_re, "event"), r1))

    # 功能式公式精确断言（o<=0.6, k 封顶后 <=2.4 < CLIP，避开可能的 clip）
    viol = []
    for st, cap in (("SHOCK", 0.5), ("ELEVATED", 0.75)):
        for o in (0.1, 0.4, 0.6):
            gross = cap * (1.0 + o)
            for k in (1, 2, 3, 5, 7, 9):
                ratio, hard = rf.event_penalty(st, gross, gross, dwell_k=k, hhi=0.0)
                expect = o * min(1.0 + 0.5 * (k - 1), 4.0)
                if abs(float(ratio) - expect) > 1e-9 or abs(float(hard)) > 1e-12:
                    viol.append("%s o=%.1f k=%d: ratio=%.9f expect=%.9f hard=%r"
                                % (st, o, k, float(ratio), expect, hard))
    check("S2: event_penalty(dwell_k) 公式精确 == (over/cap)×min(1+0.5(k−1),4)（36 组）",
          not viol, "; ".join(viol[:4]))
    r_def, _ = rf.event_penalty("SHOCK", 0.55, 0.55)
    check("S2: dwell_k 缺省=1 与 v1.1 行为一致（over/cap=0.1）",
          abs(float(r_def) - 0.1) < 1e-9, "got=%r" % r_def)


# ---------------------------------------------------------------- 14. S3 成分集中度

def inv14_s3_hhi():
    """S3（红队 H3 回归）：HHI = Σ(w_i/gross)²；非 NEUTRAL 态
    event_ratio += clip((HHI−0.5)×2, 0, 1) × (gross/cap)。
    SHOCK 帽内(0.5) 单票全押 vs 两票均分：前者 event ratio 更大，
    total 差值 == λ_S × HHI 项（用双资产同价路径隔离 r_vol）；
    NEUTRAL 态不罚集中度；gross=0 时 HHI 定义 0、无 NaN。"""
    # 功能式公式精确断言
    viol = []
    for hhi, expect in ((0.0, 0.0), (0.25, 0.0), (0.5, 0.0),
                        (0.625, 0.25), (0.75, 0.5), (1.0, 1.0)):
        ratio, hard = rf.event_penalty("SHOCK", 0.5, 0.5, dwell_k=1, hhi=hhi)
        if abs(float(ratio) - expect) > 1e-9 or abs(float(hard)) > 1e-12:
            viol.append("hhi=%.3f: ratio=%.9f expect=%.9f" % (hhi, float(ratio), expect))
    check("S3: SHOCK 帽内(gross=0.5) HHI 项 == clip((HHI−0.5)×2,0,1)×1.0（6 档）",
          not viol, "; ".join(viol[:4]))

    r_e, _ = rf.event_penalty("ELEVATED", 0.5, 0.5, dwell_k=1, hhi=1.0)
    check("S3: ELEVATED 帽内全押 HHI 项 == 1×(0.5/0.75)=0.6667",
          abs(float(r_e) - 0.5 / 0.75) < 1e-9, "got=%r" % r_e)
    r_c, _ = rf.event_penalty("SHOCK", 0.6, 0.6, dwell_k=1, hhi=1.0)
    check("S3: 超帽+全押叠加 == over/cap + 1×(gross/cap) = 0.2+1.2 = 1.4",
          abs(float(r_c) - 1.4) < 1e-9, "got=%r" % r_c)
    r_ck, _ = rf.event_penalty("SHOCK", 0.6, 0.6, dwell_k=3, hhi=1.0)
    check("S3: dwell 只乘超帽项不乘 HHI 项（k=3: 0.2×2 + 1.2 = 1.6）",
          abs(float(r_ck) - 1.6) < 1e-9, "got=%r" % r_ck)
    r_n, h_n = rf.event_penalty("NEUTRAL", 1.0, 1.0, dwell_k=5, hhi=1.0)
    check("S3: NEUTRAL 态不罚集中度（hhi=1 -> ratio==0）",
          abs(float(r_n)) <= 1e-12 and abs(float(h_n)) <= 1e-12,
          "ratio=%r hard=%r" % (r_n, h_n))
    r_z, h_z = rf.event_penalty("SHOCK", 0.0, 0.0, dwell_k=1, hhi=0.0)
    check("S3: gross=0（HHI 定义 0）-> ratio==0 且有限",
          np.isfinite(float(r_z)) and abs(float(r_z)) <= 1e-12, "ratio=%r" % r_z)

    # step_reward 端到端：双资产同价路径隔离 r_vol，prev==new 隔离成本/换手/硬罚
    rng = np.random.default_rng(114)
    p1 = geom_path(rng, 60, 0.002, 0.01)
    prices = np.column_stack([p1, p1])
    w_conc = np.array([0.5, 0.0])       # HHI=1
    w_mid = np.array([0.375, 0.125])    # HHI=0.625
    w_split = np.array([0.25, 0.25])    # HHI=0.5
    res_c = rf.step_reward(prices, 30, EQ_FLAT, w_conc, w_conc, "SHOCK", SIG0, ADV0)
    res_m = rf.step_reward(prices, 30, EQ_FLAT, w_mid, w_mid, "SHOCK", SIG0, ADV0)
    res_s = rf.step_reward(prices, 30, EQ_FLAT, w_split, w_split, "SHOCK", SIG0, ADV0)
    check("S3: 同价双资产下三种结构 r_vol 相同（隔离前置）",
          abs(fpart(res_c, "r_vol") - fpart(res_s, "r_vol")) < 1e-9
          and abs(fpart(res_m, "r_vol") - fpart(res_s, "r_vol")) < 1e-9,
          "r_vol c/m/s=%.9f/%.9f/%.9f"
          % (fpart(res_c, "r_vol"), fpart(res_m, "r_vol"), fpart(res_s, "r_vol")))
    check("S3(H3 回归): SHOCK 帽内单票全押 event ratio > 两票均分（后者为 0）",
          fpart(res_c, "event") > fpart(res_s, "event") + 1e-9
          and abs(fpart(res_s, "event")) < 1e-12,
          "event c=%r s=%r" % (res_c.parts["event"], res_s.parts["event"]))
    d_cs = float(res_s.total) - float(res_c.total)
    d_ms = float(res_s.total) - float(res_m.total)
    check("S3(H3 回归): total(均分) − total(全押) == λ_S×1.0 = 2.0（差值≈λ 修正公式）",
          abs(d_cs - 2.0) < 1e-6, "diff=%.9f expect=2.0" % d_cs)
    check("S3: total(均分) − total(中间 HHI=0.625) == λ_S×0.25 = 0.5",
          abs(d_ms - 0.5) < 1e-6, "diff=%.9f expect=0.5" % d_ms)

    # NEUTRAL 全押不罚（平时集中度归 risk-rules 管，事件层只管危险时刻）
    res_n = rf.step_reward(prices, 30, EQ_FLAT,
                           np.array([1.0, 0.0]), np.array([1.0, 0.0]),
                           "NEUTRAL", SIG0, ADV0)
    check("S3: NEUTRAL 态单票全押 parts['event'] == 0",
          abs(fpart(res_n, "event")) <= 1e-12, "event=%r" % res_n.parts["event"])
    # SHOCK 空仓：event 0 且无 NaN
    res_z = rf.step_reward(prices, 30, EQ_FLAT,
                           np.array([0.0, 0.0]), np.array([0.0, 0.0]),
                           "SHOCK", SIG0, ADV0)
    check("S3: SHOCK 态空仓（gross=0）event==0 且 total 有限",
          abs(fpart(res_z, "event")) <= 1e-12 and np.isfinite(float(res_z.total)),
          "event=%r total=%r" % (res_z.parts["event"], res_z.total))

    # 随机功能式公式抽查（gross<=1.3cap、k<=3、hhi∈[0,1]，避开 clip 区）
    rng2 = np.random.default_rng(1141)
    viol2 = []
    for i in range(20):
        st = ("ELEVATED", "SHOCK")[int(rng2.integers(0, 2))]
        cap = rf.EVENT_EXPOSURE_CAP[st]
        gross = float(cap * rng2.uniform(0.5, 1.3))
        k = int(rng2.integers(1, 4))
        hhi = float(rng2.uniform(0.0, 1.0))
        over = max(gross - cap, 0.0)
        expect = (over / cap) * min(1.0 + 0.5 * (k - 1), 4.0) \
            + min(max((hhi - 0.5) * 2.0, 0.0), 1.0) * (gross / cap)
        ratio, _ = rf.event_penalty(st, gross, gross, dwell_k=k, hhi=hhi)
        if abs(float(ratio) - expect) > 1e-9:
            viol2.append("case %d: st=%s gross=%.4f k=%d hhi=%.3f got=%.9f expect=%.9f"
                         % (i, st, gross, k, hhi, float(ratio), expect))
    check("S3: 20 组随机 (状态,gross,k,hhi) 全公式精确匹配",
          not viol2, "; ".join(viol2[:4]))


# ---------------------------------------------------------------- 15. S4 终止惩罚单调化

def inv15_s4_terminal_monotone():
    """S4（红队 H5 回归）：DD_TERMINAL_PENALTY=-25 <= 任何非终止步可达最坏值
    （规格给出的非终止最坏 ≈ -23）。对任意固定 (状态,动作)：
    dd=0.19 -> 0.21 的 total 单调变差或相等；terminal 时 total == -25。
    v1.1 实测反例：dd=0.19 恶性步 -13.83 比跌穿 -10.00 更痛（教算法
    '跌穿止损封顶损失'），此处固化为回归。"""
    rng = np.random.default_rng(115)
    viol_mono, viol_term, viol_floor = [], [], []
    for i in range(10):
        prices = geom_path(rng, 60, float(rng.uniform(-0.02, 0.02)),
                           float(rng.uniform(0.004, 0.03)), n=3)
        wp = np.asarray(rf.project_to_simplex_with_cash(rng.normal(0.0, 2.0, 3)))
        wn = np.asarray(rf.project_to_simplex_with_cash(rng.normal(0.0, 2.0, 3)))
        st = ("NEUTRAL", "ELEVATED", "SHOCK")[i % 3]
        sd = float(rng.uniform(0.005, 0.5))
        adv = 10.0 ** float(rng.uniform(2, 6))
        r19 = rf.step_reward(prices, 30, eq_for_dd(0.19), wp, wn, st, sd, adv)
        r21 = rf.step_reward(prices, 30, eq_for_dd(0.21), wp, wn, st, sd, adv)
        if bool(r19.terminal):
            viol_term.append("case %d: dd=0.19 不应 terminal" % i)
            continue
        if not bool(r21.terminal) or abs(float(r21.total) - (-25.0)) > 1e-9:
            viol_term.append("case %d: dd=0.21 terminal=%r total=%r（应 True/-25）"
                             % (i, r21.terminal, r21.total))
        if float(r21.total) > float(r19.total) + 1e-9:
            viol_mono.append("case %d(st=%s): total(0.21)=%.4f > total(0.19)=%.4f"
                             % (i, st, float(r21.total), float(r19.total)))
        if float(r19.total) < float(rf.DD_TERMINAL_PENALTY) - 1e-9:
            viol_floor.append("case %d: 非终止 total=%.4f 低于终止罚 -25（惩罚面仍非单调）"
                              % (i, float(r19.total)))
    check("S4: 10 组固定(状态,动作) dd=0.19 非 terminal、dd=0.21 terminal 且 total==-25",
          not viol_term, "; ".join(viol_term[:4]))
    check("S4(H5 回归): dd 0.19 -> 0.21 的 total 单调变差或相等（10 组）",
          not viol_mono, "; ".join(viol_mono[:4]))
    check("S4: 非终止步 total 不低于 DD_TERMINAL_PENALTY（终止=惩罚面下界）",
          not viol_floor, "; ".join(viol_floor[:4]))

    # H5 原始"恶性步"重演：dd=0.19 + SHOCK 加仓 + 全押 + 大换手 + 逆势持仓
    rng2 = np.random.default_rng(1151)
    prices_dn = geom_path(rng2, 60, -0.02, 0.004, n=2)   # 强下跌 -> r_vol 触 -CLIP
    wp = np.array([0.4, 0.0])
    wn = np.array([0.0, 0.9])       # 加仓(0.4->0.9)+全换手+超帽+HHI=1
    nasty = rf.step_reward(prices_dn, 30, eq_for_dd(0.19), wp, wn, "SHOCK", 0.5, 1.0e3)
    crash = rf.step_reward(prices_dn, 30, eq_for_dd(0.21), wp, wn, "SHOCK", 0.5, 1.0e3)
    check("S4(H5 回归): 恶性步(dd=0.19,SHOCK加仓全押大换手) 非 terminal 且 total >= -25",
          (not bool(nasty.terminal))
          and float(nasty.total) >= float(rf.DD_TERMINAL_PENALTY) - 1e-9,
          "terminal=%r total=%r" % (nasty.terminal, nasty.total))
    check("S4(H5 回归): 同一恶性动作跌穿(dd=0.21) total==-25 <= 恶性步 total",
          bool(crash.terminal) and abs(float(crash.total) + 25.0) < 1e-9
          and float(crash.total) <= float(nasty.total) + 1e-9,
          "crash=%r nasty=%r" % (crash.total, nasty.total))


# ---------------------------------------------------------------- 16. S5 RewardEngine

def inv16_s5_engine():
    """S5（红队 H6/H4 回归）：RewardEngine 持有回合级高水位与 dwell 计数，
    equity 只传当前点、hwm = max(hwm, equity_point) 由引擎累积——
    外部无法通过截断历史抹掉回撤记忆。adv/book 比值超出 [1e-4,1e6] 抛
    ValueError（带宽校验属引擎职责，J15；边界点不测）。
    引擎初始高水位 = 首个 equity_point（J18）。"""
    rng = np.random.default_rng(116)
    prices = geom_path(rng, 60, 0.0, 0.01, n=2)
    w = np.array([0.25, 0.25])

    def step(eng, eq, adv=1.0e5, book=1.0, st="NEUTRAL"):
        return eng.step(prices, 30, eq, w, w, st, SIG0, adv, book_value=book)

    # (a) H6 回归：截断式逐点喂入，先 1.0 后 0.79 -> dd=0.21 -> terminal/-25
    e1 = rf.RewardEngine()
    r_a1 = step(e1, 1.0)
    r_a2 = step(e1, 0.98)
    r_a3 = step(e1, 0.79)
    check("S5(H6 回归): 逐点喂 1.0/0.98/0.79 -> 前两步非 terminal",
          not bool(r_a1.terminal) and not bool(r_a2.terminal),
          "t1=%r t2=%r" % (r_a1.terminal, r_a2.terminal))
    check("S5(H6 回归): 第 3 步(0.79, 距 hwm=1.0 回撤 21%) terminal==True 且 total==-25"
          "（截断历史抹不掉高水位记忆，v1.1 落差为 +10.64）",
          bool(r_a3.terminal) and abs(float(r_a3.total) - (-25.0)) < 1e-9,
          "terminal=%r total=%r" % (r_a3.terminal, r_a3.total))
    check("S5: 第 2 步(0.98, dd=0.02) g_dd > 0（高水位生效于非终止段）",
          fpart(r_a2, "g_dd") > 1e-12, "g_dd=%r" % r_a2.parts["g_dd"])

    # (b) 高水位棘轮：1.0 -> 1.25 抬升 hwm，跌回 0.9375 = 距 1.25 回撤 25%
    e2 = rf.RewardEngine()
    step(e2, 1.0)
    r_b2 = step(e2, 1.25)
    r_b3 = step(e2, 0.9375)
    check("S5: 高水位棘轮——新高步 dd=0 (g_dd==0) 非 terminal",
          not bool(r_b2.terminal) and abs(fpart(r_b2, "g_dd")) <= 1e-9,
          "g_dd=%r" % r_b2.parts["g_dd"])
    check("S5: 跌回 0.9375（距新高 1.25 回撤 25%）-> terminal 且 total==-25",
          bool(r_b3.terminal) and abs(float(r_b3.total) - (-25.0)) < 1e-9,
          "terminal=%r total=%r" % (r_b3.terminal, r_b3.total))

    # (c) 新引擎无先验峰值：首点 0.79 -> dd=0（J18）
    e3 = rf.RewardEngine()
    r_c1 = step(e3, 0.79)
    check("S5: 新引擎首点 0.79 -> dd=0 非 terminal（初始 hwm=首点，J18）",
          not bool(r_c1.terminal) and abs(fpart(r_c1, "g_dd")) <= 1e-9,
          "terminal=%r g_dd=%r" % (r_c1.terminal, r_c1.parts["g_dd"]))

    # (d) H4 回归：adv/book 单位带宽校验
    e4 = rf.RewardEngine()
    check("S5(H4 回归): adv/book = 1e8/1.0 = 1e8 超带宽 -> ValueError",
          raises_valueerror(lambda: step(e4, 1.0, adv=1.0e8, book=1.0)))
    check("S5(H4 回归): adv/book = 1e-5 超带宽（过小侧）-> ValueError",
          raises_valueerror(lambda: step(rf.RewardEngine(), 1.0, adv=1.0e-5, book=1.0)))
    e5 = rf.RewardEngine()
    ok_in_band = True
    try:
        step(e5, 1.0, adv=1.0e3, book=1.0)      # 比值 1e3 带内
        step(e5, 1.0, adv=1.0e8, book=1.0e3)    # 比值 1e5 带内（校验的是比值不是绝对值）
    except Exception as exc:
        ok_in_band = False
        detail = repr(exc)
    check("S5: 带内比值 1e3 与 1e5（adv=1e8,book=1e3）不抛异常（校验比值而非绝对值）",
          ok_in_band, detail if not ok_in_band else "")

    # (e) 引擎与功能式单步等价（无回撤、NEUTRAL、k 无关场景）
    e6 = rf.RewardEngine()
    r_eng = e6.step(prices, 30, 1.0, w, w, "NEUTRAL", SIG0, 1.0e5, book_value=1.0)
    r_fn = rf.step_reward(prices, 30, EQ_FLAT, w, w, "NEUTRAL", SIG0, 1.0e5)
    check("S5: 良性单步引擎 total == 功能式 total（回合评估以引擎为准，单步语义一致）",
          abs(float(r_eng.total) - float(r_fn.total)) < 1e-9,
          "eng=%r fn=%r" % (r_eng.total, r_fn.total))
    need = {"r_vol", "g_dd", "cost", "event", "hard", "turnover"}
    check("S5: 引擎 RewardResult.parts 含六键且 total 有限",
          need.issubset(set(r_eng.parts.keys())) and np.isfinite(float(r_eng.total)),
          "keys=%s" % sorted(r_eng.parts.keys()))


# ---------------------------------------------------------------- 17. S6 训练模式

def inv17_s6_train_mode():
    """S6（G-3）：mode='train' 时 f(r_vol) 只用 h=3 单周期，
    步 t 的分数只依赖窗口 [t, t+3]（相邻步间隔>=3 则对同一段未来不重复计分）。
    验证法：构造 t+3 之后突变的路径，train 分数必须不变；突变落进窗口则必须变。
    量级/权重口径不断言（J14）。"""
    rng = np.random.default_rng(117)
    t = 30
    prices = geom_path(rng, 60, 0.001, 0.01)

    def tscore(p, tt):
        return float(np.ravel(np.asarray(
            rf.asset_forward_scores(p, tt, mode="train"), dtype=float))[0])

    def escore(p, tt):
        return float(np.ravel(np.asarray(
            rf.asset_forward_scores(p, tt, mode="eval"), dtype=float))[0])

    s_t = tscore(prices, t)
    s_t3 = tscore(prices, t + 3)
    check("S6: train 分数有限且非零（测试有效性前置）",
          np.isfinite(s_t) and abs(s_t) > 1e-12 and np.isfinite(s_t3),
          "s_t=%r s_t3=%r" % (s_t, s_t3))

    # (a) t+3 之后突变（从 t+5 起 ×1.5）：train(t) 不变；eval(t) 必变；train(t+3) 必变
    p_mut5 = prices.copy()
    p_mut5[t + 5:] *= 1.5
    check("S6: 突变 [t+5:] 后 train(t) 分数不变（只依赖 [t,t+3] 窗口）",
          abs(tscore(p_mut5, t) - s_t) <= 1e-12,
          "before=%.9f after=%.9f" % (s_t, tscore(p_mut5, t)))
    check("S6: 同一突变使 eval(t) 分数改变（eval 保留 7/15 周期，对照有效）",
          abs(escore(p_mut5, t) - escore(prices, t)) > 1e-6,
          "eval before=%.9f after=%.9f" % (escore(prices, t), escore(p_mut5, t)))
    check("S6: 同一突变使 train(t+3) 改变（t+5 ∈ [t+3,t+6]，相邻步各管各窗）",
          abs(tscore(p_mut5, t + 3) - s_t3) > 1e-9,
          "before=%.9f after=%.9f" % (s_t3, tscore(p_mut5, t + 3)))

    # (b) 窗口边界锐利：突变 [t+4:] 不影响 train(t)；突变 [t+3:] 必影响
    p_mut4 = prices.copy()
    p_mut4[t + 4:] *= 1.3
    p_mut3 = prices.copy()
    p_mut3[t + 3:] *= 1.3
    check("S6: 突变 [t+4:] 后 train(t) 不变（窗口右界 = t+3）",
          abs(tscore(p_mut4, t) - s_t) <= 1e-12,
          "before=%.9f after=%.9f" % (s_t, tscore(p_mut4, t)))
    check("S6: 突变 [t+3:] 后 train(t) 改变（t+3 是窗口内最后一点）",
          abs(tscore(p_mut3, t) - s_t) > 1e-9,
          "before=%.9f after=%.9f" % (s_t, tscore(p_mut3, t)))

    # (c) 单点突变 t+1（仅步 t 窗口内）：train(t) 变、train(t+3) 不变
    p_mut1 = prices.copy()
    p_mut1[t + 1] *= 1.02
    check("S6: 单点突变 t+1 -> train(t) 变而 train(t+3) 不变（窗口不相交=不重复计分）",
          abs(tscore(p_mut1, t) - s_t) > 1e-9
          and abs(tscore(p_mut1, t + 3) - s_t3) <= 1e-12,
          "Δt=%.3e Δt3=%.3e" % (abs(tscore(p_mut1, t) - s_t),
                                abs(tscore(p_mut1, t + 3) - s_t3)))

    # (d) 缺省 mode == eval；step_reward mode 透传
    s_def = float(np.ravel(np.asarray(rf.asset_forward_scores(prices, t), dtype=float))[0])
    check("S6: asset_forward_scores 缺省 mode == 'eval'",
          abs(s_def - escore(prices, t)) <= 1e-12,
          "default=%.9f eval=%.9f" % (s_def, escore(prices, t)))

    prices2 = np.column_stack([prices, prices * 1.0])
    wv = np.array([0.5, 0.25])
    tr_scores = np.ravel(np.asarray(
        rf.asset_forward_scores(prices2, t, mode="train"), dtype=float))
    res_tr = rf.step_reward(prices2, t, EQ_FLAT, wv, wv, "NEUTRAL", SIG0, ADV0,
                            mode="train")
    check("S6: step_reward(mode='train') 的 r_vol == weights·train_scores（透传）",
          abs(fpart(res_tr, "r_vol") - float(np.dot(wv, tr_scores))) < 1e-9,
          "got=%.9f expect=%.9f" % (fpart(res_tr, "r_vol"),
                                    float(np.dot(wv, tr_scores))))
    res_def = rf.step_reward(prices2, t, EQ_FLAT, wv, wv, "NEUTRAL", SIG0, ADV0)
    res_ev = rf.step_reward(prices2, t, EQ_FLAT, wv, wv, "NEUTRAL", SIG0, ADV0,
                            mode="eval")
    check("S6: step_reward 缺省 mode == 'eval'（total 一致）",
          abs(float(res_def.total) - float(res_ev.total)) <= 1e-12,
          "default=%r eval=%r" % (res_def.total, res_ev.total))


# ---------------------------------------------------------------- main

def main():
    print("奖励函数不变量测试 v1.2（规格派生自 reward-function.md v1.2 S1-S6"
          " + event-risk-layer.md + redteam-2026-07-12.md 回归固化）")
    print("撰写者未阅读实现代码。numpy=%s" % np.__version__)

    section("0. 契约常量")
    run(inv0_constants)
    section("1. 单纯形投影（杠杆/做空不可表达）")
    run(inv1_simplex)
    section("2. 持仓耦合（r_vol = 组合加权，现金贡献 0）")
    run(inv2_position_coupling)
    section("3. λ 单次计费（事件罚分不得双重相乘）")
    run(inv3_lambda_single_billing)
    section("4. 非对称映射（负端 ×1.5，前向同窗构造）")
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
    section("12. S1 波动率同期化（红队 H1 回归）")
    run(inv12_s1_synchronous_vol)
    section("13. S2 超帽停留累罚 dwell（红队 H2 回归）")
    run(inv13_s2_dwell)
    section("14. S3 成分集中度 HHI（红队 H3 回归）")
    run(inv14_s3_hhi)
    section("15. S4 终止惩罚单调化（红队 H5 回归）")
    run(inv15_s4_terminal_monotone)
    section("16. S5 RewardEngine 引擎化（红队 H6/H4 回归）")
    run(inv16_s5_engine)
    section("17. S6 训练模式窗口局部性（G-3）")
    run(inv17_s6_train_mode)

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
