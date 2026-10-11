"""Red-flag scanner for job descriptions. Pure regex, no network, no LLM."""
from __future__ import annotations

import re
from typing import Any, Optional

# (id, severity, kill, regex, message)
_RULES: list[tuple[str, str, bool, str, str]] = [
    ("actual_price", "high", True,
     r"(actual|real|true|final)\s+(price|budget)|not\s+a\s+place\s*holder|(price|budget)\s+(offered|listed|shown|above)\s+is\s+not",
     "Client says the posted budget is not the real one - a mega-scope for a token price."),
    ("off_platform_payment", "high", True,
     r"outside\s+(of\s+)?upwork|off[-\s]?platform|avoid(ing)?\s+(upwork\s+)?fees|pay(ment)?\s+(you\s+)?(via|through|by|with)\s+(paypal|wise|zelle|venmo|cash\s*app|usdt|crypto|bank\s+transfer|wire)|(paypal|zelle|venmo|usdt)\s+only",
     "Off-platform payment. Upwork ToS violation and no payment protection."),
    ("off_platform_contact", "high", False,
     r"\b(whatsapp|telegram|skype|discord|wechat|signal)\b|[\w.+-]+@[\w-]+\.[\w.-]+|(contact|reach|message|text|call)\s+me\s+(on|at|via)\b",
     "Pulls the conversation off Upwork before a contract exists."),
    ("free_work", "high", False,
     r"free\s+(sample|test|trial|work|task|mock-?up|prototype)|unpaid\s+(test|trial|task|sample)|work\s+for\s+exposure|trial\s+without\s+pay",
     "Asks for unpaid work."),
    ("spec_work", "medium", False,
     r"(send|submit|share|provide|build)\s+(a\s+|your\s+)?(full\s+|complete\s+|working\s+|finished\s+)?(prototype|mock-?up|design|demo|sample)s?\s+(before|with\s+your\s+(proposal|application)|to\s+apply)",
     "Wants finished spec work as part of applying."),
    ("sensitive_info", "high", False,
     r"\b(ssn|social\s+security|passport|bank\s+(login|details|account\s+number)|password|one[-\s]?time\s+(code|password)|otp|verification\s+code|gift\s*cards?)\b",
     "Asks for sensitive credentials or identity data."),
    ("get_rich", "high", False,
     r"guaranteed\s+(profit|returns?)|get\s+rich|pump\s+and\s+dump|100%\s+(profit|roi)",
     "Get-rich framing."),
    ("remote_access", "medium", False,
     r"\b(anydesk|teamviewer|ultraviewer)\b|remote\s+access\s+to\s+your\s+(computer|pc|laptop)|install\s+(this|the)\s+(software|extension|app)\s+(i|we)\s+(send|provide)",
     "Asks you to install software or give remote access to your machine."),
    ("lowball", "medium", False,
     r"low\s+budget|budget\s+is\s+(very\s+)?tight|cheapest|lowest\s+(price|bid|rate)|bid\s+low|looking\s+for\s+cheap",
     "Price-first buyer language."),
    ("future_work_carrot", "low", False,
     r"(lots?|plenty)\s+of\s+(more\s+)?work\s+(coming|ahead|to\s+follow)|long[-\s]term\s+(work\s+)?if\s+(it\s+)?goes\s+well|start(ing)?\s+small\s+and\s+(grow|scale)",
     "Promises future work to justify a low first price."),
    ("urgency", "low", False,
     r"\b(asap|urgent(ly)?|immediately|right\s+now|within\s+(1|one|2|two|3|three)\s+hours?)\b",
     "Urgency pressure."),
    ("always_on", "medium", False,
     r"24\s*/\s*7|round\s+the\s+clock|always\s+available|available\s+at\s+all\s+times",
     "Expects around-the-clock availability."),
]

_SEV_POINTS = {"high": 10, "medium": 5, "low": 2}
_DELIVERABLE = re.compile(r"(^|\n)\s*(?:[-*•]|\d+[.)])\s+\S", re.M)


def scan(text: str, fixed_budget: Optional[float] = None) -> list[dict[str, Any]]:
    """Return a list of flags: id, severity, kill, message, evidence."""
    out: list[dict[str, Any]] = []
    t = text or ""
    for fid, sev, kill, pattern, msg in _RULES:
        m = re.search(pattern, t, re.I)
        if m:
            s = max(0, m.start() - 30)
            out.append({"id": fid, "severity": sev, "kill": kill, "message": msg,
                        "evidence": t[s:m.end() + 30].replace("\n", " ").strip()})
    if fixed_budget is not None:
        n_items = len(_DELIVERABLE.findall(t))
        words = len(t.split())
        if (n_items >= 6 and fixed_budget < 200) or (words > 250 and fixed_budget < 100):
            out.append({"id": "budget_scope_mismatch", "severity": "high", "kill": False,
                        "message": f"Large scope ({n_items} list items, {words} words) against a ${fixed_budget:,.0f} budget.",
                        "evidence": f"budget={fixed_budget:g}"})
    return out


def penalty(flags: list[dict[str, Any]], cap: int = 20) -> int:
    return min(cap, sum(_SEV_POINTS[f["severity"]] for f in flags))
