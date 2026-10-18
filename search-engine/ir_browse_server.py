"""IR FYP Browse Server — All 10 features from the IR Development Focus diagram.

Features:
  1. Category Menu       — organise docs by category / subcategory
  2. Search + Browse     — BM25 search and browse collections
  3. Breadcrumb Path     — path context for current location
  4. Related Documents   — BM25-ranked related docs with same-cat boost
  5. Recently Viewed     — client-side, served via API stub
  6. Filters             — type, category, keyword filters
  7. Navigation History  — client-side back/forward via sessionStorage
  8. Document Preview    — abstract snippet before opening
  9. Internal Links      — keyword-hit-based links inside documents
 10. User-Friendly UI    — clean responsive black/yellow SPA

Run:
    python ir_browse_server.py
    → http://localhost:9090/
"""

import json
import math
import os
import re
import sys
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

# ── backend path injection ───────────────────────────────────────────────────
_HERE    = os.path.dirname(os.path.abspath(__file__))
_BACKEND = os.path.join(_HERE, "backend")
_SRC     = os.path.join(_HERE, "src")
sys.path.insert(0, _BACKEND)
sys.path.insert(0, _SRC)

from indexer import InvertedIndex, load_or_build   # noqa: E402
from engine  import SearchEngine                   # noqa: E402
from preprocess import STOPWORDS                   # noqa: E402

# ── paths ────────────────────────────────────────────────────────────────────
DATA_DIR    = os.path.join(_HERE, "data")
DOCS_JSON   = os.path.join(DATA_DIR, "documents.json")
INDEX_PATH  = os.path.join(_HERE, "index", "ir_browse_index.json")
STATIC_HTML = os.path.join(_HERE, "ir_browse.html")
PORT        = 9090

# ── subcategory keyword map ───────────────────────────────────────────────────
SUBCAT_KEYWORDS = {
    "AI": {
        "NLP":                    ["natural language", "transformer", "sentiment", "text"],
        "Computer Vision":        ["image", "convolutional", "vision", "visual", "radiograph"],
        "Reinforcement Learning": ["reinforcement", "autonomous", "agent", "policy"],
        "Generative Models":      ["generative", "adversarial", "gan", "synthesize"],
    },
    "Cybersecurity": {
        "Intrusion Detection": ["intrusion", "malicious", "anomaly"],
        "Cryptography":        ["encrypt", "cipher", "cryptograph", "quantum"],
        "Vulnerability":       ["vulnerability", "exploit", "patch"],
    },
    "Healthcare": {
        "Medical Imaging":  ["radiograph", "medical image", "diagnosis", "scan"],
        "Clinical NLP":     ["clinical", "ehr", "patient record"],
        "Drug Discovery":   ["drug", "molecule", "pharmacol"],
    },
    "Databases": {
        "Relational":          ["sql", "relational", "transaction"],
        "NoSQL":               ["nosql", "document store", "key-value"],
        "Query Optimization":  ["query optim", "execution plan", "index"],
    },
    "SoftwareEngineering": {
        "Testing":       ["test", "bug", "defect", "coverage"],
        "DevOps":        ["ci", "cd", "deploy", "pipeline"],
        "Code Analysis": ["static analysis", "code review", "refactor"],
    },
    "IR": {
        "Ranking Models": ["bm25", "tf-idf", "ranking", "retrieval model"],
        "Indexing":       ["inverted index", "posting", "index"],
        "Evaluation":     ["precision", "recall", "ndcg", "mrr", "benchmark"],
    },
}

SAME_CAT_BOOST  = 1.5
MIN_KW_LEN      = 3
MAX_LINKS       = 5
MAX_RELATED     = 5


# ── helpers ──────────────────────────────────────────────────────────────────
def _derive_subcat(title: str, category: str):
    lo = title.lower()
    for sub, kws in SUBCAT_KEYWORDS.get(category, {}).items():
        if any(kw in lo for kw in kws):
            return sub
    return None


def _ext_map_from_data(data_dir: str) -> dict:
    m = {}
    for name in os.listdir(data_dir):
        stem, ext = os.path.splitext(name)
        ext = ext.lstrip(".").lower()
        if ext not in ("txt", "json", "csv", "xml"):
            continue
        prefix = stem.split("_")[0]
        if prefix.isdigit():
            m[int(prefix)] = ext
    return m


