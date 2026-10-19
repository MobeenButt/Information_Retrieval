"""BrowseEngine — domain logic layer for the Browsing and Navigation Module.

Imports InvertedIndex, SearchEngine, and STOPWORDS from the existing backend
via sys.path injection. The engine is never modified; all new logic lives here.
"""
import json
import os
import sys

# --- sys.path injection (backend reuse) ---
_HERE = os.path.dirname(os.path.abspath(__file__))
_BACKEND = os.path.join(_HERE, "..", "search-engine", "backend")
sys.path.insert(0, _BACKEND)

from indexer import InvertedIndex  # noqa: E402
from engine import SearchEngine                    # noqa: E402
from preprocess import STOPWORDS, tokenize         # noqa: E402

# ---------------------------------------------------------------------------
# File / path constants
# ---------------------------------------------------------------------------
DOCUMENTS_JSON = os.path.join(_HERE, "..", "search-engine", "data", "documents.json")
DATA_DIR = os.path.join(_HERE, "..", "search-engine", "data")

# ---------------------------------------------------------------------------
# Subcategory keyword map — used by _derive_subcategory()
# ---------------------------------------------------------------------------
SUBCAT_KEYWORDS: dict = {
    "AI": {
        "NLP":                   ["natural language", "transformer", "sentiment", "text"],
        "Computer Vision":       ["image", "convolutional", "vision", "visual", "radiograph"],
        "Reinforcement Learning": ["reinforcement", "autonomous", "agent", "policy"],
        "Generative Models":     ["generative", "adversarial", "gan", "synthesize"],
    },
    "Cybersecurity": {
        "Intrusion Detection":   ["intrusion", "malicious", "anomaly"],
        "Cryptography":          ["encrypt", "cipher", "cryptograph"],
        "Vulnerability":         ["vulnerability", "exploit", "patch"],
    },
    "Healthcare": {
        "Medical Imaging":       ["radiograph", "medical image", "diagnosis", "scan"],
        "Clinical NLP":          ["clinical", "ehr", "patient record"],
        "Drug Discovery":        ["drug", "molecule", "pharmacol"],
    },
    "Databases": {
        "Relational":            ["sql", "relational", "transaction"],
        "NoSQL":                 ["nosql", "document store", "key-value"],
        "Query Optimization":    ["query optim", "execution plan", "index"],
    },
    "SoftwareEngineering": {
        "Testing":               ["test", "bug", "defect", "coverage"],
        "DevOps":                ["ci", "cd", "deploy", "pipeline"],
        "Code Analysis":         ["static analysis", "code review", "refactor"],
    },
    "IR": {
        "Ranking Models":        ["bm25", "tf-idf", "ranking", "retrieval model"],
        "Indexing":              ["inverted index", "posting", "index"],
        "Evaluation":            ["precision", "recall", "ndcg", "mrr", "benchmark"],
    },
}

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SAME_CAT_BOOST = 1.5
MIN_KEYWORD_LEN = 3
MAX_LINKS = 5
COMPARE_MODELS = ("bm25", "tfidf", "boolean", "overlap", "nonoverlap", "bim", "proximal")


def _metadata_values(doc: dict, keys: tuple) -> list:
    """Return scalar text values for any matching metadata keys."""
    values = []
    for key, value in doc.items():
        if key.lower() not in keys or value is None:
            continue
        candidates = value if isinstance(value, (list, tuple, set)) else [value]
        values.extend(str(candidate).strip() for candidate in candidates if candidate is not None)
    return [value for value in values if value]


def _metadata_matches(doc: dict, query: str, keys: tuple) -> bool:
    """Match a metadata filter against scalar or collection-valued fields."""
    if not query:
        return True
    needle = query.strip().casefold()
    return any(needle in value.casefold() for value in _metadata_values(doc, keys))


def _matches_date(doc: dict, date: str) -> bool:
    if not date:
        return True
    requested = date.strip()
    for value in _metadata_values(
        doc, ("date", "publication_date", "published", "published_at",
              "publication_year", "year", "created_at")
    ):
        normalized = value[:10]
        if normalized == requested or (
            len(normalized) == 4 and requested.startswith(normalized)
        ):
            return True
    return False


