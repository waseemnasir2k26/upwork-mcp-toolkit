"""Fee-aware rate maths.

Fee model (checked 2026-10-12 against Upwork's help article "Learn about the
Freelancer Service Fee",
https://support.upwork.com/hc/en-us/articles/211062538-Fees-and-charges-for-freelancers):
the freelancer service fee "ranges from 0% to 15% per contract", it is shown
to you on the proposal/offer, and it is locked once the proposal/offer/contract
is sent. Upwork's own worked examples use 10%; Enterprise clients are typically
10%. There is no single fee to hardcode, so the fee is an INPUT here. The
default (10%) is an assumption, not a promise - read the figure Upwork shows
on your proposal and pass it in.
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Optional

DEFAULT_FEE_PERCENT = 10.0
MAX_FEE_PERCENT = 30.0  # sanity ceiling; Upwork's stated range is 0-15
FEE_SOURCE = "https://support.upwork.com/hc/en-us/articles/211062538-Fees-and-charges-for-freelancers"


def _check_fee(fee_percent: float) -> float:
    if not 0 <= fee_percent <= MAX_FEE_PERCENT:
        raise ValueError(f"fee_percent must be between 0 and {MAX_FEE_PERCENT:g} (Upwork states 0-15 per contract)")
    return fee_percent


def _cents(x: float) -> float:
    return float(Decimal(str(x)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def net_to_gross(target_net: float, fee_percent: float = DEFAULT_FEE_PERCENT) -> float:
    """What to charge the client to keep `target_net` after the fee."""
    f = _check_fee(fee_percent) / 100
    return _cents(target_net / (1 - f))


def gross_to_net(gross: float, fee_percent: float = DEFAULT_FEE_PERCENT) -> float:
    f = _check_fee(fee_percent) / 100
    return _cents(gross * (1 - f))


def calculate(mode: str, amount: float, fee_percent: float = DEFAULT_FEE_PERCENT,
              hours: Optional[float] = None, connects_cost_usd: float = 0.0,
              hours_per_week: Optional[float] = None, weeks: Optional[float] = None) -> dict[str, Any]:
    """mode: 'net_to_gross' | 'gross_to_net' | 'fixed'.

    - net_to_gross: amount = hourly rate you want to take home -> rate to bill.
    - gross_to_net: amount = hourly rate you bill -> what you keep.
    - fixed: amount = fixed price; with `hours` returns the effective net hourly
      after fee and the Connects spent winning it.
    """
    fee = _check_fee(fee_percent)
    if amount < 0:
        raise ValueError("amount must be >= 0")
    out: dict[str, Any] = {"mode": mode, "fee_percent": fee, "fee_source": FEE_SOURCE,
                           "fee_note": "Upwork states the fee is 0-15% per contract and is shown on your proposal; 10% is only the default here."}
    if mode == "net_to_gross":
        gross = net_to_gross(amount, fee)
        out.update(target_net_hourly=amount, bill_hourly=gross, fee_per_hour=_cents(gross - amount))
        rate_net = amount
    elif mode == "gross_to_net":
        net = gross_to_net(amount, fee)
        out.update(bill_hourly=amount, net_hourly=net, fee_per_hour=_cents(amount - net))
        rate_net = net
    elif mode == "fixed":
        net_total = gross_to_net(amount, fee)
        out.update(project_price=amount, fee_total=_cents(amount - net_total), net_total=net_total)
        net_after_connects = _cents(net_total - connects_cost_usd)
        out["connects_cost_usd"] = connects_cost_usd
        out["net_after_connects"] = net_after_connects
        if hours:
            if hours <= 0:
                raise ValueError("hours must be > 0")
            out["effective_net_hourly"] = _cents(net_after_connects / hours)
        rate_net = out.get("effective_net_hourly")
    else:
        raise ValueError("mode must be one of: net_to_gross, gross_to_net, fixed")
    if rate_net is not None and hours_per_week and weeks:
        out["projected_net_total"] = _cents(rate_net * hours_per_week * weeks)
    return out
