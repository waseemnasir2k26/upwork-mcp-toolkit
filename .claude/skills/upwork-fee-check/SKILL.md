---
name: upwork-fee-check
description: Work out what to bid so a target take-home survives Upwork's freelancer service fee, and whether a fixed-price job pays enough per hour after fee and Connects. Use for rate, quote or "is this worth it" questions. Uses upwork-toolkit rate_calculator and connects_roi.
---

# Upwork fee check

1. Ask the user for the fee percentage shown on the proposal or offer. Upwork states the freelancer service fee is 0-15% per contract and shows it before you send; if the user does not know it, use 10% and say it is an assumption.
2. Hourly: `rate_calculator` with `mode=net_to_gross` and their target take-home to get the rate to bill. To see what a client rate nets, use `gross_to_net`.
3. Fixed price: `rate_calculator` with `mode=fixed`, the price, estimated `hours`, and `connects_cost_usd` (Connects cost x price per Connect). Report `effective_net_hourly` and compare it to the user's floor.
4. If they are deciding whether to bid, call `connects_roi` and report the break-even win probability alongside the heuristic EV. State clearly that the prior is not measured data.
5. Never present numbers as Upwork's own beyond the fee range above.
