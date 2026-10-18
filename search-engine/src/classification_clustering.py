"""Document classification and clustering (Week 3).

Supervised classification (Naive Bayes over TF-IDF features) and unsupervised
clustering (k-means), both built on the scikit-learn library.
"""
from __future__ import annotations

from typing import Dict, List

import numpy as np
from sklearn.cluster import KMeans
from sklearn.metrics import accuracy_score, classification_report
from sklearn.model_selection import train_test_split
from sklearn.naive_bayes import MultinomialNB


# ─────────────────────────────────────────────
#  Week 3 - Classification and Clustering
# ─────────────────────────────────────────────
def _build_tfidf_matrix(index) -> tuple:
    """Return (X, y, doc_ids): a TF-IDF doc-term matrix and category labels."""
    terms = index.vocabulary
    doc_ids = sorted(index.docs.keys())
    term_index = {t: i for i, t in enumerate(terms)}
    forward = index.forward_index()
    X = np.zeros((len(doc_ids), len(terms)))
    for i, did in enumerate(doc_ids):
        for t, w in forward[did].items():
            X[i, term_index[t]] = w
    y = np.array([index.docs[did].get("category", "") for did in doc_ids])
    return X, y, doc_ids


def classify_documents(index, test_size: float = 0.2) -> Dict[str, object]:
    """Train a Naive Bayes classifier on TF-IDF features and report accuracy."""
    X, y, doc_ids = _build_tfidf_matrix(index)
    # stratify when possible, otherwise a plain random split
    try:
        split = train_test_split(
            X, y, doc_ids, test_size=test_size, random_state=42, stratify=y
        )
    except ValueError:
        split = train_test_split(X, y, doc_ids, test_size=test_size, random_state=42)
    X_train, X_test, y_train, y_test, ids_train, ids_test = split

    clf = MultinomialNB()
    clf.fit(X_train, y_train)
    y_pred = clf.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)
    report = classification_report(y_test, y_pred, zero_division=0)
    predictions = [
        {"id": int(ids_test[i]), "true": str(y_test[i]), "predicted": str(y_pred[i])}
        for i in range(len(ids_test))
    ]
    return {
        "model": "MultinomialNB (Naive Bayes)",
        "accuracy": round(float(accuracy), 4),
        "n_train": len(ids_train),
        "n_test": len(ids_test),
        "classification_report": report,
        "predictions": predictions,
    }


def cluster_documents(index, n_clusters: int = 5) -> Dict[str, object]:
    """Cluster documents with k-means over TF-IDF features."""
    X, _, doc_ids = _build_tfidf_matrix(index)
    n_clusters = max(1, min(n_clusters, len(doc_ids)))
    km = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    labels = km.fit_predict(X)

    terms = index.vocabulary
    order = km.cluster_centers_.argsort()[:, ::-1]
    top_terms = {str(c): [terms[j] for j in order[c][:8]] for c in range(n_clusters)}

    assignments = [
        {
            "id": int(doc_ids[i]),
            "title": index.docs[doc_ids[i]].get("title", ""),
            "category": index.docs[doc_ids[i]].get("category", ""),
            "cluster": int(labels[i]),
        }
        for i in range(len(doc_ids))
    ]
    return {
        "n_clusters": n_clusters,
        "cluster_assignments": assignments,
        "top_terms": top_terms,
    }


def compare_classification_clustering(index) -> str:
    """Explain supervised vs unsupervised learning in the IR context."""
    return (
        "Classification (supervised) vs Clustering (unsupervised)\n"
        "--------------------------------------------------------\n"
        "Classification is SUPERVISED: we train a Naive Bayes model on documents\n"
        "that already carry category labels (AI, Healthcare, Databases, ...), so\n"
        "the model learns to PREDICT the label of a new document. We can measure\n"
        "accuracy and precision/recall because the true labels are known.\n\n"
        "Clustering is UNSUPERVISED: k-means groups documents using only their\n"
        "TF-IDF similarity, with no labels. It discovers natural topic groups and\n"
        "labels them afterwards with their top terms. There is no 'correct' answer\n"
        "to measure against - only the coherence of the clusters.\n\n"
        "In IR, classification powers category filtering and routing of documents\n"
        "to the right sub-index; clustering organises search results into themes so\n"
        "users can navigate large result sets (e.g. the 'search result clustering'\n"
        "feature of Week 3)."
    )


def filter_by_category(results: List[Dict], category: str) -> List[Dict]:
    """Keep only the results whose document belongs to the given category."""
    if not category:
        return results
    return [r for r in results if r.get("category") == category]
