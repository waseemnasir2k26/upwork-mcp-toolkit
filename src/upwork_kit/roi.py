"""Connects ROI: is this bid worth its Connects?

IMPORTANT: win probability here is a HEURISTIC PRIOR, not a measured number.
Replace it with your own history via `win_probability` (or `my_win_rate`).
The structure of the answer (cost vs value vs break-even odds) is what makes
this useful; the prior only fills the gap when you have no history.

Connects price default: US$0.15 each (what Upwork has charged for Connects;
configurable because Upwork can change it).
"""
from __future__ import annotations

from typing import Any, Optional

from .rates import DEFAULT_FEE_PERCENT, gross_to_net

DEFAULT_CONNECT_PRICE = 0.15


def prior_win_probability(proposal_count: int, quality_score: Optional[float] = None) -> float:
    p0 = 1.0 / (max(0, proposal_count) + 4)
    mult = 1.0 if quality_score is None else 0.5 + max(0.0, min(100.0, quality_score)) / 100.0
    return round(min(0.6, p0 * mult), 4)


def connects_roi(connects_cost: int, project_value_usd: float, proposal_count: int = 0,
                 quality_score: Optional[float] = None, win_probability: Optional[float] = None,
                 my_win_rate: Optional[float] = None, fee_percent: float = DEFAULT_FEE_PERCENT,
                 connect_price_usd: float = DEFAULT_CONNECT_PRICE, delivery_cost_usd: float = 0.0,
                 boost_connects: int = 0) -> dict[str, Any]:
    if connects_cost < 0 or boost_connects < 0:
        raise ValueError("connects must be >= 0")
    if project_value_usd < 0 or delivery_cost_usd < 0 or connect_price_usd < 0:
        raise ValueError("money inputs must be >= 0")
    for name, v in (("win_probability", win_probability), ("my_win_rate", my_win_rate)):
        if v is not None and not 0 <= v <= 1:
            raise ValueError(f"{name} must be between 0 and 1")

    if win_probability is not None:
        p, p_src = win_probability, "supplied win_probability"
    elif my_win_rate is not None:
        p, p_src = my_win_rate, "your historical win rate"
    else:
        p, p_src = prior_win_probability(proposal_count, quality_score), "heuristic prior (not measured)"

    cost = round((connects_cost + boost_connects) * connect_price_usd, 2)
    net_value = gross_to_net(project_value_usd, fee_percent)
    payoff = max(0.0, net_value - delivery_cost_usd)
    ev = round(p * payoff - cost, 2)
    breakeven = round(cost / payoff, 4) if payoff > 0 else None

    if payoff <= 0:
        rec, why = "skip", "Net payoff after fee and delivery cost is zero."
    elif ev >= cost:
        rec, why = "bid", "Expected return is at least 2x the Connects spend."
    elif ev > 0:
        rec, why = "marginal", "Positive but thin: bid only if the client signals are strong."
    else:
        rec, why = "skip", "Expected value is negative at this win probability."
    return {"recommendation": rec, "reason": why, "connects_spent": connects_cost + boost_connects,
            "connects_cost_usd": cost, "win_probability": p, "win_probability_source": p_src,
            "net_payoff_usd": round(payoff, 2), "expected_value_usd": ev,
            "break_even_win_probability": breakeven, "fee_percent": fee_percent}
