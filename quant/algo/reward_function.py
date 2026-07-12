"""Reward function v1.1 — implements quant/algo/reward-function.md.

R_t = w_r*f(r_vol) - w_d*g(DD_t) - w_c*Cost_t - lambda_e*EventPenalty_t + HardRules

v1.1 (2026-07-12) — independent-review remediation:
  R-1 fixed: the return component is now PORTFOLIO-COUPLED — r_vol =
      weights_new . asset_forward_scores(...). An all-cash book scores 0;
      full vs empty exposure must differ (see test_reward_invariants.py).
  R-2 fixed: lambda_event is applied ONCE, at assembly. event_penalty()
      returns the unscaled over-cap ratio.
  Terminal semantics cleaned: drawdown_penalty returns a bounded component;
      step_reward overrides total = DD_TERMINAL_PENALTY on the -20% rung.
  Referee separation: invariants live in test_reward_invariants.py, written
      from the spec by a non-implementer; this file's __main__ only smoke-tests.

Known limitation (G-3): overlapping forward horizons double-count adjacent
steps' futures; acceptable for scoring, must be de-overlapped for RL training.

Design constraints enforced structurally (not by penalty):
  - Action space is the long-only simplex + cash: weights >= 0, sum <= 1.
    Leverage and shorting are unrepresentable (risk red line R1).
  - Scoring components are clipped to [-COMPONENT_CLIP, COMPONENT_CLIP]; the
    only exceptions are the hard rule and the terminal episode penalty, which
    are episode-level constants, not scoring components.

Paper-forward experiments only. This module never touches an execution API.
Numbers marked CONSERVATIVE_PLACEHOLDER await further empirical calibration.
"""

from dataclasses import dataclass, field
import numpy as np

# ---------------------------------------------------------------- config

HORIZONS = (3, 7, 15)           # forward-return horizons, days (Trading-R1, 3-0)
HORIZON_WEIGHTS = (0.3, 0.5, 0.2)
VOL_WINDOW = 20                 # rolling vol normalizer, periods
ASYMMETRY = 1.5                 # negative returns scaled 1.5x before scoring (M1 asymmetry)
COMPONENT_CLIP = 3.0            # scoring components bounded to [-3, 3]

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

def _as_2d(prices: np.ndarray) -> np.ndarray:
    p = np.asarray(prices, dtype=float)
    return p[:, None] if p.ndim == 1 else p


def asset_forward_scores(prices: np.ndarray, t: int) -> np.ndarray:
    """Per-asset multi-horizon forward returns / trailing vol, asymmetric map.

    prices: (T,) single asset or (T, n) matrix. Returns shape (n,) of scores,
    each clipped to [-COMPONENT_CLIP, COMPONENT_CLIP].
    Requires t >= VOL_WINDOW and t + max(HORIZONS) < len(prices).
    """
    p = _as_2d(prices)
    rets = np.diff(np.log(p[: t + 1]), axis=0)
    vol = rets[-VOL_WINDOW:].std(axis=0)
    vol = np.where(vol < 1e-8, 1e-8, vol)  # degenerate flat series guard
    scores = np.zeros(p.shape[1])
    for h, wh in zip(HORIZONS, HORIZON_WEIGHTS):
        fwd = p[t + h] / p[t] - 1.0
        z = fwd / (vol * np.sqrt(h))
        z = np.where(z < 0, z * ASYMMETRY, z)
        scores += wh * z
    return np.clip(scores, -COMPONENT_CLIP, COMPONENT_CLIP)


def portfolio_return_score(prices: np.ndarray, t: int,
                           weights: np.ndarray) -> float:
    """f(r_vol), portfolio-coupled (v1.1 / review R-1): weighted sum of
    per-asset scores. Cash (1 - sum(weights)) contributes zero. An all-cash
    portfolio therefore scores exactly 0 — the agent is only paid for
    forward returns it actually holds."""
    scores = asset_forward_scores(prices, t)
    w = np.asarray(weights, dtype=float)
    if w.shape[0] != scores.shape[0]:
        raise ValueError(
            f"weights length {w.shape[0]} != n_assets {scores.shape[0]}")
    return float(np.clip(float(w @ scores), -COMPONENT_CLIP, COMPONENT_CLIP))


