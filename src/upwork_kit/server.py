"""MCP server (stdio). Offline: no network calls, no Upwork credentials.

stdout carries protocol frames ONLY. Anything diagnostic goes to stderr.
"""
from __future__ import annotations

import sys
from typing import Annotated, Any, Literal, Optional

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import Field, ValidationError

from . import flags as flagmod
from . import lint as lintmod
from . import outline as outlinemod
from . import rates, roi, scoring

mcp = MCPServer(
    "upwork-mcp-toolkit",
    instructions=(
        "Offline judgment layer for Upwork freelancers. Pair it with the official Upwork MCP server "
        "(https://mcp.upwork.com/mcp): the official server fetches jobs and your profile; these tools score, "
        "lint and price. Nothing here talks to Upwork, submits proposals, or needs credentials."
    ),
)


def _fail(e: Exception) -> ToolError:
    if isinstance(e, ValidationError):
        parts = [f"{'.'.join(str(x) for x in err['loc'])}: {err['msg']}" for err in e.errors()[:6]]
        return ToolError("Invalid input - " + "; ".join(parts))
    return ToolError(str(e))


@mcp.tool(description=(
    "Score an Upwork job 0-100 with reasons. Pass the job as returned by the official Upwork MCP find_jobs "
    "(title, description, budget, job_type, proposal_count, created_date, skills, client{...}). Runs KILL gates "
    "(low hire rate, low avg paid, already hired, stale, unverified payment, red-flag kills) then a weighted score. "
    "Verdict: bid | maybe | skip | kill. Unknown fields are reported, not guessed."))
def score_job(
    job: Annotated[dict[str, Any], Field(description="Job object (official-MCP search row shape or the schema in examples/).")],
    bid_threshold: Annotated[int, Field(ge=0, le=100, description="Score needed for a 'bid' verdict.")] = 65,
    excluded_countries: Annotated[Optional[list[str]], Field(description="Client countries you never bid on.")] = None,
    liveness_confirmed: Annotated[bool, Field(description="True once you verified a >4-day-old posting is still open.")] = False,
) -> dict[str, Any]:
    try:
        cfg = scoring.ScoreConfig(bid_threshold=bid_threshold, excluded_countries=excluded_countries or [],
                                  liveness_confirmed=liveness_confirmed)
        return scoring.score_job(job, cfg)
    except Exception as e:  # noqa: BLE001 - convert to structured tool error
        raise _fail(e) from e


@mcp.tool(description=(
    "Should I spend Connects on this bid? Returns cost in USD, win probability (heuristic prior unless you supply your "
    "own), expected value net of Upwork fee, and break-even win probability. Verdict: bid | marginal | skip."))
def connects_roi(
    connects_cost: Annotated[int, Field(ge=0, le=100, description="Connects the proposal costs.")],
    project_value_usd: Annotated[float, Field(ge=0, description="Total contract value you would bill (fixed price, or rate x expected hours).")],
    proposal_count: Annotated[int, Field(ge=0, description="Proposals already submitted.")] = 0,
    quality_score: Annotated[Optional[float], Field(ge=0, le=100, description="score_job result, if you have it.")] = None,
    win_probability: Annotated[Optional[float], Field(ge=0, le=1, description="Your own estimate; overrides the prior.")] = None,
    my_win_rate: Annotated[Optional[float], Field(ge=0, le=1, description="Your historical proposal win rate.")] = None,
    fee_percent: Annotated[float, Field(ge=0, le=30, description="Freelancer service fee on this contract (Upwork: 0-15%, shown on the proposal).")] = rates.DEFAULT_FEE_PERCENT,
    connect_price_usd: Annotated[float, Field(ge=0, description="USD price of one Connect.")] = roi.DEFAULT_CONNECT_PRICE,
    delivery_cost_usd: Annotated[float, Field(ge=0, description="Your direct cost to deliver (subcontractors, tools).")] = 0.0,
    boost_connects: Annotated[int, Field(ge=0, description="Extra Connects spent boosting the proposal.")] = 0,
) -> dict[str, Any]:
    try:
        return roi.connects_roi(connects_cost, project_value_usd, proposal_count, quality_score, win_probability,
                                my_win_rate, fee_percent, connect_price_usd, delivery_cost_usd, boost_connects)
    except Exception as e:  # noqa: BLE001
        raise _fail(e) from e


