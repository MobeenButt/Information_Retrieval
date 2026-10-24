"""Extended Boolean parsing and p-norm ranking for FYP evidence documents."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import math
import re
from difflib import SequenceMatcher
from typing import Any, Mapping, Sequence


class QuerySyntaxError(ValueError):
    """Raised when a query cannot be parsed, with a user-readable message."""


@dataclass(frozen=True)
class Node:
    """One term or Boolean operation in a parsed query."""
    kind: str
    value: str = ""
    children: tuple["Node", ...] = ()


_TOKEN = re.compile(r'\s*(\(|\)|"(?:\\.|[^"\\])*"|[^\s()"]+)')
_OPERATORS = {"AND", "OR", "NOT"}


def _tokenize(query: str) -> list[str]:
    """Split a query into operators, parentheses, phrases, and words."""
    tokens, pos = [], 0
    while pos < len(query):
        match = _TOKEN.match(query, pos)
        if not match:
            raise QuerySyntaxError(f"Unexpected character at position {pos + 1}.")
        tokens.append(match.group(1))
        pos = match.end()
    return tokens


def parse_query(query: str) -> Node:
    """Parse a query into a tree; NOT binds before AND, which binds before OR.

    Adjacent terms imply AND, so ``timeout database`` is equivalent to
    ``timeout AND database``. Quoted text is treated as one phrase leaf.
    """
    tokens = _tokenize(query.strip())
    if not tokens:
        raise QuerySyntaxError("Enter a query with at least one search term.")
    pos = 0

    def peek() -> str | None:
        return tokens[pos] if pos < len(tokens) else None

    def primary() -> Node:
        nonlocal pos
        token = peek()
        if token is None:
            raise QuerySyntaxError("Query ends where a term or '(' was expected.")
        if token == "(":
            pos += 1
            if peek() == ")":
                raise QuerySyntaxError("Empty parentheses are not a valid query.")
            node = parse_or()
            if peek() != ")":
                raise QuerySyntaxError("Unbalanced parentheses: missing ')'.")
            pos += 1
            return node
        if token == ")":
            raise QuerySyntaxError("Unexpected ')'; check the parentheses.")
        if token.upper() in _OPERATORS:
            raise QuerySyntaxError(f"Unexpected operator {token.upper()}; a search term was expected.")
        pos += 1
        if token.startswith('"'):
            phrase = bytes(token[1:-1], "utf-8").decode("unicode_escape").strip()
            if not phrase:
                raise QuerySyntaxError("Quoted phrases cannot be empty.")
            return Node("TERM", phrase)
        return Node("TERM", token)

    def parse_not() -> Node:
        nonlocal pos
        if (peek() or "").upper() == "NOT":
            pos += 1
            if peek() is None or peek() == ")" or (peek() or "").upper() in {"AND", "OR"}:
                raise QuerySyntaxError("Dangling NOT: add a term after NOT.")
            return Node("NOT", children=(parse_not(),))
        return primary()

    def parse_and() -> Node:
        nonlocal pos
        children = [parse_not()]
        while peek() is not None and peek() != ")":
            if (peek() or "").upper() == "OR":
                break
            if (peek() or "").upper() == "AND":
                pos += 1
                if peek() is None or peek() == ")" or (peek() or "").upper() in {"AND", "OR"}:
                    raise QuerySyntaxError("Dangling AND: add a search term after AND.")
            # Otherwise the next primary is adjacent, meaning implicit AND.
            children.append(parse_not())
        return children[0] if len(children) == 1 else Node("AND", children=tuple(children))

    def parse_or() -> Node:
        nonlocal pos
        children = [parse_and()]
        while (peek() or "").upper() == "OR":
            pos += 1
            if peek() is None or peek() == ")" or (peek() or "").upper() in {"AND", "OR"}:
                raise QuerySyntaxError("Dangling OR: add a search term after OR.")
            children.append(parse_and())
        return children[0] if len(children) == 1 else Node("OR", children=tuple(children))

    tree = parse_or()
    if pos < len(tokens):
        if tokens[pos] == ")":
            raise QuerySyntaxError("Unbalanced parentheses: unexpected ')'.")
        if tokens[pos].upper() in {"AND", "OR"}:
            raise QuerySyntaxError(f"Dangling {tokens[pos].upper()}: add a search term after it.")
        raise QuerySyntaxError(f"Unexpected token {tokens[pos]!r}.")
    return tree


def relevance_adjustment(document: Mapping[str, Any], phrase: str) -> float:
    """Return a bounded relevance multiplier for exact, partial, and fuzzy matches.

    Exact matches retain the normalized TF-IDF weight. Partial phrase/token
    matches receive a graded multiplier, while close spelling variants receive
    a smaller fuzzy multiplier. Field boosts favor titles and summaries without
    excluding matches found in the document body.
    """
    phrase = phrase.casefold().strip()
    title = str(document.get("title", "")).casefold()
    summary = str(document.get("summary", "")).casefold()
    body = str(document.get("text", "") or document.get("content", "")).casefold()
    source = str(document.get("source", "")).casefold()
    source_file = str(document.get("source_file", "")).casefold()
    if not phrase or phrase in title or phrase in summary or phrase in body or phrase in source or phrase in source_file:
        return 1.0 + (0.12 if phrase in title or phrase in summary else 0.0)
    phrase_tokens = re.findall(r"\w+", phrase)
    tokens = re.findall(r"\w+", f"{title} {summary} {source} {source_file}")
    if not phrase_tokens or not tokens:
        return 0.0
    matched = sum(1 for term in phrase_tokens if term in tokens)
    partial = matched / len(phrase_tokens)
    fuzzy = max((SequenceMatcher(None, phrase, token).ratio() for token in tokens), default=0.0)
    if partial:
        return min(1.0, 0.35 + 0.55 * partial)
    return 0.35 + 0.35 * fuzzy if fuzzy >= 0.78 else 0.0


def partial_scores(query: str, documents: Sequence[Mapping[str, Any]]) -> dict[str, float]:
    """Score documents by the proportion of query terms they contain."""
    terms = [term.casefold() for term in re.findall(r"\w+", query) if term.upper() not in _OPERATORS]
    if not terms:
        return {str(doc.get("id", "")): 0.0 for doc in documents}
    scores = {}
    for doc in documents:
        text = " ".join(str(doc.get(field, "")) for field in
                        ("title", "text", "summary", "content", "source", "source_file")).casefold()
        scores[str(doc.get("id", ""))] = sum(term in text for term in terms) / len(terms)
    return scores


def fuzzy_scores(query: str, documents: Sequence[Mapping[str, Any]], threshold: float = 0.78) -> dict[str, float]:
    """Return the best fuzzy token coverage for each document."""
    terms = [term.casefold() for term in re.findall(r"\w+", query) if term.upper() not in _OPERATORS]
    scores = {}
    for doc in documents:
        token_set = set(re.findall(r"\w+", " ".join(str(doc.get(field, "")) for field in
                                                     ("title", "text", "summary", "content")).casefold()))
        matches = []
        for term in terms:
            if term in token_set:
                matches.append(1.0)
                continue
            candidates = [token for token in token_set
                          if token[:1] == term[:1] and abs(len(token) - len(term)) <= 2][:64]
            matches.append(max((SequenceMatcher(None, term, token).ratio() for token in candidates), default=0.0))
        scores[str(doc.get("id", ""))] = sum(score if score >= threshold else 0.0 for score in matches) / len(terms) if terms else 0.0
    return scores


def _bm25_scores(phrases: Sequence[str], documents: Sequence[Mapping[str, Any]],
                 counts: Sequence[Counter], k1: float = 1.2, b: float = 0.75) -> list[float]:
    """Return normalized BM25 scores for the query phrases."""
    lengths = [len(re.findall(r"\w+", " ".join(str(document.get(field, ""))
                                                for field in ("title", "text", "summary", "content"))))
               for document in documents]
    average_length = sum(lengths) / len(lengths) if lengths else 1.0
    total = len(documents)
    idf = {phrase: math.log(1 + (total - sum(item[phrase] > 0 for item in counts) + .5) /
                            (sum(item[phrase] > 0 for item in counts) + .5))
           for phrase in phrases}
    scores = []
    for index, length in enumerate(lengths):
        score = 0.0
        denominator_length = 1 - b + b * length / max(average_length, 1.0)
        for phrase in phrases:
            term_frequency = counts[index][phrase]
            score += idf[phrase] * (term_frequency * (k1 + 1)) / (
                term_frequency + k1 * denominator_length) if term_frequency else 0.0
        scores.append(score)
    maximum = max(scores, default=0.0)
    return [score / maximum if maximum else 0.0 for score in scores]


def _proximity_scores(phrases: Sequence[str], documents: Sequence[Mapping[str, Any]]) -> list[float]:
    """Reward query terms occurring close together in each document."""
    scores = []
    for document in documents:
        tokens = re.findall(r"\w+", " ".join(str(document.get(field, ""))
                                             for field in ("title", "text", "summary", "content")).casefold())
        positions = []
        for phrase in phrases:
            term = phrase.casefold()
            positions.append([index for index, token in enumerate(tokens) if token == term])
        if len(positions) < 2 or not all(positions):
            scores.append(1.0 if positions and positions[0] else 0.0)
            continue
        distances = [min(abs(left - right) for left in positions[0] for right in other)
                     for other in positions[1:]]
        scores.append(1.0 / (1.0 + sum(distances) / len(distances)))
    return scores


def _phrase_counts(documents: Sequence[Mapping[str, Any]], phrases: Sequence[str]) -> list[Counter]:
    """Count phrase occurrences in each document's searchable evidence text."""
    output = []
    for document in documents:
        text = " ".join(str(document.get(field, "")) for field in
                         ("title", "text", "summary", "content", "source", "source_file", "locator")).casefold()
        counts = Counter()
        for phrase in phrases:
            escaped = re.escape(phrase.casefold())
            counts[phrase] = len(re.findall(r"(?<!\w)" + escaped + r"(?!\w)", text))
        output.append(counts)
    return output