def drawdown_penalty(equity_curve: np.ndarray) -> tuple[float, bool]:
    """g(DD): convex penalty with ladder jumps. Returns (penalty, terminal).

    The -20% rung terminates the episode: the returned component stays
    bounded like any other; the episode-level DD_TERMINAL_PENALTY is applied
    by step_reward, not here. The reward never pays for market-order
    liquidation at the bottom (Quant Quake lesson).
    """
    eq = np.asarray(equity_curve, dtype=float)
    peak = np.maximum.accumulate(eq)
    dd = float(1.0 - eq[-1] / peak[-1])
    g = (dd / DD_LADDER[2]) ** 2 * DD_KAPPA
    if dd >= DD_LADDER[0]:
        g += 0.5
    if dd >= DD_LADDER[1]:
        g += 1.0
    return float(np.clip(g, 0.0, COMPONENT_CLIP)), dd >= DD_LADDER[2]


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

    Returns (penalty, hard_rule_or_zero). penalty is the UNSCALED over-cap
    ratio (v1.1 / review R-2: lambda is applied once, in step_reward).
    ADDING exposure under ELEVATED/SHOCK trips the hard rule (red line R5).
    """
    cap = EVENT_EXPOSURE_CAP[state]
    over = max(0.0, gross_exposure - cap)
    penalty = float(np.clip(over / max(cap, 1e-8), 0.0, COMPONENT_CLIP))
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
    """One evaluation step. weights_* are projected onto the simplex first."""
    w = {**DEFAULT_WEIGHTS, **(w or {})}
    weights_prev = project_to_simplex_with_cash(weights_prev)
    weights_new = project_to_simplex_with_cash(weights_new)

    r_vol = portfolio_return_score(prices, t, weights_new)
    g_dd, terminal = drawdown_penalty(equity_curve)
    turn = float(np.abs(weights_new - weights_prev).sum())
    cost = transaction_cost(turn * book_value, book_value, sigma_daily, adv_value)
    ev_pen, hard = event_penalty(event_state, float(weights_new.sum()),
                                 float(weights_prev.sum()))
    lam_e = EVENT_LAMBDA[event_state]
    turn_pen = turnover_penalty(turn)

    total = (w["w_r"] * r_vol - w["w_d"] * g_dd - w["w_c"] * cost
             - lam_e * ev_pen - turn_pen + hard)
    if terminal:
        total = DD_TERMINAL_PENALTY
    return RewardResult(total=float(total), terminal=terminal, parts={
        "r_vol": r_vol, "g_dd": g_dd, "cost": cost, "event": ev_pen,
        "hard": hard, "turnover": turn, "turnover_pen": turn_pen,
    })


# ---------------------------------------------------------------- smoke test
# The real referee is test_reward_invariants.py — spec-derived, written by a
# non-implementer (belief B10: same-source self-checks inherit blind spots).

def _smoke():
    rng = np.random.default_rng(7)
    n, k = 120, 3
    prices = 100 * np.exp(np.cumsum(rng.normal(0.0004, 0.012, (n, k)), axis=0))
    full = step_reward(prices, 60, np.array([1.0, 1.0]),
                       np.full(k, 1 / k), np.full(k, 1 / k),
                       "NEUTRAL", 0.02, 0.10)
    empty = step_reward(prices, 60, np.array([1.0, 1.0]),
                        np.zeros(k), np.zeros(k), "NEUTRAL", 0.02, 0.10)
    print(f"smoke: full={full.total:+.4f} empty={empty.total:+.4f} "
          f"(empty r_vol must be 0: {empty.parts['r_vol']})")
    assert empty.parts["r_vol"] == 0.0
    assert full.total != empty.total
    print("smoke ok — run test_reward_invariants.py for the referee suite")


if __name__ == "__main__":
    _smoke()
