# Upwork MCP Server Toolkit: score jobs, lint proposals, price with fees (for Claude and the official Upwork MCP)

[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](pyproject.toml)
[![MCP](https://img.shields.io/badge/MCP-server-8A2BE2.svg)](https://modelcontextprotocol.io)

An **Upwork MCP server** that adds the part the official one does not: **judgment**. Upwork now ships its own first-party MCP server (`https://mcp.upwork.com/mcp`) that fetches jobs, reads your profile and drafts proposals. This toolkit runs next to it and tells **Claude** (or Cursor, or any MCP client) whether a job is worth bidding on, whether a draft proposal is ready to send, and what to charge after Upwork's fee. Use it for **Upwork AI proposal** workflows where a human still reads and confirms every proposal.

- **Fully offline.** No network calls, no Upwork login, no tokens, no API keys.
- **No scraping, no auto-apply.** It never touches Upwork. Fetching is the official server's job; submitting stays behind Upwork's draft-confirm step.
- **Also a CLI** (`upwork-kit`) with the same functions.
- MIT licensed. Python 3.11+. Tested against `mcp` 2.3.0.

> Not affiliated with or endorsed by Upwork. "Upwork" is a trademark of its owner.

## 60-second quickstart

```bash
pip install git+https://github.com/waseemnasir2k26/upwork-mcp-toolkit.git

# 1. the official Upwork MCP server (jobs, profile, drafts)
claude mcp add --transport http upwork https://mcp.upwork.com/mcp
#    then in Claude Code: /mcp -> upwork -> Authenticate

# 2. this toolkit (judgment layer, local stdio)
claude mcp add upwork-toolkit -- python -m upwork_kit.server
```

Then ask Claude: _"Search Upwork for n8n automation jobs, score each one, and tell me which are worth the Connects."_

Claude Desktop, Cursor and the "run both together" workflow: [docs/connect-official-upwork-mcp.md](docs/connect-official-upwork-mcp.md).

## Tools

| Tool               | What it does                                                                                                                                                                                                                                                                                                                                                                                                                  |
| ------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `score_job`        | 0-100 vetting score with a per-category breakdown and reasons: budget, client hire rate, spend per hire, rating, reviews, payment verified, proposal count, scope clarity, freshness, red-flag penalty. KILL gates (low hire rate, already hired, stale, unverified payment, "actual price" scams...) override the score. Verdict: `bid` / `maybe` / `skip` / `kill`. Accepts the row shape the official `find_jobs` returns. |
| `connects_roi`     | Should you spend the Connects? Cost in USD, win probability, expected value net of Upwork's fee, and the break-even win probability. Win probability is a heuristic prior unless you pass your own.                                                                                                                                                                                                                           |
| `proposal_lint`    | Word count against a 120-180 sweet spot, opening mirrors the job's key terms, question count, off-platform contact and payment phrases, leftover placeholders, generic openers, AI-filler tells. Score plus per-issue severity.                                                                                                                                                                                               |
| `proposal_outline` | Structured outline from a job description with no LLM: mirror keywords, tools, client instructions to follow literally ("start your proposal with..."), questions to answer, gaps worth asking about, five sections with word budgets and `[FILL: ...]` slots for your real proof.                                                                                                                                            |
| `red_flag_scan`    | Regex catalogue of client red flags: fake budgets, off-platform payment/contact, unpaid test work, credential requests, lowball and urgency language, scope-vs-budget mismatch.                                                                                                                                                                                                                                               |
| `rate_calculator`  | Net-to-gross, gross-to-net and fixed-price effective hourly after the freelancer service fee and Connects spend. The fee is an input.                                                                                                                                                                                                                                                                                         |

Every tool validates its input with a schema and returns a structured MCP error (`isError`) on bad input instead of crashing.

## Real output

Everything below is real output from this repo (`python -m upwork_kit ...`, `--now 2026-10-12T12:00:00Z` pinned so it is reproducible). The example jobs are made-up fixtures in [examples/](examples).

**A good job** (`examples/job_good.json`):

```text
BID  score 100/100 (bid at >= 65)  n8n automation developer to connect our CRM to Slack and invoicing
     20/20  budget                 fixed $1,800 vs $500 full-points budget
     10/10  client.hire_rate       hire rate 82%
      8/8   client.spend_per_hire  $1,323 average spend per hire
      7/7   client.rating          rating 4.9
      5/5   client.reviews         23 reviews
     10/10  payment_verified       payment method verified
     15/15  proposal_count         4 proposals
     15/15  scope_clarity          86 words, structured, timeline mentioned, named tools/skills, outcome verbs
     10/10  freshness              posted 6h ago
```

**A bad job** (`examples/job_bad.json`, first lines):

```text
KILL  score 0/100 (bid at >= 65)  Need full website + app + SEO + logo ASAP cheap
  KILL  low_hire_rate: Hire rate 7% over 60 posted jobs is under 40%.
  KILL  low_spend_per_hire: Average spend per hire $30 is under $100.
  KILL  stale_unverified: Posted 5.1 days ago; confirm it is still open then re-run with liveness_confirmed=true.
  KILL  payment_unverified: Client payment method is not verified.
  KILL  unproven_client: Only 1 review(s) despite spend.
  KILL  low_client_rating: Client rating 3.9 is under 4.4.
  KILL  actual_price: Client says the posted budget is not the real one - a mega-scope for a token price.
  KILL  off_platform_payment: Off-platform payment. Upwork ToS violation and no payment protection.
```

**Fee maths** that matches the example in Upwork's own help article ($20/hr take-home at a 10% fee means billing $22.22):

```text
$ python -m upwork_kit rate net_to_gross 20 --fee 10
  "bill_hourly": 22.22,  "fee_per_hour": 2.22
```

**Connects ROI** for a $1,800 job, 16 Connects, 4 proposals so far, quality score 100:

```text
"recommendation": "bid", "connects_cost_usd": 2.4,
"win_probability": 0.1875, "win_probability_source": "heuristic prior (not measured)",
"expected_value_usd": 301.35
```

Those probabilities come from a simple prior, not from data. Pass `win_probability` or `my_win_rate` (your own history) for numbers you can trust.

**Proposal lint** exits non-zero when a proposal has errors, so it works in a pre-send check: `python -m upwork_kit lint draft.txt --job-title "..." --job-file job.txt`.

## CLI

```bash
upwork-kit score examples/job_good.json --text
upwork-kit roi --connects 16 --value 1800 --proposals 4 --quality 90
upwork-kit lint examples/proposal_ready.txt --job-title "n8n CRM Slack invoicing"
upwork-kit outline job_description.txt --title "n8n CRM Slack"
upwork-kit flags job_description.txt --fixed-budget 100
upwork-kit rate fixed 1000 --fee 10 --hours 20 --connects-usd 2.4
upwork-kit serve          # the MCP server over stdio
```

## Claude Code skills included

[.claude/skills/](.claude/skills) ships three skills that chain the official server and this toolkit: `upwork-job-triage` (search, score, ROI), `upwork-proposal-writer` (outline, draft with your real proof, lint, hand off for human confirm) and `upwork-fee-check`.

## How the score works

Budget 20, client history 30 (hire rate 10, spend per hire 8, rating 7, reviews 5), payment verified 10, proposal count 15, scope clarity 15, freshness 10; red flags subtract up to 20. Unknown fields get neutral points and are listed under `unknown`. All thresholds are in `ScoreConfig`; they are one freelancer's vetting taste, not Upwork rules, and you can change them (`bid_threshold`, `excluded_countries`, `liveness_confirmed` are exposed on the tool).

## FAQ

**Is this allowed by Upwork?**
This toolkit never connects to Upwork, never logs in, never scrapes and never submits anything. It only analyses text you or your agent hands it. The data comes from Upwork's own official MCP server, which Upwork publishes for exactly this purpose. Proposals created through that server are drafted and need your explicit confirmation; keep that on. This is not legal advice: read Upwork's current Terms of Service and the official MCP page (<https://www.upwork.com/ai/mcp>) yourself. I deliberately do not support browser-automation Upwork MCPs or auto-apply, because those are what Upwork's bot policy targets.

**Do I need the official Upwork MCP server?**
It is how you get live jobs and your profile into the agent. The toolkit also works standalone on pasted job JSON or text.

**What does Upwork's fee look like in 2026?**
Upwork's help article "Learn about the Freelancer Service Fee" (checked 2026-10-12) says the freelancer service fee ranges from 0% to 15% per contract, is shown to you on the proposal or offer, and does not change once the contract starts. So the fee is a parameter here; 10% is just the default. Source: <https://support.upwork.com/hc/en-us/articles/211062538-Fees-and-charges-for-freelancers>.

**Will it write my proposal?**
It builds the outline and checks your draft. It leaves `[FILL: ...]` slots for real proof on purpose, and the linter fails a draft that still has one. Proposals that cite shipped work you actually did win more trust than generated filler.

**Does it guarantee more wins or income?**
No. Nothing here is measured against Upwork outcomes. It is a checklist you can run in seconds.

**Which clients does it work with?**
Any MCP client that supports stdio servers: Claude Code, Claude Desktop, Cursor and others.

## Development

```bash
python -m venv .venv && . .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest -q                     # unit tests plus a real MCP stdio client round-trip
python scripts/smoke_mcp.py   # lists tools and calls them through the SDK client
```

stdout is reserved for MCP protocol frames; diagnostics go to stderr.

CI: the GitHub Actions workflow (pytest on Ubuntu and Windows, Python 3.11 and 3.12, plus the MCP smoke test) is in [ci/github-actions-ci.yml](ci/github-actions-ci.yml). Copy it to `.github/workflows/ci.yml` to enable it on your fork.

## See also

- [upwork-job-radar](https://github.com/waseemnasir2k26/upwork-job-radar): scheduled job scoring with Slack alerts (read and alert only).

## Work with SkynetLabs

Built by [Waseem Nasir](https://www.skynetjoe.com/?utm_source=github&utm_medium=readme&utm_campaign=upwork-mcp-toolkit) at SkynetLabs — n8n + AI automation for small businesses.

- Hire on Fiverr: https://www.fiverr.com/agencies/skynetjoellc
- Hire on Upwork: https://www.upwork.com/freelancers/muhammadwaseemnasir
- Book a free call: https://calendly.com/skynetlabs/schedule-a-free-consultation
