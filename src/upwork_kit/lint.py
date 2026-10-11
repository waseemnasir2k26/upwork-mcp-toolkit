"""Proposal linter. Deterministic checks a human reviewer would make.

The 120-180 word window is a house heuristic for a cover letter that gets read
on a phone; it is not an Upwork rule. The off-platform checks reflect Upwork's
rule against taking communication/payment outside the platform before and
outside a contract (see docs/faq in the README).
"""
from __future__ import annotations

import re
from typing import Any, Optional

from .textutil import keywords, words

WORD_MIN, WORD_MAX = 120, 180

_CONTACT = [
    ("email", r"[\w.+-]+@[\w-]+\.[\w.-]+"),
    ("phone", r"(?<!\w)\+?\d[\d\s().-]{8,}\d(?!\w)"),
    ("messaging_app", r"\b(whatsapp|telegram|skype|discord|wechat|signal|viber|imessage)\b"),
    ("contact_me_phrase", r"\b(contact|reach|message|text|call|email|dm)\s+me\s+(on|at|via|through|outside)\b"),
]
_PAYMENT = r"\b(paypal|wise|zelle|venmo|cash\s*app|payoneer|usdt|bitcoin|crypto|bank\s+transfer|wire\s+transfer|direct\s+payment)\b|outside\s+(of\s+)?upwork|off[-\s]?platform|avoid(ing)?\s+(the\s+)?(upwork\s+)?fees?|skip\s+(the\s+)?(upwork\s+)?fees?"
_BOOKING = r"\b(calendly\.com|cal\.com|savvycal\.com|tidycal\.com)\b"
_PLACEHOLDER = [
    r"\[FILL[^\]]*\]", r"\[[^\]\n]{1,60}\]", r"\{\{[^}\n]{1,60}\}\}", r"<[A-Z][A-Z _-]{2,40}>", r"\blorem ipsum\b",
    r"\b(insert|your name here|client name|company name)\b", r"\bXYZ\b", r"\bTODO\b", r"\bTBD\b",
]
_GENERIC_OPEN = [
    r"^\s*dear\s+(sir|madam|hiring|client)", r"^\s*(hello|hi)\s+(sir|madam|there)\b", r"to whom it may concern",
    r"i\s+(came|stumbled)\s+across\s+your", r"i\s+saw\s+your\s+(job|post|listing)", r"i\s+am\s+writing\s+to\s+(apply|express)",
    r"i\s+hope\s+(this|you)", r"i\s+am\s+interested\s+in\s+your",
]
_AI_TELLS = [
    r"i hope this message finds you", r"in today'?s (fast[- ]paced|digital|ever[- ]changing)", r"\bdelve\b", r"\btapestry\b",
    r"\bseamless(ly)?\b", r"\brobust\b", r"cutting[- ]edge", r"\bgame[- ]chang(er|ing)\b", r"\belevate\b", r"\bleverage\b",
    r"as an ai\b", r"i am (thrilled|excited|eager) to", r"it'?s not just .{3,40}, it'?s", r"unlock the (full )?potential",
    r"\bsynerg", r"look no further", r"i('| a)m confident that i am the (perfect|ideal)",
]


def _issue(sev: str, iid: str, msg: str, detail: Any = None) -> dict[str, Any]:
    d: dict[str, Any] = {"severity": sev, "id": iid, "message": msg}
    if detail is not None:
        d["detail"] = detail
    return d


def lint(proposal: str, job_title: str = "", job_description: str = "") -> dict[str, Any]:
    text = proposal or ""
    issues: list[dict[str, Any]] = []
    wc = len(text.split())

    if wc == 0:
        issues.append(_issue("error", "empty", "Proposal is empty."))
    elif wc < 60 or wc > 300:
        issues.append(_issue("error", "word_count", f"{wc} words; target {WORD_MIN}-{WORD_MAX}.", wc))
    elif wc < WORD_MIN or wc > WORD_MAX:
        issues.append(_issue("warn", "word_count", f"{wc} words; sweet spot is {WORD_MIN}-{WORD_MAX}.", wc))

    # contact / payment
    for name, pat in _CONTACT:
        m = re.search(pat, text, re.I)
        if m:
            issues.append(_issue("error", f"off_platform_{name}", f"Contact detail in a proposal ({name}); Upwork forbids moving communication off-platform.", m.group(0).strip()))
    m = re.search(_PAYMENT, text, re.I)
    if m:
        issues.append(_issue("error", "off_platform_payment", "Mentions paying outside Upwork or an external payment route.", m.group(0)))
    m = re.search(_BOOKING, text, re.I)
    if m:
        issues.append(_issue("warn", "booking_link", "External booking link; offer a call inside Upwork messages after the client replies.", m.group(0)))

    # placeholders / generic / AI tells
    for pat in _PLACEHOLDER:
        m = re.search(pat, text)
        if m:
            issues.append(_issue("error", "placeholder", "Unfilled placeholder left in the text.", m.group(0)))
            break
    head = " ".join(text.split()[:25])
    for pat in _GENERIC_OPEN:
        if re.search(pat, text[:160], re.I):
            issues.append(_issue("warn", "generic_opening", "Generic opening line; the first two lines are all the client sees in the list view.", head))
            break
    hits = [p for p in _AI_TELLS if re.search(p, text, re.I)]
    emd = text.count("—")
    if hits or emd >= 3:
        d = {"phrases": len(hits), "em_dashes": emd}
        issues.append(_issue("warn", "ai_tell", "Reads like boilerplate/AI filler (stock phrases or heavy em-dash use). Rewrite in your own words.", d))

    # questions
    q = text.count("?")
    if q == 0:
        issues.append(_issue("warn", "no_question", "No question. One sharp, job-specific question invites a reply."))
    elif q > 3:
        issues.append(_issue("warn", "too_many_questions", f"{q} questions reads like an interrogation; keep 1-2.", q))

    # self-centred opening
    if re.match(r"\s*I\b", text) and not re.match(r"\s*I\s+(noticed|read|saw that you)", text):
        issues.append(_issue("info", "starts_with_i", "Opens with 'I'. Lead with the client's problem instead."))

    # mirror JD
    mirror: Optional[dict[str, Any]] = None
    if job_description or job_title:
        kws = keywords(job_description, job_title, top=10)
        low = " ".join(text.split()[:35]).lower()
        found = [k for k in kws if k in low]
        mirror = {"keywords": kws, "found_in_first_35_words": found}
        if len(found) < 2:
            issues.append(_issue("warn", "opening_not_mirroring", "First lines use fewer than 2 of the job's own key terms; mirror their wording.", {"expected_any_of": kws[:6]}))

    err = sum(1 for i in issues if i["severity"] == "error")
    warn = sum(1 for i in issues if i["severity"] == "warn")
    score = max(0, 100 - 25 * err - 8 * warn)
    return {"ok": err == 0, "score": score, "word_count": wc, "questions": q,
            "issues": issues, "mirror": mirror,
            "summary": f"{err} error(s), {warn} warning(s), {wc} words"}
