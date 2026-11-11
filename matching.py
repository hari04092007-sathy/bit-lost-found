"""Rule-based matching (keyword overlap + weighted fields). Not machine learning."""
import re
STOP = {"the","a","an","and","of","with","in","on","at","near","my","is","it","to","for","has","have","black","blue"}
def tokens(t): return {w for w in re.findall(r"[a-z0-9]+", (t or "").lower()) if w not in STOP and len(w) > 2}
def jac(a, b): return len(a & b) / len(a | b) if a and b else 0.0

def score(a, b):
    s = 30 if a.category_id == b.category_id else 0
    s += 30 * jac(tokens(a.name), tokens(b.name))
    s += 20 * jac(tokens(a.description), tokens(b.description))
    s += 10 if a.location == b.location else 0
    gap = abs((a.event_date - b.event_date).days)
    s += 10 if gap <= 3 else 5 if gap <= 10 else 0
    return round(s)

def find_matches(item, candidates, limit=5, minimum=35):
    out = [(score(item, c), c) for c in candidates if c.kind != item.kind and c.id != item.id and c.status == "approved"]
    return sorted([x for x in out if x[0] >= minimum], key=lambda x: -x[0])[:limit]
