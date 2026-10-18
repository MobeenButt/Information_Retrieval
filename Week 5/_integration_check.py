import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from browse import BrowseEngine

engine = BrowseEngine()

s = engine.stats()
print("stats:", s)
assert s["doc_count"] > 0
assert len(s["categories"]) == 6
assert s["indexed"] is True
print("stats() OK")

tree = engine.category_tree()
assert len(tree) == 6
print("category_tree() OK -", len(tree), "categories")

ai = engine.browse(cat="AI")
assert all(d["category"] == "AI" for d in ai)
print("browse(cat='AI') OK -", len(ai), "docs")

res = engine.search(query="neural")
hits = res["hits"]
if len(hits) > 1:
    for i in range(len(hits) - 1):
        assert hits[i]["score"] >= hits[i+1]["score"]
print("search(query='neural') OK -", len(hits), "hits")

doc = engine.document(1)
assert doc is not None
assert "related" in doc
assert "internal_links" in doc
print("document(1) OK - title:", doc.get("title", ""))

print("ALL INTEGRATION CHECKS PASSED")
