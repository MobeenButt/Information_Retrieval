"""ir_demo.py  –  standalone IR model demonstration (no external libraries needed).

Implements and compares all six IR models on a hand-built evidence corpus:
  1. Boolean retrieval   (AND / OR / NOT)
  2. Overlap             |Q ∩ D|
  3. Non-overlap         Q \\ D  (missing terms)
  4. Vector Space        TF-IDF cosine similarity
  5. BIM                 Binary Independence Model (Robertson-Sparck Jones)
  6. BM25                Okapi BM25

Run:   python backend/ir_demo.py
"""
import math
import re
from collections import Counter, defaultdict

# ─────────────────────────────────────────────────────────────────────────────
#  0. Corpus + ground-truth queries  (FYP software-bug evidence scenario)
# ─────────────────────────────────────────────────────────────────────────────
DOCS = [
    ("D1",  "log",      "ERROR checkout-service TypeError NoneType object has no attribute price in calculate_total discount_id is None order 8841"),
    ("D2",  "commit",   "a1b2c3 removes null check for discount_id in pricing module calculate_total"),
    ("D3",  "incident", "INC-101 resolved checkout returns 500 when discount is missing root cause missing null check fix adds guard clause and regression test"),
    ("D4",  "log",      "WARN payment-service timeout calling stripe gateway after 30s retry exhausted order 9102"),
    ("D5",  "incident", "INC-087 resolved payment page slow because external gateway timeout not handled fix adds timeout and retry with backoff"),
    ("D6",  "code",     "calculate_total order sums item price item qty and subtracts order discount amount"),
    ("D7",  "ticket",   "BUG-214 checkout crash 500 error after latest deploy orders without coupon fail"),
    ("D8",  "log",      "ERROR auth-service 403 user 17 tried to read order 5521 owned by user 42"),
    ("D9",  "incident", "INC-066 resolved user could view another users order missing ownership check fix adds authorization check"),
    ("D10", "commit",   "d4e5f6 update README and add docker compose for local setup"),
    ("D11", "log",      "ERROR order-service database constraint violation total does not match sum of line items order 7310"),
    ("D12", "code",     "get_order order_id user returns the order without an owner check TODO"),
    ("D13", "readme",   "checkout payment order services error logs timeout settings discount configuration README setup guide docker local development environment"),
]

QUERIES = [
    ("Q1", "checkout returns 500 error discount null",     ["D1","D2","D3","D6","D7"]),
    ("Q2", "payment gateway timeout",                      ["D4","D5"]),
    ("Q3", "user can see another user order",              ["D8","D9","D12"]),
    ("Q4", "order total mismatch line items",              ["D11"]),
    ("Q5", "NoneType has no attribute price",              ["D1","D6"]),
    ("Q6", "payment service timeout error",                ["D4","D5"]),
]

# ─────────────────────────────────────────────────────────────────────────────
#  1. Preprocessing  (code-aware tokeniser + stop-word removal + light stemming)
# ─────────────────────────────────────────────────────────────────────────────
STOPWORDS = frozenset("a about above after all also am an and any are as at be because been "
    "before being below between both but by can could did do does doing down during each "
    "few for from further had has have having he her here hers him his how i if in into is "
    "it its itself just me more most my no nor not now of off on once only or other our out "
    "over own same she should so some such than that the their them then there these they "
    "this those through to too under until up very was we were what when where which while "
    "who whom why will with would you your".split())

_SPLIT_IDENT = re.compile(r'[_]+|(?<=[a-z])(?=[A-Z])')   # snake_case / camelCase
_TOKEN       = re.compile(r'[a-z0-9]+')


def tokenize(text):
    """Lowercase, split snake/camelCase, extract alphanumeric tokens."""
    text = _SPLIT_IDENT.sub(' ', text)
    return _TOKEN.findall(text.lower())


def stem(w):
    """Simple suffix stripper: trailing 's', 'ing', 'ed'."""
    if len(w) <= 3:
        return w
    if w.endswith('sses'):
        return w[:-2]
    if w.endswith('ies') and len(w) > 4:
        return w[:-3] + 'y'
    if w.endswith('s') and not w.endswith(('ss', 'us', 'is')):
        return w[:-1]
    for suf in ('ing', 'ed'):
        if w.endswith(suf) and len(w) - len(suf) >= 3:
            base = w[:-len(suf)]
            if any(c in 'aeiou' for c in base):
                if base[-1] == base[-2] and base[-1] not in 'aeioulisz':
                    base = base[:-1]
                return base
    return w


