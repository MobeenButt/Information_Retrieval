"""Unit tests for the Extended Boolean parser and p-norm ranker."""
import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from extended_boolean import Node, QuerySyntaxError, parse_query, rank_documents


class ParserTests(unittest.TestCase):
    def test_operators_case_insensitive_and_precedence(self):
        tree = parse_query('(timeout AND database) OR crash NOT test')
        self.assertEqual(tree.kind, "OR")
        self.assertEqual(tree.children[0].kind, "AND")
        self.assertEqual(tree.children[1].kind, "AND")
        self.assertEqual(tree.children[1].children[1].kind, "NOT")

    def test_quoted_phrase_is_one_term(self):
        tree = parse_query('"connection timeout" aNd database')
        self.assertEqual(tree.kind, "AND")
        self.assertEqual(tree.children[0].value, "connection timeout")

    def test_nested_groups(self):
        tree = parse_query('NOT (a OR (b AND c))')
        self.assertEqual(tree.kind, "NOT")
        self.assertEqual(tree.children[0].kind, "OR")
        self.assertEqual(tree.children[0].children[1].kind, "AND")

    def test_implicit_and(self):
        self.assertEqual(parse_query("timeout database").kind, "AND")

    def test_invalid_queries_have_clear_errors(self):
        cases = {
            "(alpha OR beta": "Unbalanced parentheses",
            "alpha AND": "Dangling AND",
            "alpha OR )": "Dangling OR",
            "NOT": "Dangling NOT",
            "alpha beta)": "Unbalanced parentheses",
        }
        for query, message in cases.items():
            with self.subTest(query=query), self.assertRaisesRegex(QuerySyntaxError, message):
                parse_query(query)


class RankingTests(unittest.TestCase):
    def test_known_p_norm_scores_and_tie_break(self):
        # Every matching term has normalized tf-idf weight 1; absent terms 0.
        docs = [
            {"id": "b", "content": "alpha"},
            {"id": "a", "content": "alpha beta"},
            {"id": "c", "content": "beta"},
        ]
        ranked = rank_documents("alpha AND beta", docs, p=2, top_k=3, explain=True)
        self.assertEqual([item["id"] for item in ranked], ["a", "b", "c"])
        self.assertAlmostEqual(ranked[0]["score"], 1.0)
        self.assertAlmostEqual(ranked[1]["score"], 1 - math.sqrt(0.5))
        self.assertAlmostEqual(ranked[2]["score"], 1 - math.sqrt(0.5))
        self.assertEqual(ranked[0]["explain"]["term_weights"], {"alpha": 1.0, "beta": 1.0})
        self.assertEqual(ranked[0]["explain"]["expression"]["operator"], "AND")

    def test_not_and_top_k(self):
        docs = [{"id": 1, "content": "alpha"}, {"id": 2, "content": "beta"}]
        results = rank_documents("NOT alpha", docs, top_k=1)
        self.assertEqual(results[0]["id"], 2)
        self.assertEqual(results[0]["score"], 1.0)


if __name__ == "__main__":
    unittest.main()