@mcp.tool(description=(
    "Lint a draft Upwork proposal: word count (120-180 sweet spot), opening mirrors the job's keywords, question count, "
    "off-platform contact/payment phrases (ToS), leftover placeholders, generic openers, AI-filler tells. Returns issues "
    "with severity and a 0-100 score. Pass job_title/job_description to check the mirror."))
def proposal_lint(
    proposal: Annotated[str, Field(min_length=1, max_length=20000, description="The proposal text.")],
    job_title: Annotated[str, Field(max_length=500)] = "",
    job_description: Annotated[str, Field(max_length=20000)] = "",
) -> dict[str, Any]:
    try:
        return lintmod.lint(proposal, job_title, job_description)
    except Exception as e:  # noqa: BLE001
        raise _fail(e) from e


@mcp.tool(description=(
    "Build a structured proposal outline from a job description (no LLM): mirror keywords, tools, client instructions to "
    "follow literally, client questions to answer, gaps worth asking about, and 5 sections with word budgets and "
    "[FILL: ...] slots for your real proof."))
def proposal_outline(
    job_title: Annotated[str, Field(max_length=500)],
    job_description: Annotated[str, Field(min_length=1, max_length=20000)],
    fixed_budget: Annotated[Optional[float], Field(ge=0)] = None,
    hourly_rate: Annotated[Optional[float], Field(ge=0)] = None,
) -> dict[str, Any]:
    try:
        return outlinemod.outline(job_title, job_description, fixed_budget, hourly_rate)
    except Exception as e:  # noqa: BLE001
        raise _fail(e) from e


@mcp.tool(description=(
    "Scan job text for red flags: fake budgets ('actual price'), off-platform payment/contact, unpaid test work, "
    "credential requests, lowball and urgency language, scope-vs-budget mismatch. Each flag has severity, kill (hard stop) and evidence."))
def red_flag_scan(
    text: Annotated[str, Field(min_length=1, max_length=40000, description="Job title + description (or any client message).")],
    fixed_budget: Annotated[Optional[float], Field(ge=0, description="Posted fixed budget, enables the scope/budget check.")] = None,
) -> dict[str, Any]:
    try:
        fl = flagmod.scan(text, fixed_budget)
        return {"flags": fl, "count": len(fl), "kill": any(f["kill"] for f in fl), "penalty_points": flagmod.penalty(fl)}
    except Exception as e:  # noqa: BLE001
        raise _fail(e) from e


@mcp.tool(description=(
    "Fee-aware rate maths. mode=net_to_gross: hourly rate you want to take home -> rate to bill. mode=gross_to_net: "
    "rate you bill -> what you keep. mode=fixed: fixed price (+ optional hours, Connects spent) -> net and effective hourly. "
    "fee_percent is an INPUT: Upwork states the freelancer service fee is 0-15% per contract and shows it on your proposal; "
    "default 10 is an assumption. Source in the result."))
def rate_calculator(
    mode: Literal["net_to_gross", "gross_to_net", "fixed"],
    amount: Annotated[float, Field(ge=0, description="Hourly rate (net_to_gross / gross_to_net) or fixed project price.")],
    fee_percent: Annotated[float, Field(ge=0, le=30, description="Service fee on this contract, in percent.")] = rates.DEFAULT_FEE_PERCENT,
    hours: Annotated[Optional[float], Field(gt=0, description="Estimated hours (fixed mode).")] = None,
    connects_cost_usd: Annotated[float, Field(ge=0)] = 0.0,
    hours_per_week: Annotated[Optional[float], Field(gt=0, le=168)] = None,
    weeks: Annotated[Optional[float], Field(gt=0)] = None,
) -> dict[str, Any]:
    try:
        return rates.calculate(mode, amount, fee_percent, hours, connects_cost_usd, hours_per_week, weeks)
    except Exception as e:  # noqa: BLE001
        raise _fail(e) from e


def main() -> None:
    print("upwork-mcp-toolkit: stdio server starting (6 tools, offline)", file=sys.stderr)
    mcp.run("stdio")


if __name__ == "__main__":
    main()
