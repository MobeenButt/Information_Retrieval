"""Smoke tests for BrowseEngine (Task 4 checkpoint).

Verifies:
  1. BrowseEngine() initialises without error.
  2. category_tree() returns exactly 6 top-level keys.
  3. browse(cat='AI') returns docs all with category=='AI'.
  4. search(query='neural network') returns hits in non-increasing score order.
  5. search(query='test', cat='IR') returns only IR-category docs.
  6. search metadata filters match optional date, author, topic, and language fields.
  7. an unambiguous one-character typo retries with the corrected query.
  8. search results map to and contain terms from their displayed corpus documents.

Run from the Week 5 directory:
    python test_browse_smoke.py
"""

import sys
import os
import traceback

# ── make sure we can import browse.py from this directory ──
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PASS = "\u2713 PASS"
FAIL = "\u2717 FAIL"
results = []


def check(label, condition, detail=""):
    status = PASS if condition else FAIL
    line = f"  {status}  {label}"
    if detail:
        line += f" — {detail}"
    print(line)
    results.append((label, condition))


# ──────────────────────────────────────────────────
# Test 1: BrowseEngine() initialises without error
# ──────────────────────────────────────────────────
engine = None
print("\nTest 1: BrowseEngine() initialises without error")
try:
    from browse import BrowseEngine
    engine = BrowseEngine()
    check("BrowseEngine initialised", True)
except Exception as exc:
    check("BrowseEngine initialised", False, str(exc))
    traceback.print_exc()

# All subsequent tests require the engine; skip them if init failed.
if engine is None:
    print("\n[SKIPPING tests 2-5: engine could not be created]\n")
    sys.exit(1)

# ──────────────────────────────────────────────────
# Test 2: category_tree() returns exactly 6 top-level keys
# ──────────────────────────────────────────────────
print("\nTest 2: category_tree() returns exactly 6 top-level keys")
try:
    tree = engine.category_tree()
    n_keys = len(tree)
    check(
        "category_tree has 6 top-level keys",
        n_keys == 6,
        f"found {n_keys}: {list(tree.keys())}"
    )
except Exception as exc:
    check("category_tree() did not raise", False, str(exc))
    traceback.print_exc()

# ──────────────────────────────────────────────────
# Test 3: browse(cat='AI') returns only AI docs
# ──────────────────────────────────────────────────
print("\nTest 3: browse(cat='AI') returns docs all with category=='AI'")
try:
    ai_docs = engine.browse(cat="AI")
    check(
        "browse(cat='AI') returns at least one doc",
        len(ai_docs) > 0,
        f"returned {len(ai_docs)} docs"
    )
    wrong = [d for d in ai_docs if d.get("category") != "AI"]
    check(
        "all returned docs have category=='AI'",
        len(wrong) == 0,
        f"{len(wrong)} docs had wrong category" if wrong else ""
    )
except Exception as exc:
    check("browse(cat='AI') did not raise", False, str(exc))
    traceback.print_exc()

# ──────────────────────────────────────────────────
# Test 4: search(query='neural network') hits are non-increasing by score
# ──────────────────────────────────────────────────
print("\nTest 4: search(query='neural network') hits are in non-increasing score order")
try:
    result = engine.search(query="neural network")
    hits = result.get("hits", [])
    check(
        "search returns at least one hit",
        len(hits) > 0,
        f"returned {len(hits)} hits"
    )
    scores = [h.get("score", 0) for h in hits]
    is_sorted = all(scores[i] >= scores[i + 1] for i in range(len(scores) - 1))
    check(
        "hits are in non-increasing score order",
        is_sorted,
        f"scores: {scores[:5]}{'...' if len(scores) > 5 else ''}"
    )
except Exception as exc:
    check("search('neural network') did not raise", False, str(exc))
    traceback.print_exc()

# ──────────────────────────────────────────────────
# Test 5: search(query='test', cat='IR') returns only IR docs
# ──────────────────────────────────────────────────
print("\nTest 5: search(query='test', cat='IR') returns only IR-category docs")
try:
    result = engine.search(query="test", cat="IR")
    hits = result.get("hits", [])
    # It's acceptable to have zero hits (no matching IR docs for 'test'),
    # but if there are hits they must all be IR.
    wrong = [h for h in hits if h.get("category") != "IR"]
    check(
        "all hits have category=='IR' (or no hits)",
        len(wrong) == 0,
        f"{len(wrong)} hits had wrong category; total hits: {len(hits)}"
    )
    check(
        "search with cat='IR' filter ran without error",
        True,
        f"returned {len(hits)} hit(s)"
    )
