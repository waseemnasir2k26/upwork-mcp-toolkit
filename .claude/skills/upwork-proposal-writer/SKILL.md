---
name: upwork-proposal-writer
description: Draft a human-reviewed Upwork proposal for a chosen job. Use when the user wants a cover letter/proposal for a specific Upwork job. Chains the official Upwork MCP (job details, profile, draft) with upwork-toolkit (proposal_outline, proposal_lint, red_flag_scan). Never confirms or submits on the user's behalf.
---

# Upwork proposal writer

Needs `upwork` (official) and `upwork-toolkit` connected.

## Steps

1. Get the full posting from the official server (`find_jobs` with the get action). Also check the user's existing proposals and invitations for this job through the official server before drafting; skip if already applied.
2. `red_flag_scan` the description. If any flag has `kill: true`, stop and tell the user why.
3. `proposal_outline` with the title and description. Obey `client_instructions_to_follow` literally (for example a required first word). Answer `client_questions_to_answer`.
4. Ask the user for the real proof to put in the `[FILL: ...]` slot: a specific thing they actually shipped. Do not invent projects, clients, numbers or results. If they have none that fits, say so in the draft by leading with approach instead.
5. Write 120-180 words in the user's voice: lead with the client's problem using their wording, one proof point, a three-step plan, ONE specific question, one-line close.
6. `proposal_lint` the draft with the job title and description. Fix every error and warning, re-lint until `ok` is true. Never paste email, phone, messaging handles, payment methods or booking links.
7. Create the draft in the official server and show it. **Stop.** The user reads it and confirms in the official server's draft-confirm step. Never auto-confirm, never turn confirmation off.

## Rules

- No unattended submission, ever. One proposal at a time, human confirms each.
- No scraping, no logged-in browser automation, no mass-apply.
- Do not quote Upwork rules you have not verified; link the docs instead.
