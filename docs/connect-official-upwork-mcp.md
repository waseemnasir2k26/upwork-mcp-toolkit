# Connect the official Upwork MCP server (and run it next to this toolkit)

Upwork publishes a first-party MCP server at `https://mcp.upwork.com/mcp` (OAuth 2.1, free). Its own page is <https://www.upwork.com/ai/mcp>. That server **fetches and acts**: job search, your profile, proposal drafts, messages, contracts. This toolkit **judges**: it scores jobs, lints proposals and does the fee maths, offline, with no Upwork credentials.

Use both. Never use a browser-automation "Upwork MCP" that drives a logged-in session; that is the thing Upwork's bot policy bans, and this repo does not do it.

## 1. Claude Code

Official server:

```bash
claude mcp add --transport http upwork https://mcp.upwork.com/mcp
```

Then inside Claude Code run `/mcp`, pick `upwork`, and choose **Authenticate**. A browser window opens for Upwork's OAuth consent.

This toolkit (local stdio server):

```bash
pip install git+https://github.com/waseemnasir2k26/upwork-mcp-toolkit.git
claude mcp add upwork-toolkit -- python -m upwork_kit.server
```

(Not on PyPI. If `python` on your PATH is not the interpreter you installed into, use its absolute path.)

Check both are connected: run `/mcp`; you should see `upwork` and `upwork-toolkit`.

## 2. Claude Desktop

Official server: Upwork lists a Claude Desktop connector in the Claude connectors directory (Settings > Connectors, search "Upwork"). Add it there and complete the OAuth prompt.

This toolkit: edit `claude_desktop_config.json` (Settings > Developer > Edit Config):

```json
{
  "mcpServers": {
    "upwork-toolkit": {
      "command": "python",
      "args": ["-m", "upwork_kit.server"]
    }
  }
}
```

Restart Claude Desktop. Use an absolute interpreter path in `command` if you installed into a virtualenv.

## 3. Cursor

`~/.cursor/mcp.json` (or the project-level `.cursor/mcp.json`):

```json
{
  "mcpServers": {
    "upwork": { "url": "https://mcp.upwork.com/mcp" },
    "upwork-toolkit": {
      "command": "python",
      "args": ["-m", "upwork_kit.server"]
    }
  }
}
```

Cursor then walks you through the OAuth sign-in for the remote `upwork` entry. Remote-server and OAuth support depends on your Cursor version; if the remote entry does not appear, check Cursor's MCP docs for your build.

## 4. Running both together: the workflow

```
 official upwork MCP                this toolkit (offline)
 ---------------------              ----------------------
 find_jobs  ───────────────────────► score_job ──► red_flag_scan
 (title, budget, client stats)           │
                                         ▼
                                    connects_roi   (is the Connects spend worth it?)
 profile / past work ◄─ you ──────  proposal_outline ──► draft ──► proposal_lint
 manage_proposals (DRAFT) ◄───────── you read it, then confirm in the official server
```

1. Ask the agent to search jobs with the official server.
2. Pass each result row to `score_job`. Rows from the official `find_jobs` search are accepted as-is (hourly ranges like `25.00-55.00/hr`, `proposal_count` absent when 0, `verification_status`).
3. For anything scored `bid` or `maybe`, call `connects_roi` with the Connects cost the official server shows in its proposal preview.
4. `proposal_outline`, write the proposal in your voice with real proof, then `proposal_lint` until it is clean.
5. Create the draft in the official server. **You** read it and confirm.

Skills that chain these steps are in [`.claude/skills/`](../.claude/skills).

## 5. Safety

- **Keep draft-confirm ON.** Upwork's server drafts every write action (including submitting a proposal) and waits for an explicit confirm; binding money actions finish on upwork.com. The confirmation behaviour can be changed per tool in some agents. Do not switch it off, and do not wrap this in anything that auto-confirms. A person reads and confirms every proposal.
- **Connecting grants the full scope set.** At the time of writing Upwork says connecting grants the full set of scopes (there is no per-scope picker), writes included. That is why the confirm step matters.
- **Spend is real.** Submitting a proposal spends Connects on confirm.
- **This toolkit never touches Upwork.** No network calls, no tokens, no cookies. `grep -rnE "^(import|from) (requests|httpx|urllib|socket|aiohttp)" src/` returns nothing; you can check.
- **Revoke access any time:** Upwork Account Settings > Connected Apps > remove the app. Upwork documents that this invalidates access and refresh tokens. If auth errors appear later, disconnect and reconnect.
- **If you see a certificate error in a client** while `curl` reaches the host fine, that is a client trust-store issue, not necessarily an Upwork outage.
- Do not paste client names, emails or contract details into public issues or prompts you share.

## Fee note

Upwork's help article "Learn about the Freelancer Service Fee" (checked 2026-10-12) says the fee ranges from 0% to 15% per contract, is shown on the proposal/offer, and is locked once the contract starts. So `rate_calculator` and `connects_roi` take `fee_percent` as an input. Use the figure Upwork shows you; 10% is only the default.
