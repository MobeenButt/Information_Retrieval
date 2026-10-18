"""
Week 1 — Simple Document Search Engine
=======================================
Task : Develop a simple document search engine —
       indexing, searching, and ranking a small text collection.

What this program does
----------------------
STEP 1  INDEXING   — reads every .txt file in documents/,
                     tokenises, removes stop-words, stems,
                     builds an inverted index  {term -> {doc_id: tf}}

STEP 2  SEARCHING  — takes a user query, preprocesses it the
                     same way, looks terms up in the index

STEP 3  RANKING    — scores every matching document with TF-IDF
                     and BM25, sorts by score, prints results

Run:   python search_engine.py
"""

import math
import os
import re
from collections import Counter, defaultdict


# ══════════════════════════════════════════════════════════
#  PART 1 ── TEXT PREPROCESSING
#  (same pipeline for documents AND queries)
# ══════════════════════════════════════════════════════════

# Common English words that carry almost no meaning
STOPWORDS = frozenset([
    "a", "about", "after", "all", "also", "am", "an", "and", "any", "are",
    "as", "at", "be", "because", "been", "before", "both", "but", "by",
    "can", "did", "do", "does", "during", "each", "for", "from", "had",
    "has", "have", "he", "her", "him", "his", "how", "i", "if", "in",
    "into", "is", "it", "its", "just", "me", "more", "most", "my", "no",
    "nor", "not", "now", "of", "off", "on", "once", "only", "or", "our",
    "out", "own", "same", "she", "should", "so", "some", "such", "than",
    "that", "the", "their", "them", "then", "there", "these", "they",
    "this", "those", "through", "to", "too", "under", "up", "very", "was",
    "we", "were", "what", "when", "where", "which", "while", "who", "will",
    "with", "would", "you", "your"
])


def tokenize(text):
    """Split text into lowercase alphanumeric tokens."""
    return re.findall(r'[a-z0-9]+', text.lower())


def remove_stopwords(tokens):
    """Drop tokens that are in the stop-word list."""
    return [t for t in tokens if t not in STOPWORDS]


def stem(word):
    """
    Simple suffix-stripping stemmer.
    Examples:
        running  -> run
        indexes  -> index
        queries  -> queri
        ranked   -> rank
    """
    w = word
    if len(w) <= 3:
        return w
    # plurals
    if w.endswith("sses"):
        return w[:-2]
    if w.endswith("ies") and len(w) > 4:
        return w[:-3] + "y"
    if w.endswith("s") and not w.endswith(("ss", "us", "is")):
        w = w[:-1]
    # -ing / -ed
    for suffix in ("ing", "ed"):
        if w.endswith(suffix):
            base = w[: -len(suffix)]
            if len(base) >= 3 and any(c in "aeiou" for c in base):
                # double-consonant rule: running -> runn -> run
                if (len(base) >= 2
                        and base[-1] == base[-2]
                        and base[-1] not in "aeioulisz"):
                    base = base[:-1]
                return base
    return w


def preprocess(text):
    """Full pipeline: text → list of index terms."""
    tokens   = tokenize(text)
    no_stop  = remove_stopwords(tokens)
    stems    = [stem(t) for t in no_stop]
    return stems


# ══════════════════════════════════════════════════════════
#  PART 2 ── INVERTED INDEX
# ══════════════════════════════════════════════════════════

class InvertedIndex:
    """
    Stores: postings  {term -> {doc_id: term_frequency}}
            doc_info  {doc_id -> {title, text, length}}
    Computes after build: avg_doc_len, idf per term
    """

    def __init__(self):
        self.postings   = defaultdict(dict)   # term -> {doc_id: tf}
        self.doc_info   = {}                  # doc_id -> meta
        self.avg_doc_len = 0.0

    # ── build ────────────────────────────────────────────
    def add_document(self, doc_id, title, text):
        terms = preprocess(title + " " + text)
        for term, tf in Counter(terms).items():
            self.postings[term][doc_id] = tf
        self.doc_info[doc_id] = {
            "title":  title,
            "text":   text,
            "length": len(terms),      # number of index terms
        }

    def finalize(self):
        """Call once after all documents are added."""
        n = len(self.doc_info)
        if n:
            self.avg_doc_len = sum(
                d["length"] for d in self.doc_info.values()
            ) / n

    # ── statistics ───────────────────────────────────────
    @property
    def N(self):
        return len(self.doc_info)

    def df(self, term):
        """Document frequency: how many docs contain this term."""
        return len(self.postings.get(term, {}))

    def idf(self, term):
        """Inverse document frequency (log-smoothed)."""
        df = self.df(term)
        if df == 0:
            return 0.0
        return math.log(1 + self.N / df)

    def tf(self, term, doc_id):
        """Raw term frequency of term in doc."""
        return self.postings.get(term, {}).get(doc_id, 0)


