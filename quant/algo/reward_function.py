"""Reward function v1.2 — implements quant/algo/reward-function.md (spec S1-S6).

v1.2 (2026-07-12, governance round 2) — red-team-driven spec amendments:
  S1  Same-window vol normalization: f(r_vol) divides each horizon's forward
      return by realized vol over THAT forward window. Identical forward
      paths score identically regardless of trailing calm/noise (kills the
      4x calm-before-storm arbitrage, red team H1).
  S2  Dwell-escalating event penalty: holding over-cap exposure in
      ELEVATED/SHOCK compounds x(1+0.5(k-1)), capped x4 (H2).
  S3  Concentration term: in non-NEUTRAL states, HHI above 0.5 adds
      clip((HHI-0.5)*2,0,1)*(gross/cap) to the event ratio (H3).
  S4  DD_TERMINAL_PENALTY = -25 — below any reachable non-terminal total,
      so the penalty surface is monotone in drawdown (H5).
  S5  RewardEngine holds the episode high-water mark (truncated equity
      feeds cannot erase drawdown memory, H6) and enforces adv/book unit
      sanity (ratio within [1e-4, 1e6], H4). Engine is canonical for
      episodes; functional API remains for single-step scoring.
  S6  mode="train" scores only the h=3 horizon (no overlapping-window
      double counting at step >= 3, G-3); mode="eval" keeps 3/7/15.

Referee: test_reward_invariants.py v1.2 (132 assertions, spec-derived by a
non-implementer, mutation-tested). Implementer may not edit the suite; spec
disputes go back to the spec layer (belief B10).

Paper-forward experiments only. This module never touches an execution API.
"""

from dataclasses import dataclass, field
import numpy as np

# ---------------------------------------------------------------- config

HORIZONS = (3, 7, 15)           # forward-return horizons, days (Trading-R1, 3-0)
HORIZON_WEIGHTS = (0.3, 0.5, 0.2)
VOL_WINDOW = 20                 # minimum history required before scoring
ASYMMETRY = 1.5                 # negative returns scaled 1.5x before scoring
COMPONENT_CLIP = 3.0            # scoring components bounded to [-3, 3]

DD_LADDER = (0.10, 0.15, 0.20)  # docs/risk-rules ladder: freeze / halve / force-half
DD_KAPPA = 2.0                  # convexity scale for g(DD)
DD_TERMINAL_PENALTY = -25.0     # S4: below any non-terminal total (was -10)

FIXED_FEE_BPS = 1.0             # CONSERVATIVE_PLACEHOLDER round-trip fixed fee floor
SPREAD_BPS_FLOOR = 2.0          # CONSERVATIVE_PLACEHOLDER
IMPACT_COEF = 1.0               # eta in eta*sigma*sqrt(x/V), Almgren-Chriss (3-0)

TURNOVER_CAP = 0.20             # max fraction of book traded per step
TURNOVER_PENALTY = 1.0          # per unit of excess turnover

EVENT_EXPOSURE_CAP = {"NEUTRAL": 1.0, "ELEVATED": 0.75, "SHOCK": 0.50}
EVENT_LAMBDA = {"NEUTRAL": 0.0, "ELEVATED": 1.0, "SHOCK": 2.0}
HARD_RULE_PENALTY = -5.0        # adding exposure under ELEVATED/SHOCK

DWELL_STEP = 0.5                # S2: multiplier 1 + DWELL_STEP*(k-1)
DWELL_MULT_CAP = 4.0
HHI_KNEE = 0.5                  # S3: concentration penalty starts here
ADV_BOOK_RATIO_BAND = (1e-4, 1e6)  # S5: engine-level unit sanity band

DEFAULT_WEIGHTS = {"w_r": 1.0, "w_d": 1.0, "w_c": 1.0}
# Weight grids are trials: every (w_r, w_d, w_c, lambda_e) combination searched
# must increment trial count N for the DSR report (backtest protocol v1.1).


# ---------------------------------------------------------------- action space

