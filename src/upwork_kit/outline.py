"""Proposal outline from a job description. No LLM: regex + templates.

It produces structure and the questions worth asking. YOU supply the proof
(real shipped work) - the outline leaves explicit [FILL: ...] slots, which
`proposal_lint` will flag as placeholders if you forget one.
"""
from __future__ import annotations

import re
from typing import Any

from .textutil import keywords

_INSTRUCTION = re.compile(
    r"((?:start|begin|open)\s+(?:your\s+)?(?:proposal|application|cover letter|message)\s+with[^.\n]{0,80}|"
    r"(?:include|mention|use|type|put)\s+(?:the\s+)?(?:word|phrase|code|keyword)\s+[\"'“]?[^.\n]{1,60}|"
    r"(?:answer|respond to)\s+(?:the\s+)?(?:following|these)\s+questions?[^.\n]{0,80}|"
    r"(?:share|send|provide|include|attach)\s+(?:a\s+)?(?:link|links|portfolio|examples?|samples?|case study)[^.\n]{0,80})", re.I)
_TOOLS = ["n8n", "zapier", "make.com", "make", "gohighlevel", "highlevel", "ghl", "wordpress", "woocommerce", "shopify", "python",
          "javascript", "typescript", "react", "next.js", "node", "openai", "claude", "gpt", "api", "webhook", "zoho", "hubspot",
          "salesforce", "airtable", "notion", "slack", "stripe", "postgres", "postgresql", "mysql", "supabase", "firebase",
          "django", "flask", "fastapi", "aws", "docker", "figma", "ga4", "seo", "wix", "squarespace", "webflow", "sql"]
_BULLET = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+(.*\S)\s*$")


def _deliverables(desc: str) -> list[str]:
    items = []
    for line in desc.splitlines():
        m = _BULLET.match(line)
        if m:
            items.append(m.group(1)[:140])
    if not items:
        for s in re.split(r"(?<=[.!?])\s+", desc):
            if re.search(r"\b(build|create|set up|integrate|connect|automate|fix|migrate|design|develop|implement|write|audit|configure)\b", s, re.I):
                items.append(s.strip()[:140])
    return items[:6]


def _gaps(desc: str, fixed_budget: Any, hourly: Any) -> list[tuple[str, str]]:
    g = []
    d = desc.lower()
    if fixed_budget is None and hourly is None:
        g.append(("budget", "What budget range or hourly ceiling did you have in mind for this?"))
    if not re.search(r"\b(deadline|timeline|by\s+\w+day|within\s+\d+|\d+\s*(day|week|month)s?|asap|urgent)\b", d):
        g.append(("timeline", "Is there a date this needs to be live by, or is the timeline flexible?"))
    if not re.search(r"\b(access|login|credentials|existing|current|already (have|use))\b", d):
        g.append(("starting_point", "What are you running today (tools, accounts, any existing build) so I do not duplicate it?"))
    if not re.search(r"\b(success|goal|outcome|kpi|result|measure)\b", d):
        g.append(("success", "How will you judge this a success once it is delivered?"))
    return g


def outline(job_title: str, job_description: str, fixed_budget: Any = None, hourly: Any = None) -> dict[str, Any]:
    desc = job_description or ""
    kws = keywords(desc, job_title, top=8)
    low = (job_title + " " + desc).lower()
    tools = [t for t in dict.fromkeys(_TOOLS) if re.search(r"(?<![a-z0-9])" + re.escape(t) + r"(?![a-z0-9])", low)]
    instructions = [m.group(1).strip() for m in _INSTRUCTION.finditer(desc)]
    jd_questions = [l.strip() for l in re.split(r"(?<=[?])\s+|\n", desc) if l.strip().endswith("?")][:5]
    dl = _deliverables(desc)
    gaps = _gaps(desc, fixed_budget, hourly)
    ask = [q for _, q in gaps][:2] or ["What is the one outcome that would make this a clear win for you?"]

    hook_terms = ", ".join(kws[:3]) if kws else job_title
    sections = [
        {"section": "hook", "words": "20-30",
         "guide": f"Restate their problem in their words. Work in: {hook_terms}. No greeting filler, do not open with 'I'."},
        {"section": "proof", "words": "30-45",
         "guide": "[FILL: one real, shipped example closest to this job, with the concrete outcome and what you built. Only claims you can back up.]"},
        {"section": "plan", "words": "40-60",
         "guide": "Three short steps tied to their deliverables: " + ("; ".join(f"({i + 1}) {d[:70]}" for i, d in enumerate(dl[:3])) if dl else "[FILL: 3 steps you would take first]")},
        {"section": "question", "words": "15-25", "guide": "Ask ONE of: " + " | ".join(ask)},
        {"section": "close", "words": "8-15", "guide": "One line: what you can start with and when. No contact details, no off-platform links."},
    ]
    must = list(instructions)
    skeleton = "\n".join(f"{i + 1}. {s['section'].upper()} ({s['words']} words): {s['guide']}" for i, s in enumerate(sections))
    return {"job_title": job_title, "mirror_keywords": kws, "tools_mentioned": tools,
            "client_instructions_to_follow": must,
            "client_questions_to_answer": jd_questions, "deliverables": dl,
            "gaps_and_questions": [{"gap": a, "question": b} for a, b in gaps],
            "sections": sections, "target_words": "120-180", "skeleton": skeleton,
            "note": "Fill every [FILL: ...] slot with real work, then run proposal_lint. Follow any client_instructions_to_follow literally."}