def preprocess(text):
    return [stem(t) for t in tokenize(text) if t not in STOPWORDS]


# ─────────────────────────────────────────────────────────────────────────────
#  2. Inverted index  (shared by all models)
# ─────────────────────────────────────────────────────────────────────────────
def build_index(docs):
    postings  = defaultdict(dict)   # term -> {doc_id: tf}
    doc_len   = {}
    doc_text  = {}
    for did, dtype, text in docs:
        terms = preprocess(text)
        doc_text[did] = text
        doc_len[did]  = len(terms)
        for term, tf in Counter(terms).items():
            postings[term][did] = tf
    N      = len(docs)
    avgdl  = sum(doc_len.values()) / max(1, N)
    # TF-IDF norms for cosine
    norms  = defaultdict(float)
    for term, plist in postings.items():
        df  = len(plist)
        idf = math.log(1 + N / df)
        for did, tf in plist.items():
            w = (1 + math.log(tf)) * idf
            norms[did] += w * w
    norms = {d: math.sqrt(v) or 1.0 for d, v in norms.items()}
    return {
        "postings": postings, "doc_len": doc_len, "norms": norms,
        "avgdl": avgdl, "N": N, "doc_text": doc_text
    }


# ─────────────────────────────────────────────────────────────────────────────
#  3. IR Models
# ─────────────────────────────────────────────────────────────────────────────

# --- 3.1 Boolean ---
def boolean_and(idx, terms):
    sets = [set(idx["postings"].get(t, {}).keys()) for t in set(terms)]
    if not sets: return set()
    result = sets[0]
    for s in sets[1:]: result &= s
    return result

def boolean_or(idx, terms):
    result = set()
    for t in set(terms): result |= set(idx["postings"].get(t, {}).keys())
    return result

def boolean_not(idx, terms):
    return set(idx["doc_len"].keys()) - boolean_or(idx, terms)


# --- 3.2 Overlap ---
def overlap_scores(idx, terms):
    qt = set(terms)
    scores = defaultdict(float)
    for t in qt:
        for did in idx["postings"].get(t, {}):
            scores[did] += 1.0
    return dict(scores)


# --- 3.3 Non-overlap ---
def nonoverlap_info(idx, terms):
    """Returns {doc_id: {"score": int, "missing": [terms]}}"""
    qt = set(terms)
    matched = defaultdict(set)
    for t in qt:
        for did in idx["postings"].get(t, {}):
            matched[did].add(t)
    result = {}
    for did in idx["doc_len"]:
        m = matched.get(did, set())
        result[did] = {"score": float(len(m)), "missing": sorted(qt - m)}
    return result


# --- 3.4 TF-IDF (Vector Space Model) ---
def tfidf_scores(idx, terms):
    scores = defaultdict(float)
    N = idx["N"]
    for term, qtf in Counter(terms).items():
        plist = idx["postings"].get(term)
        if not plist: continue
        idf      = math.log(1 + N / len(plist))
        q_weight = (1 + math.log(qtf)) * idf
        for did, tf in plist.items():
            scores[did] += q_weight * (1 + math.log(tf)) * idf
    return {d: s / idx["norms"][d] for d, s in scores.items()}


# --- 3.5 BIM (Binary Independence Model) ---
def bim_scores(idx, terms, relevant_ids=None):
    N   = idx["N"]
    R   = len(relevant_ids) if relevant_ids else 0
    rel = set(relevant_ids) if relevant_ids else set()
    scores = defaultdict(float)
    for t in set(terms):
        plist = idx["postings"].get(t, {})
        n = len(plist)
        r = sum(1 for d in plist if d in rel)
        num = (r + 0.5) * (N - n + 0.5)
        den = (n - r + 0.5) * (R - r + 0.5) if R > 0 else (n + 0.5)
        w = math.log(max(num / max(den, 1e-9), 1e-9))
        for did in plist:
            scores[did] += w
    return dict(scores)