def project_to_simplex_with_cash(raw: np.ndarray) -> np.ndarray:
    """Map arbitrary proposals into {w >= 0, sum(w) <= 1}. Leverage/shorts
    cannot exist after this projection — structural exclusion, not a penalty."""
    w = np.clip(np.atleast_1d(np.asarray(raw, dtype=float)), 0.0, None)
    total = w.sum()
    if total > 1.0:
        w = w / total
    return w


# ---------------------------------------------------------------- components

def _as_2d(prices: np.ndarray) -> np.ndarray:
    p = np.asarray(prices, dtype=float)
    return p[:, None] if p.ndim == 1 else p


def asset_forward_scores(prices: np.ndarray, t: int, mode: str = "eval") -> np.ndarray:
    """Per-asset multi-horizon forward returns / SAME-WINDOW realized vol (S1).

    prices: (T,) or (T, n). Returns (n,) scores clipped to +-COMPONENT_CLIP.
    mode="eval": horizons 3/7/15 weighted 0.3/0.5/0.2.
    mode="train": h=3 only (S6 — no overlap for step >= 3).
    Requires t >= VOL_WINDOW (history sanity) and t + max horizon < len.
    """
    p = _as_2d(prices)
    horizons = ((3, 1.0),) if mode == "train" else tuple(zip(HORIZONS, HORIZON_WEIGHTS))
    hmax = max(h for h, _ in horizons)
    if t < VOL_WINDOW:
        raise ValueError(f"t={t} < VOL_WINDOW={VOL_WINDOW}: refusing to score "
                         "with insufficient history (redteam M3)")
    if t + hmax >= p.shape[0]:
        raise ValueError("not enough forward data: need t + max(horizon) < len(prices)")
    used = p[: t + hmax + 1]
    if not np.all(np.isfinite(used)) or np.any(used <= 0):
        raise ValueError("prices must be finite and strictly positive "
                         "(zero/negative prices poison log-returns silently — redteam M2)")
    scores = np.zeros(p.shape[1])
    for h, wh in horizons:
        fwd = p[t + h] / p[t] - 1.0
        # S1: realized vol over the SAME forward window [t, t+h]
        vol_fwd = np.diff(np.log(p[t: t + h + 1]), axis=0).std(axis=0)
        vol_fwd = np.where(vol_fwd < 1e-8, 1e-8, vol_fwd)
        z = fwd / vol_fwd / np.sqrt(h)
        z = np.where(z < 0, z * ASYMMETRY, z)
        scores += wh * z
    return np.clip(scores, -COMPONENT_CLIP, COMPONENT_CLIP)


def portfolio_return_score(prices: np.ndarray, t: int, weights: np.ndarray,
                           mode: str = "eval") -> float:
    """f(r_vol), portfolio-coupled: weights . asset scores; cash scores 0."""
    scores = asset_forward_scores(prices, t, mode=mode)
    w = np.atleast_1d(np.asarray(weights, dtype=float))
    if w.shape[0] != scores.shape[0]:
        raise ValueError(
            f"weights length {w.shape[0]} != n_assets {scores.shape[0]}")
    return float(np.clip(float(w @ scores), -COMPONENT_CLIP, COMPONENT_CLIP))


def drawdown_penalty(equity_curve: np.ndarray,
                     prior_peak: float = None) -> tuple[float, bool]:
    """g(DD): convex penalty with ladder jumps. Returns (penalty, terminal).

    The bounded component is returned here; the episode-level
    DD_TERMINAL_PENALTY is applied by the assembler. prior_peak lets callers
    (and the engine) carry the episode high-water mark (redteam H6).
    """
    eq = np.asarray(equity_curve, dtype=float)
    if eq.size == 0:
        raise ValueError("equity_curve must be non-empty (redteam L1)")
    peak = np.maximum.accumulate(eq)
    hwm = peak[-1] if prior_peak is None else max(float(prior_peak), float(peak[-1]))
    dd = float(1.0 - eq[-1] / hwm)
    g = (dd / DD_LADDER[2]) ** 2 * DD_KAPPA
    if dd >= DD_LADDER[0]:
        g += 0.5
    if dd >= DD_LADDER[1]:
        g += 1.0
    return float(np.clip(g, 0.0, COMPONENT_CLIP)), dd >= DD_LADDER[2]


