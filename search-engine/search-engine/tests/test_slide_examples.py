"""Verification tests for the slide examples and core models.

All imports come from ``src/`` (not ``backend/``). ``conftest.py`` puts
``src`` on ``sys.path`` so the tests can import the modules directly.
"""
import os

import pytest

from boolean_model import boolean_search, parse_and_execute
from indexing import InvertedIndex
from probabilistic_models import bim_search, bm25_search, sigmoid, verify_sigmoid_example
from text_processing import analyze_pipeline, preprocess, stem
from vector_space_model import verify_slide_example, vsm_search

DATA = os.path.join(os.path.dirname(__file__), "..", "data", "documents.json")


@pytest.fixture(scope="module")
def index():
    return InvertedIndex.build_from_json(DATA)


# ── slide / sanity examples ──────────────────
def test_cosine_slide_example():
    res = verify_slide_example()
    assert abs(res["cosine_D1"] - 0.816) < 0.01
    assert abs(res["cosine_D2"] - 0.408) < 0.01
    assert abs(res["cosine_D3"] - 0.000) < 0.01


def test_sigmoid_values():
    assert abs(sigmoid(3.5) - 0.9707) < 0.001
    assert abs(sigmoid(2.0) - 0.8808) < 0.001
    assert abs(sigmoid(4.8) - 0.9918) < 0.001
    assert verify_sigmoid_example()["sigmoid"] == [0.9707, 0.8808, 0.9918]


# ── Boolean model ─────────────────────────────
def test_boolean_and(index):
    ids, _ = parse_and_execute("diabetes AND treatment", index)
    assert ids == {11, 12, 13}


def test_boolean_or(index):
    ids, _ = parse_and_execute("diabetes OR cryptography", index)
    assert ids == {8, 11, 12, 13}


def test_boolean_not(index):
    ids, _ = parse_and_execute("NOT diabetes", index)
    assert ids == set(range(1, 26)) - {11, 12, 13}


def test_boolean_search_returns_score_one(index):
    hits = boolean_search("diabetes AND treatment", index)
    assert len(hits) == 3
    assert all(h["score"] == 1.0 for h in hits)


# ── ranking ordering ──────────────────────────
def test_bm25_ordering(index):
    hits = bm25_search("best treatment for diabetes", index, top_k=5)
    top_ids = [h["id"] for h in hits]
    assert set(top_ids[:3]) == {11, 12, 13}
    scores = [h["score"] for h in hits]
    assert scores == sorted(scores, reverse=True)


def test_tfidf_ordering(index):
    hits = vsm_search("best treatment for diabetes", index, top_k=5)
    top_ids = [h["id"] for h in hits]
    assert set(top_ids[:3]) == {11, 12, 13}
    scores = [h["score"] for h in hits]
    assert scores == sorted(scores, reverse=True)


# ── BIM ───────────────────────────────────────
def test_bim_scores_positive(index):
    hits = bim_search("best treatment for diabetes", index, top_k=5)
    assert len(hits) > 0
    assert all(h["score"] > 0 for h in hits)
    assert all(0.0 <= h["probability"] <= 1.0 for h in hits)
    assert set([h["id"] for h in hits][:3]) == {11, 12, 13}


# ── text processing ───────────────────────────
def test_stemming():
    assert stem("running") == "run"
    assert stem("machines") == "machin"
    assert stem("databases") == "databas"
    assert stem("ranking") == "rank"


def test_preprocessing_pipeline():
    res = analyze_pipeline("The running machines")
    assert res["raw"] == "The running machines"
    assert res["tokens"] == ["the", "running", "machines"]
    assert res["no_stop"] == ["running", "machines"]
    assert res["stems"] == ["run", "machin"]
    # preprocess drops stop-words and stems the rest
    assert preprocess("best treatment for diabetes") == ["best", "treatment", "diabet"]