def _topic_matches(doc: dict, topic: str) -> bool:
    if not topic:
        return True
    # The current corpus uses category and title as its only topic metadata.
    keys = ("topic", "topics", "tag", "tags", "category", "subcategory", "title")
    return _metadata_matches(doc, topic, keys)


def _one_edit_apart(left: str, right: str) -> bool:
    """Return whether two terms differ by exactly one insertion/deletion/substitution."""
    if abs(len(left) - len(right)) > 1:
        return False

    short, long = sorted((left, right), key=len)
    short_index = long_index = edits = 0
    while short_index < len(short) and long_index < len(long):
        if short[short_index] == long[long_index]:
            short_index += 1
            long_index += 1
            continue
        edits += 1
        if edits > 1:
            return False
        if len(short) == len(long):
            short_index += 1
        long_index += 1

    edits += len(long) - long_index
    return edits == 1


def _correct_query(query: str, vocabulary: set) -> str:
    """Correct unknown words only when each has one unambiguous one-edit match."""
    corrected = []
    changed = False
    for token in tokenize(query):
        if token in vocabulary or len(token) < 5:
            corrected.append(token)
            continue
        candidates = [
            term for term in vocabulary
            if _one_edit_apart(token, term)
        ]
        if len(candidates) != 1:
            return query
        corrected.append(candidates[0])
        changed = True
    return " ".join(corrected) if changed else query


def _derive_subcategory(title: str, category: str):
    """Return the first matching subcategory label for *title*, or None."""
    lower = title.lower()
    for subcat, keywords in SUBCAT_KEYWORDS.get(category, {}).items():
        if any(kw in lower for kw in keywords):
            return subcat
    return None


def _strip_doc(doc: dict) -> dict:
    """Return a lightweight copy of *doc* safe for JSON API responses."""
    return {
        "id":          doc.get("id"),
        "title":       doc.get("title", ""),
        "abstract":    doc.get("abstract", ""),
        "category":    doc.get("category", ""),
        "file_type":   doc.get("file_type", "txt"),
        "subcategory": doc.get("subcategory"),
        "date":        next(iter(_metadata_values(
            doc, ("date", "publication_date", "published", "published_at",
                  "publication_year", "year", "created_at")
        )), None),
        "author":      next(iter(_metadata_values(
            doc, ("author", "authors", "creator", "creators")
        )), None),
        "language":    next(iter(_metadata_values(
            doc, ("language", "lang")
        )), None),
        "topic":       next(iter(_metadata_values(
            doc, ("topic", "topics", "tag", "tags")
        )), None),
    }


