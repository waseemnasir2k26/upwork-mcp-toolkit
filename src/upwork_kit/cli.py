"""`upwork-kit` CLI - same functions as the MCP tools. JSON on stdout."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from typing import Any

from pydantic import ValidationError

from . import flags as flagmod
from . import lint as lintmod
from . import outline as outlinemod
from . import rates, roi, scoring


def _read(path: str) -> str:
    if path == "-":
        return sys.stdin.read()
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _emit(obj: Any) -> None:
    sys.stdout.write(json.dumps(obj, indent=2, ensure_ascii=False, default=str) + "\n")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="upwork-kit", description="Offline Upwork judgment toolkit (companion to the official Upwork MCP).")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("score", help="score a job JSON 0-100")
    s.add_argument("file", help="job JSON file or - for stdin")
    s.add_argument("--bid-threshold", type=int, default=65)
    s.add_argument("--exclude-country", action="append", default=[])
    s.add_argument("--liveness-confirmed", action="store_true")
    s.add_argument("--text", action="store_true", help="human-readable output")
    s.add_argument("--now", help="ISO timestamp to treat as 'now' (reproducible demos/tests)")

    r = sub.add_parser("roi", help="Connects ROI")
    r.add_argument("--connects", type=int, required=True)
    r.add_argument("--value", type=float, required=True, help="project value in USD")
    r.add_argument("--proposals", type=int, default=0)
    r.add_argument("--quality", type=float)
    r.add_argument("--win-probability", type=float)
    r.add_argument("--my-win-rate", type=float)
    r.add_argument("--fee", type=float, default=rates.DEFAULT_FEE_PERCENT)
    r.add_argument("--connect-price", type=float, default=roi.DEFAULT_CONNECT_PRICE)
    r.add_argument("--delivery-cost", type=float, default=0.0)
    r.add_argument("--boost-connects", type=int, default=0)

    l = sub.add_parser("lint", help="lint a proposal text file")
    l.add_argument("file")
    l.add_argument("--job-title", default="")
    l.add_argument("--job-file", help="job description text file for the opening-mirror check")

    o = sub.add_parser("outline", help="proposal outline from a job description file")
    o.add_argument("file")
    o.add_argument("--title", default="")
    o.add_argument("--fixed-budget", type=float)
    o.add_argument("--hourly-rate", type=float)

    f = sub.add_parser("flags", help="red-flag scan a text file")
    f.add_argument("file")
    f.add_argument("--fixed-budget", type=float)

    c = sub.add_parser("rate", help="fee-aware rate calculator")
    c.add_argument("mode", choices=["net_to_gross", "gross_to_net", "fixed"])
    c.add_argument("amount", type=float)
    c.add_argument("--fee", type=float, default=rates.DEFAULT_FEE_PERCENT, help="service fee %% on this contract (Upwork: 0-15)")
    c.add_argument("--hours", type=float)
    c.add_argument("--connects-usd", type=float, default=0.0)
    c.add_argument("--hours-per-week", type=float)
    c.add_argument("--weeks", type=float)

    sub.add_parser("serve", help="run the MCP server over stdio")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.cmd == "serve":
            from .server import main as serve
            serve()
            return 0
        if args.cmd == "score":
            cfg = scoring.ScoreConfig(bid_threshold=args.bid_threshold, excluded_countries=args.exclude_country,
                                      liveness_confirmed=args.liveness_confirmed)
            now = datetime.fromisoformat(args.now.replace("Z", "+00:00")) if args.now else None
            if now is not None and now.tzinfo is None:
                now = now.replace(tzinfo=timezone.utc)
            res = scoring.score_job(json.loads(_read(args.file)), cfg, now)
            if args.text:
                print(scoring.render_text(res))
            else:
                _emit(res)
        elif args.cmd == "roi":
            _emit(roi.connects_roi(args.connects, args.value, args.proposals, args.quality, args.win_probability,
                                   args.my_win_rate, args.fee, args.connect_price, args.delivery_cost, args.boost_connects))
        elif args.cmd == "lint":
            jd = _read(args.job_file) if args.job_file else ""
            res = lintmod.lint(_read(args.file), args.job_title, jd)
            _emit(res)
            return 0 if res["ok"] else 1
        elif args.cmd == "outline":
            _emit(outlinemod.outline(args.title, _read(args.file), args.fixed_budget, args.hourly_rate))
        elif args.cmd == "flags":
            fl = flagmod.scan(_read(args.file), args.fixed_budget)
            _emit({"flags": fl, "count": len(fl), "kill": any(x["kill"] for x in fl), "penalty_points": flagmod.penalty(fl)})
        elif args.cmd == "rate":
            _emit(rates.calculate(args.mode, args.amount, args.fee, args.hours, args.connects_usd, args.hours_per_week, args.weeks))
        return 0
    except (ValueError, ValidationError, OSError, json.JSONDecodeError) as e:
        sys.stderr.write(f"error: {e}\n")
        return 2


if __name__ == "__main__":
    sys.exit(main())
