"""Command-line search:  python backend/cli.py "inverted index" --model bm25 --mode all"""
import argparse
import os
import re

from engine import SearchEngine
from indexer import load_or_build

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

parser = argparse.ArgumentParser()
parser.add_argument("query")
parser.add_argument("--model", choices=["tfidf", "bm25"], default="tfidf")
parser.add_argument("--mode", choices=["any", "all"], default="any")
parser.add_argument("-k", type=int, default=5)
args = parser.parse_args()

engine = SearchEngine(load_or_build(os.path.join(ROOT, "data"),
                                    os.path.join(ROOT, "index", "index.json")))
res = engine.search(args.query, args.model, args.mode, args.k)
print(f"Query terms after processing: {res['trace']['stems']}  ({res['total']} matches, {res['took_ms']} ms)\n")
for rank, hit in enumerate(res["hits"], 1):
    print(f"{rank}. {hit['title']}  [score {hit['score']}]")
    print("   " + re.sub(r"</?mark>", "", hit["snippet"]) + "\n")
