"""Streamlit app for the IR search engine.

Six tabs: Search, Compare Models, Pipeline View, Evaluation,
Classification + Clustering, and Filtering Demo.

Run with:  streamlit run app.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

import pandas as pd
import streamlit as st

from classification_clustering import (classify_documents, cluster_documents,
                                        compare_classification_clustering)
from evaluation import evaluate_all_models, print_comparison_table
from filtering import demo_filtering
from search_engine import SearchEngine

MODELS = ["boolean", "vsm", "bm25", "bim",
          "overlap", "nonoverlap", "proximal", "field_bm25"]
CATEGORIES = ["(none)", "AI", "Cybersecurity", "Healthcare",
              "Databases", "SoftwareEngineering", "IR"]

st.set_page_config(page_title="IR Search Engine", page_icon="🔎", layout="wide")


@st.cache_resource
def get_engine() -> SearchEngine:
    return SearchEngine("data/documents.json", "index/structured_index.json")


def _mean_metrics_df(results):
    rows = {}
    for model, per_q in results.items():
        qs = list(per_q.values())
        rows[model] = {m: sum(q[m] for q in qs) / len(qs)
                       for m in ["precision@5", "recall@5", "f1@5", "ap", "mrr", "ndcg@5"]}
    return pd.DataFrame(rows).T.round(4)


# ── tabs ──────────────────────────────────────
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "Search", "Compare Models", "Pipeline View", "Evaluation",
    "Classification + Clustering", "Filtering Demo",
])

# 1. Search
with tab1:
    st.header("🔍 Search")
    query = st.text_input("Query", "best treatment for diabetes")
    col1, col2, col3 = st.columns(3)
    model = col1.selectbox("Ranking model", MODELS, index=2)
    top_k = col2.slider("Top K", 1, 25, 5)
    category = col3.selectbox("Category filter", CATEGORIES)
    show_math = st.checkbox("Show BM25 math walkthrough", value=False)

    field_weights = None
    if model == "field_bm25":
        st.subheader("Field weights")
        c1, c2, c3, c4 = st.columns(4)
        field_weights = {
            "title": c1.slider("title", 1, 5, 3),
            "abstract": c2.slider("abstract", 1, 5, 2),
            "methodology": c3.slider("methodology", 1, 5, 1),
            "results": c4.slider("results", 1, 5, 1),
        }

    if st.button("Search", type="primary"):
        se = get_engine()
        filters = {"category": category} if category != "(none)" else None
        result = se.search(query, model=model, fields=field_weights, top_k=top_k,
                          filters=filters, show_math=show_math)
        st.caption(f"model={result['model']} | total={result['total']} | "
                   f"stems={result['pipeline']['stems']} | {result['took_ms']} ms")
        if not result["hits"]:
            st.info("No matching documents.")
        for hit in result["hits"]:
            label = f"#{hit['id']}  {hit.get('title', '')}  (score {hit['score']})"
            with st.expander(label, expanded=False):
                st.json(hit)

# 2. Compare Models
with tab2:
    st.header("📊 Compare Models")
    if st.button("Run full evaluation across 5 judged queries"):
        se = get_engine()
        results = evaluate_all_models(se.index)
        df = _mean_metrics_df(results)
        st.dataframe(df, use_container_width=True)
        st.subheader("Mean metrics by model (bar chart)")
        st.bar_chart(df[["precision@5", "recall@5", "mrr"]])
        st.subheader("Markdown comparison table")
        st.markdown(print_comparison_table(results))

# 3. Pipeline View
with tab3:
    st.header("🛠 Pipeline View")
    query3 = st.text_input("Query", "best treatment for diabetes", key="pipe")
    if st.button("Trace pipeline"):
        se = get_engine()
        for stage in se.pipeline_trace(query3):
            with st.container(border=True):
                st.subheader(stage["stage"])
                st.caption(stage["description"])
                st.write(stage["output"])

# 4. Evaluation
with tab4:
    st.header("📈 Evaluation")
    if st.button("Run evaluation (Precision, Recall, AP, MRR, nDCG)"):
        se = get_engine()
        results = evaluate_all_models(se.index)
        st.markdown(print_comparison_table(results))
        df = _mean_metrics_df(results)
        st.subheader("Precision@5 vs Recall@5")
        st.bar_chart(df[["precision@5", "recall@5"]])

# 5. Classification + Clustering
with tab5:
    st.header("🧪 Classification + Clustering")
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Classification (Naive Bayes)")
        if st.button("Train & evaluate classifier"):
            se = get_engine()
            res = classify_documents(se.index)
            st.metric("Accuracy", f"{res['accuracy'] * 100:.1f}%")
            st.caption(f"train={res['n_train']}  test={res['n_test']}  model={res['model']}")
            st.text(res["classification_report"])
            st.dataframe(res["predictions"], use_container_width=True)
    with c2:
        st.subheader("Clustering (k-means)")
        nc = st.slider("Number of clusters", 2, 8, 5, key="nc")
        if st.button("Run clustering"):
            se = get_engine()
            res = cluster_documents(se.index, nc)
            st.dataframe(res["cluster_assignments"], use_container_width=True)
            st.write("Top terms per cluster:")
            st.json(res["top_terms"])
    st.subheader("Supervised vs Unsupervised")
    if st.button("Show explanation"):
        st.text(compare_classification_clustering(get_engine().index))

# 6. Filtering Demo
with tab6:
    st.header("📨 Filtering Demo (Ad-hoc vs Filtering)")
    demo = demo_filtering(get_engine().index)
    st.subheader("User profiles")
    st.json(demo["profiles"])
    st.subheader("Ad-hoc search: 'best treatment for diabetes'")
    st.dataframe(demo["adhoc_search"], use_container_width=True)
    for label, key in [("Diabetes Researcher", "stream_profile1"),
                       ("Security Analyst", "stream_profile2")]:
        st.subheader(f"Stream filtering - {label}")
        rows = [{
            "id": x["document"]["id"],
            "title": x["document"]["title"],
            "match_score": x["match_score"],
            "matched_keywords": x["matched_keywords"],
        } for x in demo[key]]
        st.dataframe(rows, use_container_width=True)
