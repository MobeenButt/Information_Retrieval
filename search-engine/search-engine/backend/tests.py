"""Run:  python backend/tests.py"""
import os
import unittest

from engine import SearchEngine
from indexer import InvertedIndex, build_index
from preprocess import preprocess, stem, tokenize

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")


class TextProcessing(unittest.TestCase):
    def test_tokenize(self):
        self.assertEqual(tokenize("Machine-Learning, 2020!"), ["machine", "learning", "2020"])

    def test_stemming(self):
        self.assertEqual(stem("running"), "run")
        self.assertEqual(stem("indexes"), "index")
        self.assertEqual(stem("queries"), "query")
        self.assertEqual(stem("computing"), stem("computed"))

    def test_pipeline_matches_deck_example(self):
        self.assertEqual(preprocess("machine learning"), ["machine", "learn"])
        self.assertEqual(preprocess("the cat is on the mat"), ["cat", "mat"])


class Index(unittest.TestCase):
    def test_postings_and_df(self):
        idx = InvertedIndex()
        idx.add_document(1, "A", "apple banana apple")
        idx.add_document(2, "B", "banana cherry")
        idx.finalize()
        self.assertEqual(idx.df("banana"), 2)
        self.assertEqual(idx.postings["apple"][1], 2)          # term frequency
        self.assertGreater(idx.idf("cherry"), idx.idf("banana"))  # rarer term, higher idf


class Search(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = SearchEngine(build_index(DATA))

    def top(self, q, **kw):
        return self.engine.search(q, **kw)["hits"][0]["title"]

    def test_expected_top_results(self):
        self.assertEqual(self.top("inverted index"), "Inverted Index")
        self.assertEqual(self.top("BM25", model="bm25"), "BM25 Ranking Function")
        self.assertEqual(self.top("FAISS vector database"), "Vector Databases and FAISS")
        self.assertEqual(self.top("web crawler"), "Web Crawling")

    def test_ranking_is_sorted(self):
        scores = [h["score"] for h in self.engine.search("search engine ranking")["hits"]]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_all_mode_requires_every_term(self):
        res = self.engine.search("precision recall", mode="all")
        self.assertTrue(res["hits"])
        for h in res["hits"]:
            self.assertEqual(len(h["matched"]), 2)

    def test_no_results(self):
        self.assertEqual(self.engine.search("zebra giraffe")["total"], 0)

    def test_snippet_is_escaped_and_highlighted(self):
        hit = self.engine.search("inverted index")["hits"][0]
        self.assertIn("<mark>", hit["snippet"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