# --- 3.6 BM25 ---
def bm25_scores(idx, terms, k1=1.5, b=0.75):
    scores = defaultdict(float)
    N = idx["N"]
    for t in set(terms):
        plist = idx["postings"].get(t)
        if not plist: continue
        df  = len(plist)
        idf = math.log(1 + (N - df + 0.5) / (df + 0.5))
        for did, tf in plist.items():
            norm = k1 * (1 - b + b * idx["doc_len"][did] / idx["avgdl"])
            scores[did] += idf * tf * (k1 + 1) / (tf + norm)
    return dict(scores)


# ─────────────────────────────────────────────────────────────────────────────
#  4. Evaluation metrics
# ─────────────────────────────────────────────────────────────────────────────

def precision_at_k(ranked, relevant, k):
    return sum(1 for d in ranked[:k] if d in relevant) / k

def recall_at_k(ranked, relevant, k):
    if not relevant: return 0.0
    return sum(1 for d in ranked[:k] if d in relevant) / len(relevant)

def mrr(ranked, relevant):
    for i, d in enumerate(ranked, 1):
        if d in relevant: return 1.0 / i
    return 0.0

def ndcg_at_k(ranked, relevant, k):
    dcg  = sum(1 / math.log2(i + 1) for i, d in enumerate(ranked[:k], 1) if d in relevant)
    idcg = sum(1 / math.log2(i + 1) for i in range(1, min(len(relevant), k) + 1))
    return dcg / idcg if idcg else 0.0

def evaluate(model_fn, idx, queries, k=3):
    rows = []
    for qid, qtext, rel_ids in queries:
        terms  = preprocess(qtext)
        scores = model_fn(idx, terms)
        if isinstance(scores, dict):
            ranked = [d for d, _ in sorted(scores.items(), key=lambda x: -x[1])]
        else:
            ranked = sorted(scores)   # boolean returns a set
        rel = set(rel_ids)
        rows.append({
            "qid": qid,
            "P@3": precision_at_k(ranked, rel, 3),
            "R@3": recall_at_k(ranked, rel, 3),
            "MRR": mrr(ranked, rel),
            "nDCG@5": ndcg_at_k(ranked, rel, 5),
        })
    means = {m: sum(r[m] for r in rows) / len(rows) for m in ("P@3","R@3","MRR","nDCG@5")}
    return rows, means


