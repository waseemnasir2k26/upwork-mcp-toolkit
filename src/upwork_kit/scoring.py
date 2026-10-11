"""0-100 job vetting rubric with reasons. Offline, deterministic.

Pipeline: KILL gates first (hard stops), then a 100-point score, then red-flag
penalty. Unknown signals get roughly half points and are listed under
`unknown`, so a missing field never silently reads as good or bad.

Points: budget 20, client history 30 (hire rate 10, spend/hire 8, rating 7,
reviews 5), payment verified 10, proposal count 15, scope clarity 15,
freshness 10. All thresholds live in ScoreConfig; none are Upwork rules, they
are a freelancer's own vetting taste.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from . import flags as flagmod
from .models import Job


class ScoreConfig(BaseModel):
    bid_threshold: int = Field(default=65, ge=0, le=100)
    min_hire_rate: float = Field(default=0.40, ge=0, le=1)
    hire_gate_min_posted: int = Field(default=5, ge=1)
    min_avg_hourly_paid: float = Field(default=25.0, ge=0)
    min_spend_per_hire: float = Field(default=100.0, ge=0)
    min_reviews: int = Field(default=2, ge=0)
    min_rating: float = Field(default=4.4, ge=0, le=5)
    stale_after_hours: float = Field(default=96.0, gt=0)
    liveness_confirmed: bool = False  # set True after you checked the posting is still open
    full_points_fixed_budget: float = Field(default=500.0, gt=0)
    full_points_hourly: float = Field(default=35.0, gt=0)
    excluded_countries: list[str] = Field(default_factory=list)


def _row(cat: str, pts: float, mx: float, why: str) -> dict[str, Any]:
    return {"category": cat, "points": round(pts, 1), "max": mx, "reason": why}


def _kill_gates(job: Job, cfg: ScoreConfig, age: Optional[float]) -> list[dict[str, str]]:
    c, gates = job.client, []

    def g(gid: str, why: str) -> None:
        gates.append({"gate": gid, "reason": why})

    if c.country and c.country.strip().lower() in {x.strip().lower() for x in cfg.excluded_countries}:
        g("excluded_country", f"Client country {c.country} is on your exclusion list.")
    if c.hire_rate is not None and (c.total_posted_jobs or 0) >= cfg.hire_gate_min_posted and c.hire_rate < cfg.min_hire_rate:
        g("low_hire_rate", f"Hire rate {c.hire_rate:.0%} over {c.total_posted_jobs} posted jobs is under {cfg.min_hire_rate:.0%}.")
    if job.job_type == "hourly" and c.avg_hourly is not None and c.avg_hourly < cfg.min_avg_hourly_paid:
        g("low_avg_hourly_paid", f"Client's average paid rate ${c.avg_hourly:.2f}/hr is under ${cfg.min_avg_hourly_paid:g}/hr.")
    if job.job_type != "hourly" and c.spend_per_hire is not None and c.spend_per_hire < cfg.min_spend_per_hire:
        g("low_spend_per_hire", f"Average spend per hire ${c.spend_per_hire:.0f} is under ${cfg.min_spend_per_hire:g}.")
    if job.total_hired:
        g("already_hired", f"Posting already shows {job.total_hired} hire(s).")
    if age is not None and age > cfg.stale_after_hours and not cfg.liveness_confirmed:
        g("stale_unverified", f"Posted {age / 24:.1f} days ago; confirm it is still open then re-run with liveness_confirmed=true.")
    if c.payment_verified is False:
        g("payment_unverified", "Client payment method is not verified.")
    if c.total_reviews is not None and c.total_reviews < cfg.min_reviews and (c.total_spent or 0) > 0:
        g("unproven_client", f"Only {c.total_reviews} review(s) despite spend.")
    if c.rating is not None and c.rating < cfg.min_rating and (c.total_reviews or 0) >= 1:
        g("low_client_rating", f"Client rating {c.rating} is under {cfg.min_rating}.")
    return gates


_VAGUE = re.compile(r"\b(simple|quick|easy|something like|asap|just need|small task)\b", re.I)
_TIMELINE = re.compile(r"\b(deadline|timeline|by (monday|tuesday|wednesday|thursday|friday|the end)|within \d+|\d+\s*(day|week|month)s?|milestone)\b", re.I)
_OUTCOME = re.compile(r"\b(build|integrate|deliver|migrate|set up|connect|automate|fix|audit|design|implement|must|need|require)\b", re.I)
_BULLET = re.compile(r"(^|\n)\s*(?:[-*•]|\d+[.)])\s+\S")


def _scope(job: Job) -> tuple[float, str]:
    d = job.description or ""
    words = len(d.split())
    pts, notes = 0.0, []
    if words >= 80: pts += 5; notes.append(f"{words} words")
    elif words >= 40: pts += 3; notes.append(f"{words} words (short)")
    elif words >= 20: pts += 1; notes.append(f"{words} words (very short)")
    else: notes.append(f"only {words} words")
    if _BULLET.search(d) or d.count("\n") >= 3: pts += 3; notes.append("structured")
    if _TIMELINE.search(d): pts += 2; notes.append("timeline mentioned")
    if len(job.skills) >= 2 or len(re.findall(r"\b[A-Z][A-Za-z0-9.+#-]{2,}\b", d)) >= 4: pts += 3; notes.append("named tools/skills")
    if _OUTCOME.search(d): pts += 2; notes.append("outcome verbs")
    vague = len(_VAGUE.findall(d))
    if vague: pts -= min(3, vague); notes.append(f"{vague} vague word(s)")
    return max(0.0, min(15.0, pts)), ", ".join(notes)


def score_job(job_data: dict[str, Any] | Job, config: Optional[ScoreConfig] = None,
              now: Optional[datetime] = None) -> dict[str, Any]:
    job = job_data if isinstance(job_data, Job) else Job.model_validate(job_data)
    cfg = config or ScoreConfig()
    c = job.client
    age = job.age_hours(now)
    rows, unknown = [], []

    # budget (20)
    if job.job_type == "hourly" and (job.hourly_min is not None or job.hourly_max is not None):
        lo, hi = job.hourly_min or job.hourly_max, job.hourly_max or job.hourly_min
        mid = (lo + hi) / 2
        r = mid / cfg.full_points_hourly
        pts = 20 if r >= 1 else 12 if r >= 0.7 else 6 if r >= 0.4 else 2
        rows.append(_row("budget", pts, 20, f"hourly ${lo:g}-${hi:g}/hr, midpoint ${mid:g} vs ${cfg.full_points_hourly:g} full-points rate"))
    elif job.fixed_budget is not None:
        b = job.fixed_budget
        pts = 20 if b >= 2 * cfg.full_points_fixed_budget else 16 if b >= cfg.full_points_fixed_budget else 10 if b >= 250 else 5 if b >= 100 else 0
        rows.append(_row("budget", pts, 20, f"fixed ${b:,.0f} vs ${cfg.full_points_fixed_budget:,.0f} full-points budget"))
    else:
        rows.append(_row("budget", 10, 20, "no budget stated (neutral)")); unknown.append("budget")

    # client history (30)
    if c.hire_rate is not None:
        pts = 10 if c.hire_rate >= 0.6 else 6 if c.hire_rate >= 0.4 else 2
        rows.append(_row("client.hire_rate", pts, 10, f"hire rate {c.hire_rate:.0%}"))
    else:
        rows.append(_row("client.hire_rate", 5, 10, "hire rate unknown (neutral)")); unknown.append("client.hire_rate")
    sph = c.spend_per_hire
    if sph is not None:
        pts = 8 if sph >= 500 else 5 if sph >= 200 else 3 if sph >= 100 else 0
        rows.append(_row("client.spend_per_hire", pts, 8, f"${sph:,.0f} average spend per hire"))
    else:
        rows.append(_row("client.spend_per_hire", 4, 8, "spend per hire unknown (neutral)")); unknown.append("client.spend_per_hire")
    if c.rating is not None:
        pts = 7 if c.rating >= 4.8 else 5 if c.rating >= 4.5 else 3 if c.rating >= cfg.min_rating else 0
        rows.append(_row("client.rating", pts, 7, f"rating {c.rating}"))
    else:
        rows.append(_row("client.rating", 3, 7, "rating unknown (neutral)")); unknown.append("client.rating")
    if c.total_reviews is not None:
        pts = 5 if c.total_reviews >= 10 else 3 if c.total_reviews >= 3 else 1
        rows.append(_row("client.reviews", pts, 5, f"{c.total_reviews} reviews"))
    else:
        rows.append(_row("client.reviews", 2, 5, "review count unknown (neutral)")); unknown.append("client.reviews")

    # payment (10)
    if c.payment_verified is True: rows.append(_row("payment_verified", 10, 10, "payment method verified"))
    elif c.payment_verified is False: rows.append(_row("payment_verified", 0, 10, "payment NOT verified"))
    else: rows.append(_row("payment_verified", 5, 10, "payment verification unknown (neutral)")); unknown.append("payment_verified")

    # proposals (15)
    n = job.proposal_count
    pts = 15 if n <= 5 else 10 if n <= 10 else 4 if n <= 15 else 0
    rows.append(_row("proposal_count", pts, 15, f"{n} proposals" + (" (absent in feed = 0)" if n == 0 else "")))

    # scope (15)
    sp, why = _scope(job)
    rows.append(_row("scope_clarity", sp, 15, why))

    # freshness (10)
    if age is None:
        rows.append(_row("freshness", 5, 10, "posting time unknown (neutral)")); unknown.append("created_date")
    else:
        pts = 10 if age <= 24 else 8 if age <= 48 else 4 if age <= 96 else 0
        rows.append(_row("freshness", pts, 10, f"posted {age:.0f}h ago"))

    base = sum(r["points"] for r in rows)
    fl = flagmod.scan(f"{job.title}\n{job.description}", job.fixed_budget)
    pen = flagmod.penalty(fl)
    score = max(0, round(base - pen))
    gates = _kill_gates(job, cfg, age)
    for f in fl:
        if f["kill"]:
            gates.append({"gate": f["id"], "reason": f["message"]})

    if gates:
        verdict = "kill"
    elif score >= cfg.bid_threshold:
        verdict = "bid"
    elif score >= cfg.bid_threshold - 15:
        verdict = "maybe"
    else:
        verdict = "skip"
    return {"score": score, "verdict": verdict, "bid_threshold": cfg.bid_threshold,
            "kill_gates": gates, "breakdown": rows, "red_flags": fl, "red_flag_penalty": pen,
            "unknown": unknown, "title": job.title}


def render_text(result: dict[str, Any]) -> str:
    lines = [f"{result['verdict'].upper()}  score {result['score']}/100 (bid at >= {result['bid_threshold']})  {result['title']}".rstrip()]
    for g in result["kill_gates"]:
        lines.append(f"  KILL  {g['gate']}: {g['reason']}")
    for r in result["breakdown"]:
        lines.append(f"  {r['points']:>5g}/{r['max']:<3g} {r['category']:<22} {r['reason']}")
    for f in result["red_flags"]:
        lines.append(f"  FLAG  [{f['severity']}] {f['id']}: {f['message']}")
    if result["red_flag_penalty"]:
        lines.append(f"  -{result['red_flag_penalty']} red-flag penalty")
    return "\n".join(lines)
