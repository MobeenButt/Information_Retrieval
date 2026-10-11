"""Ad-hoc search vs filtering (Week 2).

Ad-hoc retrieval answers a one-time query. Filtering instead maintains a
long-term user profile and keeps every incoming document that matches the
profile above a threshold - the model used by push/news-alert systems.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional

from probabilistic_models import bm25_search
from text_processing import preprocess


# ─────────────────────────────────────────────
#  Week 2 - Ad-hoc vs Filtering
# ─────────────────────────────────────────────
@dataclass
class UserProfile:
    """A long-term interest profile for filtering."""

    name: str
    interest_keywords: List[str] = field(default_factory=list)
    category_preferences: List[str] = field(default_factory=list)

    def match_score(self, doc: Dict, index) -> float:
        """Score a document against this profile in [0, 1].

        Combines keyword overlap (0.6 weight) with a category preference
        match (0.4 weight).
        """
        text = " ".join(str(v) for k, v in doc.items() if k not in ("id", "category"))
        doc_terms = set(preprocess(text))
        kw_stems = set(preprocess(" ".join(self.interest_keywords)))
        kw_overlap = (len(doc_terms & kw_stems) / len(kw_stems)) if kw_stems else 0.0
        cat_match = 1.0 if doc.get("category") in self.category_preferences else 0.0
        return round(0.6 * kw_overlap + 0.4 * cat_match, 4)


def adhoc_search(query: str, index, top_k: int = 10) -> List[Dict]:
    """One-shot query-driven retrieval (here using BM25).

    Week 2 - Ad-hoc retrieval: the user states a need once and gets ranked
    results; there is no persistent profile.
    """
    return bm25_search(query, index, top_k=top_k)


def stream_filter(documents: List[Dict], profile: UserProfile, index,
                  threshold: float = 0.3) -> List[Dict]:
    """Push/filtering model: keep documents whose profile match_score >= threshold.

    Week 2 - Filtering: a standing profile scores every incoming document;
    only those above the threshold are delivered to the user.
    """
    kw_stems = set(preprocess(" ".join(profile.interest_keywords)))
    results: List[Dict] = []
    for doc in documents:
        score = profile.match_score(doc, index)
        if score >= threshold:
            text = " ".join(str(v) for k, v in doc.items() if k not in ("id", "category"))
            doc_terms = set(preprocess(text))
            matched = [kw for kw in profile.interest_keywords
                       if set(preprocess(kw)) & doc_terms]
            results.append({
                "document": doc,
                "match_score": score,
                "matched_keywords": matched,
            })
    results.sort(key=lambda x: (-x["match_score"], x["document"].get("id", 0)))
    return results


def demo_filtering(index) -> Dict[str, object]:
    """Demonstrate two profiles with both ad-hoc search and stream filtering."""
    profiles = [
        UserProfile("Diabetes Researcher",
                    ["diabetes", "treatment", "glucose"], ["Healthcare"]),
        UserProfile("Security Analyst",
                    ["malware", "intrusion", "vulnerability"], ["Cybersecurity"]),
    ]
    documents = list(index.docs.values())
    return {
        "profiles": [asdict(p) for p in profiles],
        "adhoc_search": adhoc_search("best treatment for diabetes", index, top_k=5),
        "stream_profile1": stream_filter(documents, profiles[0], index, threshold=0.3),
        "stream_profile2": stream_filter(documents, profiles[1], index, threshold=0.3),
    }
