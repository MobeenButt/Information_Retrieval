"""Extended Boolean parsing and p-norm ranking for FYP evidence documents."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import math
import re
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
    """REPLACEABLE TEAMMATE HOOK: multiplier for external relevance functions.

    Returns 1.0 until a teammate's relevance, partial-match, or fuzzy score
    function is available. Replace this body or pass a weight_hook to rank.
    """
    return 1.0


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
                   weight_hook=None) -> list[dict[str, Any]]:
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

    results = []
    for index, document in enumerate(documents):
        score, detail = evaluate(tree, weights[index])
        result = {"document": document, "id": document.get("id", ""), "score": score}
        if explain:
            result["explain"] = {"term_weights": weights[index], "expression": detail}
        results.append(result)
    results.sort(key=lambda result: (-result["score"], str(result["id"])))
    return results[:top_k]
