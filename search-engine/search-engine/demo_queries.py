"""Demo: run 5 queries through every retrieval model.

Query 4 ('best treatment for diabetes') prints the full BM25 walkthrough:
per-term tf, idf, length normalisation, term score, final score and ranked output.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from probabilistic_models import bm25_explain          # noqa: E402
from search_engine import SearchEngine                 # noqa: E402
from text_processing import preprocess                 # noqa: E402

QUERIES = [
    "machine learning intrusion detection",
    "neural network image classification",
    "information retrieval search ranking",
    "best treatment for diabetes",
    "bug investigation software repositories",
]

MODELS = [
    "boolean", "vsm", "bm25", "bim",
    "overlap", "nonoverlap", "proximal", "field_bm25",
]


def main() -> None:
    se = SearchEngine("data/documents.json", "index/structured_index.json")

    for qi, query in enumerate(QUERIES, 1):
        print("=" * 74)
        print(f"QUERY {qi}: {query!r}")
        print("=" * 74)

        for model in MODELS:
            result = se.search(query, model=model, top_k=3)
            print(f"\n--- {model:<11} | total={result['total']} | {result['took_ms']} ms ---")
            for hit in result["hits"]:
                title = hit.get("title", "")[:55]
                print(f"  #{hit['id']:>2}  score={hit['score']:.4f}  {title}")

        # Query 4: full per-term BM25 math walkthrough
        if qi == 4:
            print("\n" + "#" * 74)
            print("# FULL BM25 WALKTHROUGH for 'best treatment for diabetes'")
            print("#" * 74)
            idx = se.index
            terms = preprocess(query)
            result = se.search(query, model="bm25", top_k=5, show_math=True)
            for rank, hit in enumerate(result["hits"], 1):
                print(f"\n[Rank {rank}] doc {hit['id']}: {hit.get('title','')}")
                print("-" * 74)
                print(bm25_explain(terms, hit["id"], idx))

    print("\nAll 5 queries executed across 8 models.")


if __name__ == "__main__":
    main()
