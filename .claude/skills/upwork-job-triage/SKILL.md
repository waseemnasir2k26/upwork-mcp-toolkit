---
name: upwork-job-triage
description: Triage Upwork job search results. Use when the user asks to find, vet or shortlist Upwork jobs. Chains the official Upwork MCP (find_jobs) with the upwork-toolkit judgment tools (score_job, red_flag_scan, connects_roi). Read-only; never submits anything.
---

# Upwork job triage

Needs two MCP servers connected: `upwork` (official, https://mcp.upwork.com/mcp) and `upwork-toolkit` (this repo). See docs/connect-official-upwork-mcp.md.

## Steps

1. Ask the user for the search (skills/keywords, budget floor, job type). If they gave none, use what their profile suggests via the official server; do not invent a niche.
2. Search with the official `find_jobs` tool. Keep to ordinary, user-initiated searches. Do not loop it on a timer.
3. For each result, call `score_job` with the row as returned. Set `excluded_countries` only if the user told you to. Leave `liveness_confirmed` false unless you actually re-checked the posting through the official server.
4. Drop every `kill` verdict, but show the one-line gate reason so the user can overrule it.
5. For `bid` and `maybe`, call `connects_roi` with the Connects cost from the official server and a realistic project value. Say plainly that win probability is a heuristic unless the user supplied their own win rate.
6. Report a table: title, score, verdict, kill gates or top reasons, Connects cost, EV, recommendation. Offer to run `upwork-proposal-writer` on the ones the user picks.

## Rules

- Read-only. Never create or submit a proposal from this skill.
- Show unknown fields from `score_job.unknown` instead of guessing them.
- Never promise a win rate or income.