def transaction_cost(trade_value: float, book_value: float,
                     sigma_daily: float, adv_value: float) -> float:
    """Cost_t: fixed fee + spread floor + sqrt-RATE impact sigma*sqrt(x/V).

    Sublinear in trade size per spec ("conservative even for small size").
    Unit-band enforcement lives in the engine (J15), not here.
    """
    if book_value <= 0:
        raise ValueError("book_value must be > 0 (redteam M1)")
    if adv_value <= 0:
        raise ValueError("adv_value must be > 0 (redteam M1)")
    if sigma_daily < 0:
        raise ValueError("sigma_daily must be >= 0 (redteam M1)")
    if trade_value <= 0:
        return 0.0
    frac = trade_value / book_value
    fee = (FIXED_FEE_BPS + SPREAD_BPS_FLOOR) * 1e-4 * frac
    impact = IMPACT_COEF * sigma_daily * np.sqrt(trade_value / adv_value)
    return float(np.clip(fee + impact, 0.0, COMPONENT_CLIP))


def hhi_of(weights: np.ndarray) -> float:
    """Concentration: sum((w_i/gross)^2); 0 for an all-cash book (S3)."""
    w = np.clip(np.atleast_1d(np.asarray(weights, dtype=float)), 0.0, None)
    gross = w.sum()
    if gross <= 0:
        return 0.0
    x = w / gross
    return float((x * x).sum())


def event_penalty(state: str, gross_exposure: float, prev_gross_exposure: float,
                  dwell_k: int = 1, hhi: float = 0.0) -> tuple[float, float]:
    """EventPenalty_t + HardRules for the black-swan state machine (S2/S3).

    ratio = (over/cap) * min(1 + 0.5*(k-1), 4)          [dwell escalation]
          + [state != NEUTRAL] clip((HHI-0.5)*2, 0, 1) * (gross/cap)
    Returned pre-lambda, post-clip (J11); lambda applies once at assembly.
    """
    cap = EVENT_EXPOSURE_CAP[state]
    over = max(0.0, gross_exposure - cap)
    mult = min(1.0 + DWELL_STEP * (max(int(dwell_k), 1) - 1), DWELL_MULT_CAP)
    ratio = (over / max(cap, 1e-8)) * mult
    if state != "NEUTRAL":
        conc = float(np.clip((hhi - HHI_KNEE) * 2.0, 0.0, 1.0))
        ratio += conc * (gross_exposure / max(cap, 1e-8))
    penalty = float(np.clip(ratio, 0.0, COMPONENT_CLIP))
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


def _assemble(prices, t, equity_curve, weights_prev, weights_new, event_state,
              sigma_daily, adv_value, book_value, w, prior_peak, dwell_k, mode):
    w = {**DEFAULT_WEIGHTS, **(w or {})}
    weights_prev = project_to_simplex_with_cash(weights_prev)
    weights_new = project_to_simplex_with_cash(weights_new)

    r_vol = portfolio_return_score(prices, t, weights_new, mode=mode)
    g_dd, terminal = drawdown_penalty(equity_curve, prior_peak=prior_peak)
    turn = float(np.abs(weights_new - weights_prev).sum())
    cost = transaction_cost(turn * book_value, book_value, sigma_daily, adv_value)
    ev_pen, hard = event_penalty(event_state, float(weights_new.sum()),
                                 float(weights_prev.sum()),
                                 dwell_k=dwell_k, hhi=hhi_of(weights_new))
    lam_e = EVENT_LAMBDA[event_state]
    turn_pen = turnover_penalty(turn)

    total = (w["w_r"] * r_vol - w["w_d"] * g_dd - w["w_c"] * cost
             - lam_e * ev_pen - turn_pen + hard)
    if terminal:
        total = DD_TERMINAL_PENALTY
    return RewardResult(total=float(total), terminal=terminal, parts={
        "r_vol": r_vol, "g_dd": g_dd, "cost": cost, "event": ev_pen,
        "hard": hard, "turnover": turn_pen, "turnover_raw": turn,
    })