def _strip(doc: dict) -> dict:
    return {
        "id":          doc["id"],
        "title":       doc.get("title", ""),
        "abstract":    doc.get("abstract", ""),
        "category":    doc.get("category", ""),
        "subcategory": doc.get("subcategory"),
        "file_type":   doc.get("file_type", "txt"),
    }


# ── engine initialisation ────────────────────────────────────────────────────
class IRBrowseEngine:
    def __init__(self):
        print("  Loading corpus…")
        with open(DOCS_JSON, encoding="utf-8") as fh:
            raw = json.load(fh)

        ext_map = _ext_map_from_data(DATA_DIR)
        self._docs: list = []
        self._by_id: dict = {}

        for d in raw:
            d = dict(d)
            doc_id = int(d["id"])
            d["id"]         = doc_id
            d["file_type"]  = ext_map.get(doc_id, "txt")
            d["subcategory"]= _derive_subcat(d.get("title",""), d.get("category",""))
            self._docs.append(d)
            self._by_id[doc_id] = d

        print("  Building / loading index…")
        self._index  = load_or_build(DATA_DIR, INDEX_PATH)
        self._engine = SearchEngine(self._index)
        print(f"  Ready — {len(self._docs)} documents indexed.")

    # ── 1. Category tree ────────────────────────────────────────────────────
    def category_tree(self) -> dict:
        tree = {cat: {"doc_count": 0, "subcategories": {}} for cat in SUBCAT_KEYWORDS}
        for doc in self._docs:
            cat = doc.get("category", "")
            if cat not in tree:
                tree[cat] = {"doc_count": 0, "subcategories": {}}
            tree[cat]["doc_count"] += 1
            bucket = doc.get("subcategory") or "_unclassified"
            sc = tree[cat]["subcategories"]
            if bucket not in sc:
                sc[bucket] = {"doc_count": 0, "docs": []}
            sc[bucket]["doc_count"] += 1
            sc[bucket]["docs"].append(_strip(doc))
        return tree

    # ── 2. Browse ───────────────────────────────────────────────────────────
    def browse(self, cat="", sub="") -> list:
        out = []
        for doc in self._docs:
            if cat and doc.get("category","") != cat:
                continue
            if sub:
                derived = _derive_subcat(doc.get("title",""), doc.get("category",""))
                if sub == "_unclassified":
                    if derived is not None: continue
                else:
                    if derived != sub: continue
            out.append(_strip(doc))
        return out

    # ── 2. Search ───────────────────────────────────────────────────────────
    def search(self, query: str, cat="", file_type="", author="",
               date_from="", date_to="", k=10) -> dict:
        raw   = self._engine.search(query, model="bm25", k=100)
        hits  = []
        for hit in raw["hits"]:
            doc = self._by_id.get(hit["id"])
            if not doc:
                continue
            if cat       and doc.get("category","")  != cat:        continue
            if file_type and doc.get("file_type","txt") != file_type: continue
            if author    and author.lower() not in doc.get("title","").lower(): continue
            h = dict(hit)
            h["category"]    = doc.get("category","")
            h["subcategory"] = doc.get("subcategory")
            h["file_type"]   = doc.get("file_type","txt")
            h["abstract"]    = doc.get("abstract","")
            hits.append(h)
            if len(hits) >= k: break
        return {"hits": hits, "total": len(hits), "query": query}

    # ── 4. Related documents ─────────────────────────────────────────────────
    def related_docs(self, doc_id: int, n=MAX_RELATED) -> list:
        src = self._by_id.get(doc_id)
        if not src: return []
        q    = src["title"] + " " + src.get("abstract","")
        raw  = self._engine.search(q, model="bm25", k=len(self._docs))
        out  = []
        for hit in raw["hits"]:
            if hit["id"] == doc_id: continue
            d      = self._by_id.get(hit["id"])
            if not d: continue
            same   = d["category"] == src["category"]
            score  = round(hit["score"] * (SAME_CAT_BOOST if same else 1.0), 4)
            out.append({"id": hit["id"], "title": d["title"],
                        "score": score, "same_category": same,
                        "abstract": d.get("abstract","")[:200]})
        out.sort(key=lambda x: -x["score"])
        return out[:n]

    # ── 9. Internal links ────────────────────────────────────────────────────
    def internal_links(self, doc_id: int) -> list:
        src = self._by_id.get(doc_id)
        if not src: return []
        related_ids = {r["id"] for r in self.related_docs(doc_id)}
        pool = {
            d["id"] for d in self._docs
            if d["category"] == src["category"] or d["id"] in related_ids
        }
        pool.discard(doc_id)
        full = " ".join([
            src.get("title",""),
            src.get("abstract",""),
            src.get("methodology",""),
            src.get("results",""),
        ]).lower()
        matches = []
        for cid in pool:
            cand  = self._by_id[cid]
            words = [w for w in cand["title"].lower().split()
                     if len(w) >= MIN_KW_LEN and w not in STOPWORDS]
            hits  = sum(1 for w in words if w in full)
            if hits:
                matches.append({"id": cid, "title": cand["title"], "hits": hits})
        matches.sort(key=lambda x: -x["hits"])
        return matches[:MAX_LINKS]

    # ── Full document ────────────────────────────────────────────────────────
    def document(self, doc_id: int):
        src = self._by_id.get(doc_id)
        if not src: return None
        return {
            "id":             src["id"],
            "title":          src.get("title",""),
            "abstract":       src.get("abstract",""),
            "methodology":    src.get("methodology",""),
            "results":        src.get("results",""),
            "category":       src.get("category",""),
            "subcategory":    src.get("subcategory"),
            "file_type":      src.get("file_type","txt"),
            "related":        self.related_docs(doc_id),
            "internal_links": self.internal_links(doc_id),
        }

    # ── Stats ────────────────────────────────────────────────────────────────
    def stats(self) -> dict:
        return {
            "doc_count":  len(self._docs),
            "categories": list(SUBCAT_KEYWORDS.keys()),
            "indexed":    self._index is not None,
        }