# ══════════════════════════════════════════════════════════
#  PART 3 ── RANKING MODELS
# ══════════════════════════════════════════════════════════

def tfidf_rank(index, query_terms):
    """
    TF-IDF ranking.
    score(D, Q) = Σ  tf(t,D) * idf(t)   for each query term t in D
    Simple version (no cosine normalisation) — enough for Week 1.
    """
    scores = defaultdict(float)
    for term in set(query_terms):
        if term not in index.postings:
            continue
        idf = index.idf(term)
        for doc_id, tf in index.postings[term].items():
            scores[doc_id] += tf * idf
    return scores


def bm25_rank(index, query_terms, k1=1.5, b=0.75):
    """
    BM25 ranking.
    score(D,Q) = Σ  IDF(t) * tf(t,D)*(k1+1) / (tf(t,D) + k1*(1-b+b*|D|/avgdl))

    Parameters
    ----------
    k1 : term frequency saturation  (1.5 is typical)
    b  : length normalisation       (0.75 is typical)
    """
    scores = defaultdict(float)
    for term in set(query_terms):
        if term not in index.postings:
            continue
        df  = index.df(term)
        idf = math.log(1 + (index.N - df + 0.5) / (df + 0.5))
        for doc_id, tf in index.postings[term].items():
            dl   = index.doc_info[doc_id]["length"]
            norm = k1 * (1 - b + b * dl / index.avg_doc_len)
            scores[doc_id] += idf * tf * (k1 + 1) / (tf + norm)
    return scores


def boolean_search(index, query_terms, mode="OR"):
    """
    Boolean retrieval — returns a set of doc_ids (unranked).
    mode="AND" → every term must be present
    mode="OR"  → at least one term present
    """
    if not query_terms:
        return set()
    sets = [set(index.postings.get(t, {}).keys()) for t in set(query_terms)]
    if mode == "AND":
        result = sets[0]
        for s in sets[1:]:
            result = result & s
    else:                          # OR
        result = set()
        for s in sets:
            result |= s
    return result


# ══════════════════════════════════════════════════════════
#  PART 4 ── LOAD DOCUMENTS FROM FOLDER
# ══════════════════════════════════════════════════════════

def load_documents(folder):
    """
    Read every .txt file in folder.
    Expected format:
        Title: <title on first line>
        <body text...>
    Returns list of (doc_id, title, body_text).
    """
    docs = []
    files = sorted(f for f in os.listdir(folder) if f.endswith(".txt"))
    for i, fname in enumerate(files, start=1):
        path = os.path.join(folder, fname)
        with open(path, encoding="utf-8") as f:
            lines = f.read().strip().splitlines()
        title = fname.replace(".txt", "").replace("_", " ")
        body  = []
        for line in lines:
            if line.lower().startswith("title:"):
                title = line.split(":", 1)[1].strip()
            else:
                body.append(line)
        docs.append((i, title, " ".join(body)))
    return docs


# ══════════════════════════════════════════════════════════
#  PART 5 ── BUILD THE INDEX
# ══════════════════════════════════════════════════════════

def build_index(folder):
    index = InvertedIndex()
    docs  = load_documents(folder)
    for doc_id, title, text in docs:
        index.add_document(doc_id, title, text)
    index.finalize()
    return index, docs


# ══════════════════════════════════════════════════════════
#  PART 6 ── SEARCH FUNCTION
# ══════════════════════════════════════════════════════════

def search(index, query, model="bm25", top_k=5):
    """
    Process query → preprocess → rank → return top_k results.

    Returns list of dicts:
        rank, doc_id, title, score, matched_terms, snippet
    """
    query_terms = preprocess(query)

    if not query_terms:
        return []

    # Score documents
    if model == "tfidf":
        scores = tfidf_rank(index, query_terms)
    elif model == "boolean":
        matched = boolean_search(index, query_terms, mode="OR")
        scores  = {d: 1.0 for d in matched}
    else:          # default: bm25
        scores = bm25_rank(index, query_terms)

    # Sort by score descending
    ranked = sorted(scores.items(), key=lambda x: -x[1])

    results = []
    for rank, (doc_id, score) in enumerate(ranked[:top_k], start=1):
        info = index.doc_info[doc_id]
        # which query terms matched?
        matched = [t for t in set(query_terms)
                   if t in index.postings and doc_id in index.postings[t]]
        # short snippet around first match
        words  = info["text"].split()
        snippet = " ".join(words[:20]) + ("..." if len(words) > 20 else "")
        results.append({
            "rank":    rank,
            "doc_id":  doc_id,
            "title":   info["title"],
            "score":   round(score, 4),
            "matched": matched,
            "snippet": snippet,
        })
    return results


