"""Boolean Retrieval Model (Week 3).

A full Boolean expression parser with the correct operator precedence
    NOT  >  AND  >  OR
and support for parentheses. Documents are returned as an unranked set
(score = 1 for every match) because the Boolean model is set-based.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Set, Tuple

from text_processing import preprocess


# ─────────────────────────────────────────────
#  Week 3 - Boolean Retrieval Model
# ─────────────────────────────────────────────
def _tokenize_query(query: str) -> List[str]:
    """Split a query into tokens, treating parentheses as standalone tokens."""
    query = query.replace("(", " ( ").replace(")", " ) ")
    return [t for t in query.split() if t]


def _fmt(docs: Set[int]) -> str:
    return "{" + ", ".join(str(d) for d in sorted(docs)) + "}"


def _query_stems(query: str) -> List[str]:
    """All indexable stems appearing anywhere in the query (for matched list)."""
    stems = []
    for tok in _tokenize_query(query):
        if tok.upper() in ("AND", "OR", "NOT", "(", ")"):
            continue
        stems.extend(preprocess(tok))
    return list(dict.fromkeys(stems))


class _Parser:
    """Recursive-descent parser: or := and (OR and)* ; and := not (AND not)*."""

    def __init__(self, tokens: List[str], index) -> None:
        self.tokens = tokens
        self.pos = 0
        self.index = index

    def _peek(self) -> Optional[str]:
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def _next(self) -> Optional[str]:
        tok = self._peek()
        self.pos += 1
        return tok

    def parse(self) -> Tuple[Set[int], str]:
        return self._parse_or()

    def _parse_or(self) -> Tuple[Set[int], str]:
        left, lexp = self._parse_and()
        while self._peek() and self._peek().upper() == "OR":
            self._next()
            right, rexp = self._parse_and()
            combined = left | right
            lexp = f"({lexp} OR {rexp}) = {_fmt(combined)}"
            left = combined
        return left, lexp

    def _parse_and(self) -> Tuple[Set[int], str]:
        left, lexp = self._parse_not()
        while True:
            tok = self._peek()
            if tok is None or tok.upper() in ("OR", ")"):
                break
            if tok.upper() == "AND":
                self._next()
            right, rexp = self._parse_not()
            combined = left & right
            lexp = f"({lexp} AND {rexp}) = {_fmt(combined)}"
            left = combined
        return left, lexp

    def _parse_not(self) -> Tuple[Set[int], str]:
        if self._peek() and self._peek().upper() == "NOT":
            self._next()
            operand, oexp = self._parse_not()
            combined = set(self.index.docs.keys()) - operand
            return combined, f"(NOT {oexp}) = {_fmt(combined)}"
        return self._parse_atom()

    def _parse_atom(self) -> Tuple[Set[int], str]:
        tok = self._peek()
        if tok == "(":
            self._next()
            result, exp = self._parse_or()
            if self._peek() == ")":
                self._next()
            return result, exp
        self._next()
        if tok is None:
            return set(), "(end)"
        if tok.upper() in ("AND", "OR"):
            return set(), f"(unexpected '{tok}')"
        stems = preprocess(tok)
        if not stems:
            return set(), f"'{tok}' -> (no indexable terms) = {{}}"
        # a single word normally yields one stem; if several, require ALL of them
        sets = [set(self.index.postings.get(s, {}).keys()) for s in stems]
        docs = sets[0]
        for s in sets[1:]:
            docs &= s
        label = stems[0] if len(stems) == 1 else "(" + " AND ".join(stems) + ")"
        return docs, f"'{label}' = {_fmt(docs)}"


def parse_and_execute(query_string: str, index) -> Tuple[Set[int], str]:
    """Parse and evaluate a Boolean query against the index.

    Week 3 - Boolean Retrieval Model. Returns ``(matching_doc_ids, explanation)``
    where the explanation traces each operator and its intermediate result set.
    """
    tokens = _tokenize_query(query_string)
    if not tokens:
        return set(), "Empty query."
    parser = _Parser(tokens, index)
    result, trace = parser.parse()
    lines = [
        f"Query : {query_string}",
        f"Tokens: {tokens}",
        f"Trace : {trace}",
        f"Result: {len(result)} document(s) -> {_fmt(result)}",
    ]
    if parser.pos != len(tokens):
        lines.append(f"Note  : {len(tokens) - parser.pos} unconsumed token(s) ignored.")
    return result, "\n".join(lines)


def boolean_search(query: str, index, top_k: Optional[int] = None) -> List[Dict]:
    """Run a Boolean query and return an unranked list of matching documents.

    Week 3 - Boolean Retrieval Model. Every match has ``score = 1`` (no ranking).
    """
    doc_ids, _ = parse_and_execute(query, index)
    stems = _query_stems(query)
    hits: List[Dict] = []
    for doc_id in sorted(doc_ids):
        doc = index.docs.get(doc_id)
        if doc is None:
            continue
        matched = [s for s in stems if doc_id in index.postings.get(s, {})]
        hits.append({
            "id": doc_id,
            "title": doc.get("title", ""),
            "category": doc.get("category", ""),
            "score": 1.0,
            "matched": matched,
        })
    if top_k is not None:
        hits = hits[:top_k]
    return hits