# ── HTTP handler ─────────────────────────────────────────────────────────────
ENGINE: IRBrowseEngine = None


class Handler(BaseHTTPRequestHandler):

    def _json(self, status: int, body):
        data = json.dumps(body, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)

    def _html(self):
        try:
            with open(STATIC_HTML, "rb") as fh:
                data = fh.read()
        except OSError:
            self._json(404, {"error": "ir_browse.html not found"})
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        url    = urlparse(self.path)
        params = {k: v[0] for k, v in parse_qs(url.query).items()}
        path   = url.path

        if path in ("/", "/index.html", "/ir_browse.html"):
            return self._html()

        elif path == "/api/categories":
            return self._json(200, ENGINE.category_tree())

        elif path == "/api/browse":
            return self._json(200, ENGINE.browse(
                params.get("cat",""), params.get("sub","")))

        elif path == "/api/search":
            q = params.get("q","").strip()[:300]
            if not q:
                return self._json(400, {"error": "Missing q"})
            return self._json(200, ENGINE.search(
                q,
                cat       = params.get("cat",""),
                file_type = params.get("type",""),
                author    = params.get("author",""),
                k         = int(params.get("k","15")),
            ))

        elif path == "/api/doc":
            try:
                doc_id = int(params.get("id","0"))
            except ValueError:
                return self._json(400, {"error": "Invalid id"})
            result = ENGINE.document(doc_id)
            if result is None:
                return self._json(404, {"error": "Not found"})
            return self._json(200, result)

        elif path == "/api/stats":
            return self._json(200, ENGINE.stats())

        else:
            self._json(404, {"error": "Not found"})

    def log_message(self, fmt, *args):
        print(f"  {self.address_string()}  {fmt % args}")


# ── entry point ──────────────────────────────────────────────────────────────
def main():
    global ENGINE
    print("\n╔══════════════════════════════════════╗")
    print("║   IR FYP Browse Server — starting   ║")
    print("╚══════════════════════════════════════╝\n")
    ENGINE = IRBrowseEngine()
    print(f"\n→  Open  http://localhost:{PORT}/  in your browser\n")
    with ThreadingHTTPServer(("", PORT), Handler) as srv:
        try:
            srv.serve_forever()
        except KeyboardInterrupt:
            print("\nServer stopped.")


if __name__ == "__main__":
    main()