def step_reward(prices: np.ndarray, t: int, equity_curve: np.ndarray,
                weights_prev: np.ndarray, weights_new: np.ndarray,
                event_state: str, sigma_daily: float, adv_value: float,
                book_value: float = 1.0, w: dict = None,
                prior_peak: float = None, mode: str = "eval") -> RewardResult:
    """Single-step functional scoring (dwell defaults to 1 — v1.1 compatible).

    UNIT CONTRACT (redteam H4): adv_value must share book_value's currency
    unit; the RewardEngine enforces the ratio band, this API trusts the
    caller. For episodes, use RewardEngine (drawdown memory, dwell)."""
    return _assemble(prices, t, equity_curve, weights_prev, weights_new,
                     event_state, sigma_daily, adv_value, book_value, w,
                     prior_peak, 1, mode)


class RewardEngine:
    """Canonical episode evaluator (S5): holds the high-water mark and the
    event dwell counter so neither can be erased or reset by the caller."""

    def __init__(self, w: dict = None):
        self.w = w
        self.hwm = None     # episode high-water mark (J18: first point seeds it)
        self.dwell = 0      # consecutive over-cap steps in ELEVATED/SHOCK

    def step(self, prices, t, equity_point: float, weights_prev, weights_new,
             event_state: str, sigma_daily: float, adv_value: float,
             book_value: float = 1.0, mode: str = "eval") -> RewardResult:
        ratio = adv_value / book_value if book_value > 0 else float("inf")
        lo, hi = ADV_BOOK_RATIO_BAND
        if not (lo <= ratio <= hi):
            raise ValueError(
                f"adv/book ratio {ratio:.3g} outside {ADV_BOOK_RATIO_BAND}: "
                "unit mismatch suspected (redteam H4)")
        e = float(equity_point)
        self.hwm = e if self.hwm is None else max(self.hwm, e)

        wn = project_to_simplex_with_cash(weights_new)
        gross = float(wn.sum())
        cap = EVENT_EXPOSURE_CAP[event_state]
        if event_state != "NEUTRAL" and gross > cap:
            self.dwell += 1
        else:
            self.dwell = 0

        return _assemble(prices, t, np.array([e]), weights_prev, weights_new,
                         event_state, sigma_daily, adv_value, book_value,
                         self.w, self.hwm, max(self.dwell, 1), mode)


# ---------------------------------------------------------------- smoke test
# The real referee is test_reward_invariants.py v1.2 (132 assertions).

def _smoke():
    rng = np.random.default_rng(7)
    n, k = 120, 3
    prices = 100 * np.exp(np.cumsum(rng.normal(0.0004, 0.012, (n, k)), axis=0))
    full = step_reward(prices, 60, np.array([1.0]), np.full(k, 1 / k),
                       np.full(k, 1 / k), "NEUTRAL", 0.02, 0.10)
    empty = step_reward(prices, 60, np.array([1.0]), np.zeros(k),
                        np.zeros(k), "NEUTRAL", 0.02, 0.10)
    assert empty.parts["r_vol"] == 0.0 and full.total != empty.total
    eng = RewardEngine()
    r1 = eng.step(prices, 60, 1.0, np.zeros(k), np.full(k, 0.3), "SHOCK", 0.02, 0.10)
    r2 = eng.step(prices, 61, 1.0, np.full(k, 0.3), np.full(k, 0.3), "SHOCK", 0.02, 0.10)
    assert r2.parts["event"] > r1.parts["event"]  # dwell escalation
    print("smoke ok — run test_reward_invariants.py (v1.2, 132 checks)")


if __name__ == "__main__":
    _smoke()
