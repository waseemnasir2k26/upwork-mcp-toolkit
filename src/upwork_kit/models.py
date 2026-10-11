"""Input models.

Tolerant of the row shape the official Upwork MCP returns for job search
(budget as a string, hourly range as "15.00-38.00/hr" with an EN DASH,
proposal_count absent when 0) and of hand-written JSON. Every field is
optional: an unknown signal is reported as unknown, never guessed.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_NUM = re.compile(r"\d[\d,]*\.?\d*")


def parse_money(value: Any) -> Optional[float]:
    """'$1,000.00' -> 1000.0 ; 1200 -> 1200.0 ; '' / None / junk -> None."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    m = _NUM.search(str(value))
    if not m:
        return None
    try:
        return float(m.group(0).replace(",", ""))
    except ValueError:
        return None


def parse_range(value: Any) -> tuple[Optional[float], Optional[float]]:
    """'15.00–38.00/hr' (EN DASH) or '15-38' -> (15.0, 38.0)."""
    if value is None:
        return None, None
    nums = []
    for n in _NUM.findall(str(value)):
        try:
            nums.append(float(n.replace(",", "")))
        except ValueError:
            continue
    if not nums:
        return None, None
    return (nums[0], nums[-1])


def _pct(v: Any) -> Optional[float]:
    f = parse_money(v)
    if f is None:
        return None
    return f / 100.0 if f > 1.0 else f


class Client(BaseModel):
    model_config = ConfigDict(extra="ignore")
    country: Optional[str] = None
    rating: Optional[float] = Field(default=None, ge=0, le=5)
    total_reviews: Optional[int] = Field(default=None, ge=0)
    total_spent: Optional[float] = Field(default=None, ge=0)
    total_hires: Optional[int] = Field(default=None, ge=0)
    total_posted_jobs: Optional[int] = Field(default=None, ge=0)
    hire_rate: Optional[float] = Field(default=None, ge=0, le=1)
    payment_verified: Optional[bool] = None
    avg_hourly_paid: Optional[float] = Field(default=None, ge=0)
    hours_total: Optional[float] = Field(default=None, ge=0)

    @model_validator(mode="before")
    @classmethod
    def _normalise(cls, d: Any) -> Any:
        if not isinstance(d, dict):
            return d
        d = dict(d)
        for alias, canon in (
            ("jobs_posted", "total_posted_jobs"),
            ("total_jobs_posted", "total_posted_jobs"),
            ("feedback_count", "total_reviews"),
            ("hires", "total_hires"),
            ("avg_hourly_rate", "avg_hourly_paid"),
        ):
            if alias in d and canon not in d:
                d[canon] = d[alias]
        for k in ("total_spent", "avg_hourly_paid", "hours_total"):
            if k in d:
                d[k] = parse_money(d[k])
        for k in ("total_reviews", "total_hires", "total_posted_jobs"):
            if k in d:
                v = parse_money(d[k])
                d[k] = None if v is None else int(v)
        if "hire_rate" in d:
            d["hire_rate"] = _pct(d["hire_rate"])
        if d.get("rating") is not None:
            d["rating"] = parse_money(d["rating"])
        if d.get("payment_verified") is None and "verification_status" in d:
            vs = str(d["verification_status"] or "").strip().lower()
            if vs in ("verified", "payment_verified", "payment verified"):
                d["payment_verified"] = True
            elif vs in ("unverified", "not_verified", "not verified", "payment_unverified"):
                d["payment_verified"] = False
        if d.get("hire_rate") is None and d.get("total_hires") is not None and d.get("total_posted_jobs"):
            d["hire_rate"] = min(1.0, d["total_hires"] / d["total_posted_jobs"])
        return d

    @property
    def spend_per_hire(self) -> Optional[float]:
        if self.total_spent is not None and self.total_hires:
            return self.total_spent / self.total_hires
        return None

    @property
    def avg_hourly(self) -> Optional[float]:
        if self.avg_hourly_paid is not None:
            return self.avg_hourly_paid
        if self.total_spent is not None and self.hours_total:
            return self.total_spent / self.hours_total
        return None


class Job(BaseModel):
    model_config = ConfigDict(extra="ignore")
    title: str = ""
    description: str = ""
    job_type: Optional[str] = None  # "hourly" | "fixed"
    fixed_budget: Optional[float] = Field(default=None, ge=0)
    hourly_min: Optional[float] = Field(default=None, ge=0)
    hourly_max: Optional[float] = Field(default=None, ge=0)
    proposal_count: int = Field(default=0, ge=0)  # the official MCP omits it when 0
    created_date: Optional[datetime] = None
    skills: list[str] = Field(default_factory=list)
    experience_level: Optional[str] = None
    connects_cost: Optional[int] = Field(default=None, ge=0)
    total_hired: Optional[int] = Field(default=None, ge=0)
    client: Client = Field(default_factory=Client)

    @model_validator(mode="before")
    @classmethod
    def _normalise(cls, d: Any) -> Any:
        if not isinstance(d, dict):
            return d
        d = dict(d)
        if not d.get("description") and d.get("description_snippet"):
            d["description"] = d["description_snippet"]
        raw = d.get("budget")
        jt = str(d.get("job_type") or "").lower()
        if raw is not None and "fixed_budget" not in d and "hourly_min" not in d:
            is_hourly = "hour" in jt or "/hr" in str(raw).lower()
            if is_hourly:
                d["hourly_min"], d["hourly_max"] = parse_range(raw)
                d.setdefault("job_type", "hourly")
            else:
                d["fixed_budget"] = parse_money(raw)
                d.setdefault("job_type", "fixed")
        for k in ("fixed_budget", "hourly_min", "hourly_max"):
            if k in d:
                d[k] = parse_money(d[k])
        pc = parse_money(d.get("proposal_count"))
        d["proposal_count"] = 0 if pc is None else int(pc)
        if isinstance(d.get("skills"), str):
            d["skills"] = [s.strip() for s in d["skills"].split(",") if s.strip()]
        if d.get("skills"):
            d["skills"] = [s.get("name", "") if isinstance(s, dict) else str(s) for s in d["skills"]]
        cd = d.get("created_date") or d.get("published_date")
        if isinstance(cd, str):
            try:
                d["created_date"] = datetime.fromisoformat(cd.replace("Z", "+00:00"))
            except ValueError:
                d["created_date"] = None
        elif cd is not None:
            d["created_date"] = cd
        if d.get("job_type"):
            d["job_type"] = "hourly" if "hour" in str(d["job_type"]).lower() else "fixed"
        return d

    @field_validator("created_date")
    @classmethod
    def _tz(cls, v: Optional[datetime]) -> Optional[datetime]:
        if v is not None and v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v

    def age_hours(self, now: Optional[datetime] = None) -> Optional[float]:
        if self.created_date is None:
            return None
        now = now or datetime.now(timezone.utc)
        return max(0.0, (now - self.created_date).total_seconds() / 3600)