# ─────────────────────────────────────────────────────────────────────────────
#  5. Main – run everything and print results
# ─────────────────────────────────────────────────────────────────────────────
def main():
    idx = build_index(DOCS)

    SEP = "─" * 72

    # ── 5.1 Boolean demo ───────────────────────────────────────────────────
    print(SEP)
    print("BOOLEAN RETRIEVAL")
    print(SEP)
    q1_terms = preprocess("checkout discount null")
    print(f"  AND  ({' AND '.join(q1_terms)}): {boolean_and(idx, q1_terms)}")
    print(f"  OR   ({' OR  '.join(q1_terms)}): {boolean_or(idx, q1_terms)}")
    print(f"  NOT  ({' '.join(q1_terms)}):     (first 5) {list(boolean_not(idx, q1_terms))[:5]}")

    # ── 5.2 Overlap / Non-overlap demo ────────────────────────────────────
    print(f"\n{SEP}")
    print("OVERLAP and NON-OVERLAP  (Q1: checkout returns 500 error discount null)")
    print(SEP)
    q1 = preprocess("checkout returns 500 error discount null")
    no_data = nonoverlap_info(idx, q1)
    top5 = sorted(((d, v["score"]) for d, v in no_data.items() if v["score"] > 0),
                  key=lambda x: -x[1])[:5]
    print(f"  {'Doc':<6} {'Score':>6}  Missing terms")
    for d, s in top5:
        miss = no_data[d]["missing"]
        print(f"  {d:<6} {s:>6.0f}  {miss or '(none)'}")

    # ── 5.3 BM25 step-by-step (Q2) ────────────────────────────────────────
    print(f"\n{SEP}")
    print("BM25 STEP-BY-STEP  (Q2: payment gateway timeout)")
    print(SEP)
    q2 = preprocess("payment gateway timeout")
    N = idx["N"]
    print(f"  Collection: N={N}, avgdl={idx['avgdl']:.1f}, k1=1.5, b=0.75")
    print(f"\n  {'Term':<12} {'df':>4} {'IDF':>8}  D4 contrib  D5 contrib")
    for t in q2:
        plist = idx["postings"].get(t, {})
        df  = len(plist)
        idf = math.log(1 + (N - df + 0.5) / (df + 0.5))
        def contrib(did):
            tf = plist.get(did, 0)
            if tf == 0: return "-"
            norm = 1.5 * (1 - 0.75 + 0.75 * idx["doc_len"][did] / idx["avgdl"])
            return f"{idf * tf * 2.5 / (tf + norm):.3f}(tf={tf})"
        print(f"  {t:<12} {df:>4} {idf:>8.3f}  {contrib('D4'):<12} {contrib('D5')}")
    sc = bm25_scores(idx, q2)
    top_q2 = sorted(sc.items(), key=lambda x: -x[1])[:3]
    print(f"\n  Top 3: {[(d, round(s,3)) for d,s in top_q2]}")

    # ── 5.4 BIM relevance feedback (Q6) ───────────────────────────────────
    print(f"\n{SEP}")
    print("BIM RELEVANCE FEEDBACK  (Q6: payment service timeout error)")
    print(SEP)
    q6 = preprocess("payment service timeout error")
    sc_before = bim_scores(idx, q6)
    top_before = [d for d,_ in sorted(sc_before.items(), key=lambda x: -x[1])[:4]]
    print(f"  Before feedback: {top_before}")
    sc_after = bim_scores(idx, q6, relevant_ids=["D4"])
    top_after  = [d for d,_ in sorted(sc_after.items(), key=lambda x: -x[1])[:4]]
    print(f"  After D4 marked relevant: {top_after}")

    # ── 5.5 Top-3 table for all queries ───────────────────────────────────
    print(f"\n{SEP}")
    print("TOP-3 RESULTS PER QUERY")
    print(SEP)
    model_fns = {
        "Overlap":  lambda i, t: overlap_scores(i, t),
        "BIM":      lambda i, t: bim_scores(i, t),
        "BM25":     lambda i, t: bm25_scores(i, t),
        "TF-IDF":   lambda i, t: tfidf_scores(i, t),
    }
    header = f"  {'Query':<6}" + "".join(f" {m:<22}" for m in model_fns)
    print(header)
    print("  " + "-" * (len(header) - 2))
    for qid, qtext, rel_ids in QUERIES:
        terms = preprocess(qtext)
        rel   = set(rel_ids)
        row   = f"  {qid:<6}"
        for mname, fn in model_fns.items():
            sc = fn(idx, terms)
            top3 = [d for d,_ in sorted(sc.items(), key=lambda x:-x[1])[:3]]
            # mark relevant items with *
            col = ", ".join(d + ("*" if d in rel else "") for d in top3)
            row += f" {col:<22}"
        print(row)
    print("  (* = truly relevant)")

    # ── 5.6 Metrics comparison ────────────────────────────────────────────
    print(f"\n{SEP}")
    print("METRICS COMPARISON  (mean over 6 queries, k=3)")
    print(SEP)
    all_models = {
        "Boolean-OR":  lambda i, t: {d: 1.0 for d in boolean_or(i, t)},
        "Overlap":     overlap_scores,
        "Non-overlap": lambda i, t: {d: v["score"] for d, v in nonoverlap_info(i, t).items()},
        "TF-IDF":      tfidf_scores,
        "BIM":         bim_scores,
        "BM25":        bm25_scores,
    }
    print(f"  {'Model':<14} {'P@3':>6} {'R@3':>6} {'MRR':>6} {'nDCG@5':>8}")
    print("  " + "-" * 44)
    best_mrr = 0.0
    best_model = ""
    for mname, fn in all_models.items():
        _, means = evaluate(fn, idx, QUERIES)
        print(f"  {mname:<14} {means['P@3']:>6.3f} {means['R@3']:>6.3f} "
              f"{means['MRR']:>6.3f} {means['nDCG@5']:>8.3f}")
        if means["MRR"] > best_mrr:
            best_mrr, best_model = means["MRR"], mname
    print(f"\n  Best model by MRR: {best_model}  ({best_mrr:.3f})")
    print(SEP)


if __name__ == "__main__":
    main()
