"""Small shared text helpers."""
from __future__ import annotations

import re
from collections import Counter

STOP = set("""a about above after again all also am an and any are as at be because been before being below between both but by can
could did do does doing down during each few for from further had has have having he her here hers him his how i if in into is it its
just me more most my no nor not now of off on once only or other our out over own same she should so some such than that the their
them then there these they this those through to too under until up us very was we were what when where which while who whom why will
with would you your yours looking need needs want wanted seeking hire hiring job project work worker freelancer please experience
experienced ideal candidate must good great new etc able using use also well like get make""".split())


def words(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9][A-Za-z0-9+#.'-]*", text or "")


def keywords(text: str, title: str = "", top: int = 10) -> list[str]:
    cnt: Counter[str] = Counter()
    for w in words(text):
        lw = w.lower().strip(".'-")
        if len(lw) > 2 and lw not in STOP and not lw.isdigit():
            cnt[lw] += 1
    for w in words(title):
        lw = w.lower().strip(".'-")
        if len(lw) > 2 and lw not in STOP:
            cnt[lw] += 3
    return [w for w, _ in cnt.most_common(top)]
