"""Smoke tests for BrowseEngine (Task 4 checkpoint).

Verifies:
  1. BrowseEngine() initialises without error.
  2. category_tree() returns exactly 6 top-level keys.
  3. browse(cat='AI') returns docs all with category=='AI'.
  4. search(query='neural network') returns hits in non-increasing score order.
  5. search(query='test', cat='IR') returns only IR-category docs.

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
# Summary
# ──────────────────────────────────────────────────
passed = sum(1 for _, ok in results if ok)
total  = len(results)
print(f"\n{'='*50}")
print(f"  Results: {passed}/{total} passed")
print(f"{'='*50}\n")

if passed < total:
    sys.exit(1)
