"""Real MCP client round-trip against the stdio server: initialize, tools/list, tools/call.

Run:  python scripts/smoke_mcp.py
Exit 0 only if every expectation holds. Server stderr is passed through.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parent.parent
EXPECTED = {"score_job", "connects_roi", "proposal_lint", "proposal_outline", "red_flag_scan", "rate_calculator"}


def _payload(res) -> dict:
    sc = getattr(res, "structured_content", None) or getattr(res, "structuredContent", None)
    if sc:
        return sc
    return json.loads(res.content[0].text)


async def run() -> int:
    params = StdioServerParameters(command=sys.executable, args=["-m", "upwork_kit.server"],
                                   env={"PYTHONPATH": str(ROOT / "src"), "PYTHONIOENCODING": "utf-8"})
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            tools = await s.list_tools()
            names = {t.name for t in tools.tools}
            print("tools/list ->", sorted(names))
            assert names == EXPECTED, names

            job = json.loads((ROOT / "examples" / "job_good.json").read_text(encoding="utf-8"))
            ok = await s.call_tool("score_job", {"job": job})
            p = _payload(ok)
            print("score_job(job_good) -> verdict", p["verdict"], "score", p["score"])
            assert not ok.is_error and p["verdict"] in {"bid", "kill", "maybe", "skip"}

            ok = await s.call_tool("rate_calculator", {"mode": "net_to_gross", "amount": 20, "fee_percent": 10})
            p = _payload(ok)
            print("rate_calculator(net_to_gross 20 @10%) -> bill_hourly", p["bill_hourly"])
            assert p["bill_hourly"] == 22.22

            bad = await s.call_tool("rate_calculator", {"mode": "net_to_gross", "amount": 20, "fee_percent": 99})
            print("rate_calculator(fee 99) -> is_error", bad.is_error, "|", bad.content[0].text[:140])
            assert bad.is_error

            bad2 = await s.call_tool("rate_calculator", {"mode": "nonsense", "amount": 1})
            print("rate_calculator(mode=nonsense) -> is_error", bad2.is_error)
            assert bad2.is_error

            bad3 = await s.call_tool("connects_roi", {"connects_cost": "many", "project_value_usd": 100})
            print("connects_roi(connects_cost='many') -> is_error", bad3.is_error)
            assert bad3.is_error

            lint = await s.call_tool("proposal_lint", {"proposal": "Email me at a@b.com or WhatsApp +1 415 555 0100."})
            p = _payload(lint)
            print("proposal_lint(contact details) -> ok", p["ok"], [i["id"] for i in p["issues"]])
            assert p["ok"] is False
    print("SMOKE OK")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(run()))