class BrowseEngine:
    """Domain logic for browsing, searching, related-doc discovery, and internal links.

    Full implementation delivered across Tasks 2–6.
    """

    def __init__(self):
        """Load the primary corpus, build/reuse the inverted index, and derive metadata."""
        # ── 1. Resolve and validate documents.json ──────────────────────────
        docs_path = os.path.normpath(DOCUMENTS_JSON)
        if not os.path.isfile(docs_path):
            raise FileNotFoundError(
                f"Primary corpus not found: {docs_path}\n"
                "Expected documents.json inside search-engine/data/."
            )

        # ── 2. Load primary corpus ──────────────────────────────────────────
        with open(docs_path, encoding="utf-8") as fh:
            raw_docs: list = json.load(fh)

        # ── 3. Derive file_type for every document from the supporting corpus ──
        # Scan the data directory for supported files and build an id->file_type
        # mapping using the numeric prefix in each filename (01_ → 1, etc.).
        _ext_map: dict[int, str] = {}
        if os.path.isdir(DATA_DIR):
            for name in os.listdir(DATA_DIR):
                stem, ext = os.path.splitext(name)
                ext = ext.lstrip(".").lower()
                if ext not in ("txt", "json", "csv", "xml"):
                    continue
                # numeric prefix before the first underscore, e.g. "01" → 1
                prefix = stem.split("_")[0]
                if prefix.isdigit():
                    _ext_map[int(prefix)] = ext

        # ── 4. Attach derived fields (subcategory, file_type) ───────────────
        self._docs: list = []
        self._docs_by_id: dict = {}
        for doc in raw_docs:
            doc = dict(doc)  # shallow copy — do not mutate the parsed list
            doc_id = int(doc["id"])
            doc["id"] = doc_id
            # file_type: use the supporting-corpus mapping; fall back to "txt"
            doc["file_type"] = _ext_map.get(doc_id, "txt")
            # subcategory: derived from title + category
            doc["subcategory"] = _derive_subcategory(
                doc.get("title", ""), doc.get("category", "")
            )
            self._docs.append(doc)
            self._docs_by_id[doc_id] = doc

        # ── 5. Build the search index from the same corpus exposed to the UI ──
        # The general search-engine data directory contains a separate corpus
        # whose numeric IDs do not correspond to documents.json.
        self._index = InvertedIndex()
        for doc in self._docs:
            text = " ".join(
                doc.get(field, "")
                for field in ("abstract", "methodology", "results")
                if doc.get(field)
            )
            self._index.add_document(
                doc["id"],
                doc.get("title", ""),
                text,
                source=str(doc["id"]),
                file_type=doc.get("file_type", "txt"),
            )
        self._index.finalize()

        # ── 6. Instantiate the search engine ────────────────────────────────
        self._engine: SearchEngine = SearchEngine(self._index)

    # ------------------------------------------------------------------
    # Public API (stubs — implemented in later tasks)
    # ------------------------------------------------------------------

    def category_tree(self) -> dict:
        """Return a hierarchical category tree for all six known categories.

        Structure::

            {
              "AI": {
                "doc_count": 8,
                "subcategories": {
                  "NLP": {"doc_count": 2, "docs": [{"id": 2, "title": "..."}, ...]},
                  "_unclassified": {"doc_count": 1, "docs": [...]}
                }
              },
              ...
            }

        All six categories from SUBCAT_KEYWORDS are always present, even if they
        contain zero documents.  Documents that match no subcategory keyword are
        placed under the ``_unclassified`` bucket.
        """
        # Pre-seed all six known categories so they're always present in output.
        tree: dict = {}
        for cat in SUBCAT_KEYWORDS:
            tree[cat] = {"doc_count": 0, "subcategories": {}}

        for doc in self._docs:
            cat = doc.get("category", "")
            if cat not in tree:
                # Unknown category not in SUBCAT_KEYWORDS — add it dynamically.
                tree[cat] = {"doc_count": 0, "subcategories": {}}

            tree[cat]["doc_count"] += 1

            subcat = doc.get("subcategory")          # already derived in __init__
            bucket = subcat if subcat is not None else "_unclassified"

            subcats = tree[cat]["subcategories"]
            if bucket not in subcats:
                subcats[bucket] = {"doc_count": 0, "docs": []}
            subcats[bucket]["doc_count"] += 1
            subcats[bucket]["docs"].append(_strip_doc(doc))

        return tree

    def browse(self, cat: str = "", sub: str = "") -> list:
        """Return stripped doc dicts matching the given category and optional subcategory.

        - When *cat* is non-empty, only documents whose ``category`` equals *cat* are
          included.  An unknown *cat* value simply produces an empty list.
        - When *sub* is ``"_unclassified"``, only documents whose derived subcategory is
          ``None`` (i.e. no keyword matched) are included.
        - When *sub* is any other non-empty string, only documents whose derived
          subcategory equals *sub* are included.
        - When both *cat* and *sub* are empty, all documents are returned.
        """
        results = []
        for doc in self._docs:
            # --- Category filter ---
            if cat and doc.get("category", "") != cat:
                continue

            # --- Subcategory filter ---
            if sub:
                derived = _derive_subcategory(doc.get("title", ""), doc.get("category", ""))
                if sub == "_unclassified":
                    # include only docs that have no matching subcategory
                    if derived is not None:
                        continue
                else:
                    # include only docs whose derived subcategory matches sub
                    if derived != sub:
                        continue

            results.append(_strip_doc(doc))

        return results

    def search(
        self, query: str, cat: str = "", file_type: str = "", k: int = 10,
        date: str = "", author: str = "", topic: str = "", language: str = "",
        sub: str = "",
    ) -> dict:
        """BM25 search with optional category, file type, and metadata filters.

        Retrieves all indexed candidates before applying filters so matching
        documents are not lost when a filter excludes high-ranking results.

        Returns
        -------
        dict
            ``{"hits": [...], "total": int, ...}`` — the original engine
            response dict with ``hits`` and ``total`` replaced.

        HTTP 400 / empty-query guard is handled by the caller (app.py) before
        this method is invoked; this method does not need to raise on empty query.
        """
        raw = self._engine.search(
            query, model="bm25", k=max(len(self._docs), len(self._index.docs))
        )
        corrected_query = query
        if not raw["hits"]:
            corrected_query = _correct_query(query, set(self._index.postings))
            if corrected_query != query:
                corrected_results = self._engine.search(
                    corrected_query,
                    model="bm25",
                    k=max(len(self._docs), len(self._index.docs)),
                )
                if corrected_results["hits"]:
                    raw = corrected_results

        hits = []
        for hit in raw["hits"]:
            doc = self._docs_by_id.get(hit["id"])
            if not doc:
                continue
            # Post-filter by category
            if cat and doc.get("category", "") != cat:
                continue
            if sub and (doc.get("subcategory") or "_unclassified") != sub:
                continue
            # Post-filter by file_type
            if file_type and doc.get("file_type", "txt") != file_type:
                continue
            if not _matches_date(doc, date):
                continue
            if not _metadata_matches(
                doc, author, ("author", "authors", "creator", "creators")
            ):
                continue
            if not _topic_matches(doc, topic):
                continue
            if not _metadata_matches(doc, language, ("language", "lang")):
                continue
            # Attach metadata fields
            hit = dict(hit)  # shallow copy — do not mutate the engine's list
            hit["category"] = doc.get("category", "")
            hit["file_type"] = doc.get("file_type", "txt")
            hit.update(_strip_doc(doc))
            hits.append(hit)
            if len(hits) >= k:
                break
        raw = dict(raw)  # shallow copy of the top-level response
        raw["query"] = query
        if corrected_query != query and raw["hits"]:
            raw["corrected_query"] = corrected_query
        raw["hits"] = hits
        raw["total"] = len(hits)
        return raw

    def compare(self, query: str, models: list, k: int = 10) -> dict:
        """Run the existing search engine for each selected model and add corpus metadata."""
        selected = list(dict.fromkeys(models))
        if not selected or any(model not in COMPARE_MODELS for model in selected):
            raise ValueError("Select at least one supported model.")

        results = {}
        for model in selected:
            raw = self._engine.search(query, model=model, k=k)
            hits = []
            for rank, item in enumerate(raw.get("hits", []), start=1):
                doc = self._docs_by_id.get(item["id"])
                if not doc:
                    continue
                hit = dict(item)
                hit["rank"] = rank
                hit["category"] = doc.get("category", "")
                hit["subcategory"] = doc.get("subcategory")
                hit["file_type"] = doc.get("file_type", "txt")
                hits.append(hit)
            results[model] = {
                "hits": hits,
                "total": raw.get("total", len(hits)),
                "took_ms": raw.get("took_ms", 0),
            }
        return {"query": query, "models": selected, "results": results}

    def related_docs(self, doc_id: int, n: int = 5) -> list:
        """Return up to *n* documents related to *doc_id*.

        Uses the source document's ``title + abstract`` as a BM25 query,
        excludes the source document from results, and boosts documents in the
        same category by ``SAME_CAT_BOOST`` (1.5×) before re-ranking.

        Returns
        -------
        list
            Each element is a hit dict augmented with a ``same_category`` bool
            and a re-scored ``score``.  Returns ``[]`` for an unknown *doc_id*.
        """
        source = self._docs_by_id.get(doc_id)
        if not source:
            return []

        query = source["title"] + " " + source["abstract"]
        raw = self._engine.search(query, model="bm25", k=len(self._docs))

        boosted = []
        for hit in raw["hits"]:
            if hit["id"] == doc_id:
                continue  # exclude source document
            hit_doc = self._docs_by_id.get(hit["id"])
            if not hit_doc:
                continue  # skip indexed docs not present in corpus
            same_cat = hit_doc["category"] == source["category"]
            score = hit["score"] * (SAME_CAT_BOOST if same_cat else 1.0)
            boosted.append({**hit, "score": round(score, 4), "same_category": same_cat})

        boosted.sort(key=lambda x: -x["score"])
        return boosted[:n]

    def internal_links(self, doc_id: int) -> list:
        """Return up to MAX_LINKS documents that are good internal link targets.

        Candidate pool
        --------------
        The union of:
          - all documents in the same category as *doc_id*
          - all documents returned by :meth:`related_docs` for *doc_id*
        …with the source document itself excluded.

        Scoring
        -------
        Each candidate's title is tokenised (lowercased, split on whitespace).
        Tokens shorter than MIN_KEYWORD_LEN or present in STOPWORDS are ignored.
        The hit count is the number of surviving tokens found anywhere in the
        source document's full text (title + abstract + methodology + results).

        Only candidates with at least one hit are returned, sorted by hit count
        descending, truncated to MAX_LINKS entries.

        Returns
        -------
        list[dict]
            Each element is ``{"id": int, "title": str, "hits": int}``.
            Returns ``[]`` for an unknown *doc_id*.
        """
        source = self._docs_by_id.get(doc_id)
        if not source:
            return []

        # Build candidate pool: same-category docs ∪ related docs, minus source
        related_ids = {r["id"] for r in self.related_docs(doc_id)}
        allowed_ids = {
            d["id"] for d in self._docs
            if d["category"] == source["category"] or d["id"] in related_ids
        }
        allowed_ids.discard(doc_id)

        # Full text of the source document (lower-cased for substring matching)
        full_text = " ".join([
            source.get("title", ""),
            source.get("abstract", ""),
            source.get("methodology", ""),
            source.get("results", ""),
        ]).lower()

        matches = []
        for candidate_id in allowed_ids:
            cand = self._docs_by_id[candidate_id]
            # Tokenise candidate title; discard stopwords and short tokens
            words = [
                w for w in cand["title"].lower().split()
                if len(w) >= MIN_KEYWORD_LEN and w not in STOPWORDS
            ]
            hit_count = sum(1 for w in words if w in full_text)
            if hit_count > 0:
                matches.append({"id": candidate_id, "title": cand["title"], "hits": hit_count})

        matches.sort(key=lambda x: -x["hits"])
        return matches[:MAX_LINKS]

    def document(self, doc_id: int):
        """Return the full document response dict for *doc_id*, or ``None`` if unknown.

        The caller (app.py handler) is responsible for converting a ``None`` return
        value into an HTTP 404 response with ``{"error": "Not found"}``.

        Returns
        -------
        dict | None
            A dict with the shape::

                {
                  "id":             int,
                  "title":          str,
                  "abstract":       str,
                  "methodology":    str,
                  "results":        str,
                  "category":       str,
                  "subcategory":    str | None,
                  "file_type":      str,
                  "related":        list[dict],   # from related_docs()
                  "internal_links": list[dict],   # from internal_links()
                }

            ``None`` when *doc_id* is not present in the corpus.
        """
        source = self._docs_by_id.get(doc_id)
        if source is None:
            return None

        metadata = _strip_doc(source)
        return {
            "id":             source["id"],
            "title":          source.get("title", ""),
            "abstract":       source.get("abstract", ""),
            "methodology":    source.get("methodology", ""),
            "results":        source.get("results", ""),
            "category":       source.get("category", ""),
            "subcategory":    source.get("subcategory"),
            "file_type":      source.get("file_type", "txt"),
            "date":           metadata["date"],
            "author":         metadata["author"],
            "language":       metadata["language"],
            "topic":          metadata["topic"],
            "related":        self.related_docs(doc_id),
            "internal_links": self.internal_links(doc_id),
        }

    def stats(self) -> dict:
        """Placeholder — implemented in Task 7.5."""
        return {
            "doc_count":  len(self._docs),
            "categories": list(SUBCAT_KEYWORDS.keys()),
            "indexed":    self._index is not None,
        }