def _tree_terms(node: Node) -> list[str]:
    """Return distinct query leaves in first-seen order."""
    found = []
    def visit(current: Node) -> None:
        if current.kind == "TERM":
            if current.value.casefold() not in [item.casefold() for item in found]:
                found.append(current.value)
        for child in current.children:
            visit(child)
    visit(node)
    return found


def rank_documents(query: str, documents: Sequence[Mapping[str, Any]], *, p: float = 2,
                   top_k: int = 10, explain: bool = False,
                   weight_hook=None, rerank: bool = False) -> list[dict[str, Any]]:
    """Score all docs using normalized TF-IDF and p-norm Boolean operators.

    AND uses the complement p-norm, OR uses the direct p-norm, and NOT uses
    the complement of its child's score. The optional hook can incorporate
    teammate relevance logic. Sorting is score descending then document id.
    """
    if not math.isfinite(float(p)) or p < 1:
        raise ValueError("p must be a finite number greater than or equal to 1.")
    if top_k < 0:
        raise ValueError("top_k cannot be negative.")
    tree = parse_query(query)
    phrases = _tree_terms(tree)
    counts = _phrase_counts(documents, phrases)
    n_docs = len(documents)
    idf = {phrase: math.log((n_docs + 1) / (sum(c[phrase] > 0 for c in counts) + 1)) + 1 for phrase in phrases}
    raw = {phrase: [((1 + math.log(c[phrase])) * idf[phrase] if c[phrase] else 0.0) for c in counts] for phrase in phrases}
    maxima = {phrase: max(values, default=0.0) for phrase, values in raw.items()}
    hook = weight_hook or relevance_adjustment
    weights = [{phrase: min(1.0, max(0.0, raw[phrase][i] / maxima[phrase] if maxima[phrase] else 0.0) * float(hook(doc, phrase)))
                for phrase in phrases} for i, doc in enumerate(documents)]

    def evaluate(node: Node, doc_weights: Mapping[str, float]) -> tuple[float, dict]:
        if node.kind == "TERM":
            value = doc_weights[node.value]
            return value, {"term": node.value, "weight": value, "score": value}
        parts = [evaluate(child, doc_weights) for child in node.children]
        values = [item[0] for item in parts]
        if node.kind == "NOT":
            score = 1 - values[0]
        elif node.kind == "AND":
            score = 1 - (sum((1 - value) ** p for value in values) / len(values)) ** (1 / p)
        else:
            score = (sum(value ** p for value in values) / len(values)) ** (1 / p)
        return score, {"operator": node.kind, "children": [item[1] for item in parts], "score": score}

    partial = partial_scores(query, documents)
    fuzzy = fuzzy_scores(query, documents)
    bm25 = _bm25_scores(phrases, documents, counts)
    proximity = _proximity_scores(phrases, documents)
    results = []
    for index, document in enumerate(documents):
        score, detail = evaluate(tree, weights[index])
        document_id = str(document.get("id", ""))
        coverage = partial.get(document_id, 0.0)
        fuzzy_coverage = fuzzy.get(document_id, 0.0)
        boolean_score = score
        if rerank:
            score = min(1.0, .55 * boolean_score + .25 * bm25[index] +
                        .10 * proximity[index] + .10 * coverage)
        detail["score"] = score
        result = {"document": document, "id": document.get("id", ""), "score": score}
        if explain:
            result["explain"] = {"term_weights": weights[index], "expression": detail,
                                 "partial_coverage": coverage, "fuzzy_coverage": fuzzy_coverage,
                                 "boolean_score": boolean_score, "bm25_score": bm25[index],
                                 "proximity_score": proximity[index], "coverage_score": coverage,
                                 "reranked": rerank}
        results.append(result)
    results.sort(key=lambda result: (-result["score"], str(result["id"])))
    return results[:top_k]
