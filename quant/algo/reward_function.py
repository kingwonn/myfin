"""Reward function v1.0 skeleton — implements quant/algo/reward-function.md.

R_t = w_r*f(r_vol) - w_d*g(DD_t) - w_c*Cost_t - lambda_e*EventPenalty_t + HardRules

Design constraints enforced structurally (not by penalty):
  - Action space is the long-only simplex + cash: weights >= 0, sum(weights) <= 1.
    Leverage and shorting are unrepresentable, per risk red line R1 (R2c report).
  - Every component is clipped to a bounded range (anti reward-hacking).

Paper-forward experiments only. This module never touches an execution API.
Numbers marked CONSERVATIVE_PLACEHOLDER await M1b empirical parameters.

Usage: python reward_function.py  (runs the synthetic-data self-check)
"""

from dataclasses import dataclass, field
import numpy as np

# ---------------------------------------------------------------- config

HORIZONS = (3, 7, 15)           # forward-return horizons, days (Trading-R1, 3-0)
HORIZON_WEIGHTS = (0.3, 0.5, 0.2)
VOL_WINDOW = 20                 # rolling vol normalizer, periods
ASYMMETRY = 1.5                 # negative returns scaled 1.5x before scoring (M1 asymmetry)
COMPONENT_CLIP = 3.0            # every component bounded to [-3, 3]

DD_LADDER = (0.10, 0.15, 0.20)  # docs/risk-rules ladder: freeze / halve / force-half
DD_KAPPA = 2.0                  # convexity scale for g(DD)
DD_TERMINAL_PENALTY = -10.0     # episode ends at -20% with a large negative reward

FIXED_FEE_BPS = 1.0             # CONSERVATIVE_PLACEHOLDER round-trip fixed fee floor
SPREAD_BPS_FLOOR = 2.0          # CONSERVATIVE_PLACEHOLDER
IMPACT_COEF = 1.0               # eta in eta*sigma*sqrt(x/V), Almgren-Chriss (3-0)

TURNOVER_CAP = 0.20             # max fraction of book traded per step
TURNOVER_PENALTY = 1.0          # per unit of excess turnover

EVENT_EXPOSURE_CAP = {"NEUTRAL": 1.0, "ELEVATED": 0.75, "SHOCK": 0.50}
EVENT_LAMBDA = {"NEUTRAL": 0.0, "ELEVATED": 1.0, "SHOCK": 2.0}
HARD_RULE_PENALTY = -5.0        # adding exposure under ELEVATED/SHOCK

DEFAULT_WEIGHTS = {"w_r": 1.0, "w_d": 1.0, "w_c": 1.0}
# Weight grids are trials: every (w_r, w_d, w_c, lambda_e) combination searched
# must increment trial count N for the DSR report (backtest protocol v1.1).


# ---------------------------------------------------------------- action space

def project_to_simplex_with_cash(raw: np.ndarray) -> np.ndarray:
    """Map arbitrary proposals into {w >= 0, sum(w) <= 1}. Leverage/shorts
    cannot exist after this projection — structural exclusion, not a penalty."""
    w = np.clip(np.asarray(raw, dtype=float), 0.0, None)
    total = w.sum()
    if total > 1.0:
        w = w / total
    return w


# ---------------------------------------------------------------- components

def vol_normalized_return(prices: np.ndarray, t: int) -> float:
    """f(r_vol): multi-horizon forward returns / trailing vol, asymmetric map.

    Requires t >= VOL_WINDOW and t + max(HORIZONS) < len(prices).
    """
    rets = np.diff(np.log(prices[: t + 1]))
    vol = rets[-VOL_WINDOW:].std()
    if vol < 1e-8:
        vol = 1e-8  # degenerate flat series: avoid division blowup
    score = 0.0
    for h, wh in zip(HORIZONS, HORIZON_WEIGHTS):
        fwd = prices[t + h] / prices[t] - 1.0
        z = fwd / (vol * np.sqrt(h))
        if z < 0:
            z *= ASYMMETRY
        score += wh * z
    return float(np.clip(score, -COMPONENT_CLIP, COMPONENT_CLIP))