except Exception as exc:
    check("search('test', cat='IR') did not raise", False, str(exc))
    traceback.print_exc()

# ──────────────────────────────────────────────────
# Test 6: optional metadata filters
# ──────────────────────────────────────────────────
print("\nTest 6: search metadata filters match optional document fields")
try:
    # The bundled corpus has no publication metadata; add test-only metadata
    # to one indexed document to exercise the filter behavior.
    engine._docs_by_id[14].update({
        "publication_date": "2024-03-15",
        "authors": ["Alice Smith", "Bob Jones"],
        "topics": ["neural networks"],
        "lang": "en",
    })
    result = engine.search(
        query="cancer diagnosis",
        date="2024-03-15",
        author="alice",
        topic="networks",
        language="en",
    )
    hits = result.get("hits", [])
    check(
        "combined date/author/topic/language filters find the matching doc",
        len(hits) == 1 and hits[0].get("id") == 14,
        f"returned document ids: {[h.get('id') for h in hits]}"
    )
    check(
        "search hits include optional metadata",
        bool(hits) and hits[0].get("date") == "2024-03-15"
        and hits[0].get("author") == "Alice Smith"
        and hits[0].get("language") == "en",
        f"metadata: { {key: hits[0].get(key) for key in ('date', 'author', 'language')} if hits else {}}"
    )
    wrong_author = engine.search("cancer diagnosis", author="No Such Author")
    check(
        "metadata filters exclude non-matching documents",
        len(wrong_author.get("hits", [])) == 0,
        f"returned {len(wrong_author.get('hits', []))} hits"
    )
    topic_match = engine.search("cancer diagnosis", topic="Healthcare")
    check(
        "topic filter also matches existing category metadata",
        bool(topic_match.get("hits")),
        f"returned {len(topic_match.get('hits', []))} hits"
    )
except Exception as exc:
    check("metadata filters did not raise", False, str(exc))
    traceback.print_exc()

# ──────────────────────────────────────────────────
# Test 7: unambiguous typo correction
# ──────────────────────────────────────────────────
print("\nTest 7: search(query='neutral') retries as 'neural'")
try:
    result = engine.search(query="neutral")
    hits = result.get("hits", [])
    check(
        "misspelled query returns relevant hits",
        len(hits) > 0,
        f"returned {len(hits)} hits"
    )
    check(
        "response identifies the corrected query",
        result.get("query") == "neutral" and result.get("corrected_query") == "neural",
        f"query={result.get('query')!r}, corrected_query={result.get('corrected_query')!r}"
    )
    exact = engine.search(query="neural")
    check(
        "exact query does not report a correction",
        "corrected_query" not in exact,
        f"response keys: {list(exact)}"
    )
except Exception as exc:
    check("search typo correction did not raise", False, str(exc))
    traceback.print_exc()

# ──────────────────────────────────────────────────
# Test 8: search/index document mapping
# ──────────────────────────────────────────────────
print("\nTest 8: search results correspond to the displayed corpus")
try:
    result = engine.search(query="machine")
    hits = result.get("hits", [])
    mismatches = []
    for hit in hits:
        doc = engine._docs_by_id[hit["id"]]
        searchable_text = " ".join(
            doc.get(field, "")
            for field in ("title", "abstract", "methodology", "results")
        ).casefold()
        if "machine" not in searchable_text:
            mismatches.append(hit["id"])
    check(
        "every machine result contains the query in its displayed document",
        bool(hits) and not mismatches,
        f"{len(hits)} hits; mismatched ids: {mismatches}"
    )
    index_title_mismatches = [
        doc_id for doc_id, doc in engine._docs_by_id.items()
        if engine._index.docs[doc_id]["title"] != doc["title"]
    ]
    check(
        "index titles match the browse corpus by document id",
        not index_title_mismatches,
        f"mismatched ids: {index_title_mismatches}"
    )
except Exception as exc:
    check("search result mapping did not raise", False, str(exc))
    traceback.print_exc()

# ──────────────────────────────────────────────────
# Summary
# ──────────────────────────────────────────────────
passed = sum(1 for _, ok in results if ok)
total  = len(results)
print(f"\n{'='*50}")
print(f"  Results: {passed}/{total} passed")
print(f"{'='*50}\n")

if passed < total:
    sys.exit(1)