# ══════════════════════════════════════════════════════════
#  PART 7 ── DISPLAY HELPERS
# ══════════════════════════════════════════════════════════

SEP  = "─" * 65
SEP2 = "═" * 65

def print_results(results, query, model):
    print(f"\n  Query : \"{query}\"")
    print(f"  Model : {model.upper()}")
    print(f"  Hits  : {len(results)}")
    print(SEP)
    if not results:
        print("  No matching documents found.")
        return
    for r in results:
        print(f"  [{r['rank']}] {r['title']}")
        print(f"      Score   : {r['score']}")
        print(f"      Matched : {r['matched']}")
        print(f"      Snippet : {r['snippet']}")
        print()


def show_index_stats(index):
    print(SEP2)
    print("  INVERTED INDEX STATISTICS")
    print(SEP2)
    print(f"  Total documents : {index.N}")
    print(f"  Unique terms    : {len(index.postings)}")
    print(f"  Avg doc length  : {index.avg_doc_len:.1f} tokens")
    print()
    # Show a sample of the index (top 10 most frequent terms)
    freq = {t: sum(index.postings[t].values()) for t in index.postings}
    top10 = sorted(freq.items(), key=lambda x: -x[1])[:10]
    print("  Top 10 terms in collection:")
    print(f"  {'Term':<18} {'Doc Freq':>9} {'Total TF':>10}  {'IDF':>8}")
    print("  " + "-" * 52)
    for term, total_tf in top10:
        print(f"  {term:<18} {index.df(term):>9} {total_tf:>10}  {index.idf(term):>8.4f}")
    print()
    # Show postings for one interesting term
    sample_term = "retriev"
    plist = index.postings.get(sample_term, {})
    print(f"  Postings list for term '{sample_term}':")
    print(f"  {{'doc_id': tf}}  =  {dict(sorted(plist.items()))}")
    print()


# ══════════════════════════════════════════════════════════
#  PART 8 ── MAIN DEMO  (runs all three models on 5 queries)
# ══════════════════════════════════════════════════════════

DEMO_QUERIES = [
    "information retrieval indexing",
    "TF-IDF term frequency ranking",
    "BM25 ranking algorithm length normalization",
    "precision recall evaluation",
    "web crawling search engine index",
]

def main():
    # ── Load & Index ─────────────────────────────────────
    folder = os.path.join(os.path.dirname(__file__), "documents")
    print(SEP2)
    print("  WEEK 1 — SIMPLE DOCUMENT SEARCH ENGINE")
    print(SEP2)
    print(f"\n  Loading documents from: {folder}")

    index, docs = build_index(folder)

    print(f"\n  Loaded {len(docs)} documents:")
    for doc_id, title, _ in docs:
        print(f"    [{doc_id:2}] {title}")

    # ── Show index statistics ─────────────────────────────
    print()
    show_index_stats(index)

    # ── Preprocessing demo ────────────────────────────────
    print(SEP2)
    print("  PREPROCESSING PIPELINE DEMO")
    print(SEP2)
    sample = "information retrieval systems rank documents"
    raw_tokens  = tokenize(sample)
    no_stop     = remove_stopwords(raw_tokens)
    stemmed     = [stem(t) for t in no_stop]
    print(f"\n  Input    : \"{sample}\"")
    print(f"  Tokens   : {raw_tokens}")
    print(f"  No stops : {no_stop}")
    print(f"  Stems    : {stemmed}")
    print()

    # ── Run all 3 models on all demo queries ──────────────
    for model in ["boolean", "tfidf", "bm25"]:
        print(SEP2)
        print(f"  MODEL: {model.upper()}")
        print(SEP2)
        for q in DEMO_QUERIES:
            results = search(index, q, model=model, top_k=3)
            print_results(results, q, model)

    # ── Interactive mode ──────────────────────────────────
    print(SEP2)
    print("  INTERACTIVE SEARCH (type 'quit' to exit)")
    print(SEP2)
    print("  Available models: bm25 | tfidf | boolean")
    print()
    while True:
        q = input("  Enter query : ").strip()
        if q.lower() in ("quit", "exit", "q"):
            print("  Goodbye!")
            break
        if not q:
            continue
        m = input("  Model [bm25]: ").strip().lower() or "bm25"
        if m not in ("bm25", "tfidf", "boolean"):
            m = "bm25"
        results = search(index, q, model=m, top_k=5)
        print_results(results, q, m)


if __name__ == "__main__":
    main()