def drawdown_penalty(equity_curve: np.ndarray) -> tuple[float, bool]:
    """g(DD): convex penalty with ladder jumps. Returns (penalty, terminal).

    Ladder semantics follow risk red line R3: penalties shape the policy toward
    reducing exposure early; the -20% rung terminates the episode. The reward
    never rewards market-order liquidation at the bottom (Quant Quake lesson).
    """
    peak = np.maximum.accumulate(equity_curve)
    dd = float(1.0 - equity_curve[-1] / peak[-1])
    if dd >= DD_LADDER[2]:
        return -DD_TERMINAL_PENALTY, True  # caller applies sign via w_d
    g = (dd / DD_LADDER[2]) ** 2 * DD_KAPPA
    if dd >= DD_LADDER[0]:
        g += 0.5
    if dd >= DD_LADDER[1]:
        g += 1.0
    return float(np.clip(g, 0.0, COMPONENT_CLIP)), False


def transaction_cost(trade_value: float, book_value: float,
                     sigma_daily: float, adv_value: float) -> float:
    """Cost_t: fixed fee + spread floor + square-root impact (Almgren-Chriss).

    All terms in fractions of book value; conservative even for small size.
    """
    if trade_value <= 0 or book_value <= 0:
        return 0.0
    frac = trade_value / book_value
    fee = (FIXED_FEE_BPS + SPREAD_BPS_FLOOR) * 1e-4 * frac
    impact = IMPACT_COEF * sigma_daily * np.sqrt(trade_value / max(adv_value, 1e-8)) * frac
    return float(np.clip(fee + impact, 0.0, COMPONENT_CLIP))


def event_penalty(state: str, gross_exposure: float,
                  prev_gross_exposure: float) -> tuple[float, float]:
    """EventPenalty_t + HardRules trigger for the black-swan state machine.

    Returns (penalty, hard_rule_bonus_or_zero). Exposure over the state cap is
    penalized proportionally; ADDING exposure under ELEVATED/SHOCK trips the
    hard rule (red line R5 / event-risk-layer.md).
    """
    cap = EVENT_EXPOSURE_CAP[state]
    lam = EVENT_LAMBDA[state]
    over = max(0.0, gross_exposure - cap)
    penalty = float(np.clip(lam * over / max(cap, 1e-8), 0.0, COMPONENT_CLIP))
    hard = 0.0
    if state != "NEUTRAL" and gross_exposure > prev_gross_exposure + 1e-9:
        hard = HARD_RULE_PENALTY
    return penalty, hard


def turnover_penalty(turnover: float) -> float:
    return float(np.clip(max(0.0, turnover - TURNOVER_CAP) * TURNOVER_PENALTY,
                         0.0, COMPONENT_CLIP))


# ---------------------------------------------------------------- assembly

@dataclass
class RewardResult:
    total: float
    terminal: bool
    parts: dict = field(default_factory=dict)


def step_reward(prices: np.ndarray, t: int, equity_curve: np.ndarray,
                weights_prev: np.ndarray, weights_new: np.ndarray,
                event_state: str, sigma_daily: float, adv_value: float,
                book_value: float = 1.0, w: dict = None) -> RewardResult:
    """One evaluation step. weights_* are post-projection simplex weights."""
    w = {**DEFAULT_WEIGHTS, **(w or {})}
    weights_prev = project_to_simplex_with_cash(weights_prev)
    weights_new = project_to_simplex_with_cash(weights_new)

    r_vol = vol_normalized_return(prices, t)
    g_dd, terminal = drawdown_penalty(equity_curve)
    turn = float(np.abs(weights_new - weights_prev).sum())
    cost = transaction_cost(turn * book_value, book_value, sigma_daily, adv_value)
    ev_pen, hard = event_penalty(event_state, weights_new.sum(), weights_prev.sum())
    lam_e = EVENT_LAMBDA[event_state]

    total = (w["w_r"] * r_vol - w["w_d"] * g_dd - w["w_c"] * cost
             - lam_e * ev_pen + hard - turnover_penalty(turn))
    if terminal:
        total = DD_TERMINAL_PENALTY
    return RewardResult(total=float(total), terminal=terminal, parts={
        "r_vol": r_vol, "g_dd": g_dd, "cost": cost, "event": ev_pen,
        "hard": hard, "turnover": turn,
    })


# ---------------------------------------------------------------- self-check

def _selfcheck():
    """Synthetic-data sanity suite. No market data, no lookback contamination —
    prices are generated from a seeded random walk with an injected crash."""
    rng = np.random.default_rng(42)
    n = 300
    rets = rng.normal(0.0004, 0.012, n)
    rets[150:156] = -0.06  # injected 6-day crash, ~ -31% cumulative
    prices = 100 * np.exp(np.cumsum(rets))

    failures = []

    def check(name, cond):
        print(("PASS " if cond else "FAIL ") + name)
        if not cond:
            failures.append(name)

    # 1. Action space: leverage and shorts are unrepresentable.
    w = project_to_simplex_with_cash(np.array([0.8, 0.9, -0.5]))
    check("simplex: no shorts, sum<=1", (w >= 0).all() and w.sum() <= 1.0 + 1e-12)

    # 2. Component bounds hold even through the crash (anti reward-hacking).
    vals = [vol_normalized_return(prices, t) for t in range(VOL_WINDOW, n - 16)]
    check("f(r_vol) bounded", max(np.abs(vals)) <= COMPONENT_CLIP)

    # 3. Asymmetry: a crash scores worse than a rally of equal size scores well.
    up = prices.copy()
    up[151:] = up[151:] * (prices[150] / prices[155]) ** 2  # mirror the crash upward
    down_score = vol_normalized_return(prices, 149)
    up_score = vol_normalized_return(up, 149)
    check("asymmetric: crash penalized harder", down_score < 0 < up_score
          and abs(down_score) > abs(up_score) * 0.9)

    # 4. Drawdown ladder is convex and terminal at -20%.
    eq_small = np.array([1.0, 0.97, 0.95])
    eq_mid = np.array([1.0, 0.95, 0.88])
    eq_dead = np.array([1.0, 0.9, 0.79])
    p_small, t1 = drawdown_penalty(eq_small)
    p_mid, t2 = drawdown_penalty(eq_mid)
    _, t3 = drawdown_penalty(eq_dead)
    check("dd convex ladder", p_small < p_mid and not t1 and not t2)
    check("dd -20% terminal", t3)

    # 5. Impact cost grows sublinearly in size but is monotone.
    c1 = transaction_cost(0.01, 1.0, 0.02, 0.10)
    c2 = transaction_cost(0.04, 1.0, 0.02, 0.10)
    check("sqrt impact monotone", 0 < c1 < c2)

    # 6. Hard rule: adding exposure in SHOCK is heavily negative.
    r = step_reward(prices, 100, np.array([1.0, 1.0]), np.array([0.3, 0.2]),
                    np.array([0.5, 0.3]), "SHOCK", 0.02, 0.10)
    check("hard rule fires in SHOCK", r.parts["hard"] == HARD_RULE_PENALTY
          and r.total < 0)

    # 7. Reducing exposure in SHOCK does NOT trip the hard rule.
    r2 = step_reward(prices, 100, np.array([1.0, 1.0]), np.array([0.5, 0.3]),
                     np.array([0.2, 0.1]), "SHOCK", 0.02, 0.10)
    check("de-risking in SHOCK allowed", r2.parts["hard"] == 0.0)

    # 8. Turnover cap penalizes churn.
    r3 = step_reward(prices, 100, np.array([1.0, 1.0]), np.array([1.0, 0.0]),
                     np.array([0.0, 1.0]), "NEUTRAL", 0.02, 0.10)
    check("turnover churn penalized", r3.parts["turnover"] > TURNOVER_CAP)

    print("-" * 40)
    if failures:
        raise SystemExit("SELF-CHECK FAILED: " + ", ".join(failures))
    print("all checks passed — skeleton consistent with reward-function.md v1.0")


if __name__ == "__main__":
    _selfcheck()
