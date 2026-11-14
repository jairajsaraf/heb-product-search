"""Search service: BM25 + optional precomputed-embedding linear hybrid, with per-component scores.

Thin wrapper over the root-level rankers (not modified). Same scoring as
`semantic_ranker.HybridRanker._linear`: BM25 divided by its max, semantic = (cos + 1) / 2.
"""
import json
from pathlib import Path

import numpy as np

from baseline_ranker import BM25Ranker, preprocess_text

# Final system (reports/cv_results.md): linear BM25 + MiniLM, BM25 weight 0.10 (3 of 5 folds; 0.15 in the other 2).
BM25_WEIGHT = 0.10
MODEL_NAME = "all-MiniLM-L6-v2"
MODEL_REVISION = "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"  # reports/cv_results.json meta.models.minilm


def _norm(s):
    return " ".join(s.lower().split())


def load_dev_labels(data_dir):
    """Return (query text -> dev query_id, dev query_id -> {product_id: relevance}, locked query texts).

    Locked query ids never enter the label map, so their labels cannot reach a response (spec M8).
    """
    data_dir = Path(data_dir)
    read = lambda n: json.loads((data_dir / n).read_text(encoding="utf-8"))  # noqa: E731
    locked = set(read("split_v1.json")["locked"])
    queries = read("queries_synth_train.json")
    by_text = {_norm(q["query"]): q["query_id"] for q in queries if q["query_id"] not in locked}
    locked_texts = {_norm(q["query"]) for q in queries if q["query_id"] in locked}
    labels = {qid: {} for qid in by_text.values()}
    for r in read("labels_synth_train.json"):
        if r["query_id"] in labels:
            labels[r["query_id"]][r["product_id"]] = r["relevance"]
    return by_text, labels, locked_texts


class Searcher:
    """encoder=None or embeddings=None gives BM25-only search (semantic fields are None)."""

    def __init__(self, products, embeddings=None, encoder=None, bm25_weight=BM25_WEIGHT, data_dir=None):
        self.products = products
        self.bm25 = BM25Ranker(products)
        self.encoder = encoder
        self.bm25_weight = bm25_weight
        self.by_text, self.labels, self.locked_texts = ({}, {}, set())
        if data_dir is not None:
            self.by_text, self.labels, self.locked_texts = load_dev_labels(data_dir)
        self._unit = None
        if embeddings is not None:
            self._unit = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)

    @property
    def mode(self):
        return "hybrid" if self.encoder is not None and self._unit is not None else "bm25"

    def search(self, query, k=30):
        raw = np.asarray(self.bm25.bm25.get_scores(preprocess_text(query)), dtype=float)
        mx = raw.max()
        bm25 = raw / mx if mx > 0 else raw
        if self.mode == "hybrid":
            q = self.encoder.encode([query], convert_to_numpy=True)[0]
            sem = (self._unit @ (q / np.linalg.norm(q)) + 1) / 2
            final = self.bm25_weight * bm25 + (1 - self.bm25_weight) * sem
        else:
            sem, final = None, bm25
        text = _norm(query)
        qid = self.by_text.get(text)
        split = "dev" if qid else ("held_out" if text in self.locked_texts else None)
        labels = self.labels.get(qid, {})
        results = []
        for rank, i in enumerate(np.argsort(-final, kind="stable")[:k], 1):
            p = self.products[i]
            results.append({
                "rank": rank,
                "product_id": p["product_id"],
                "title": p["title"],
                "brand": p.get("brand"),
                "score": float(final[i]),
                "bm25_score": float(bm25[i]),
                "semantic_score": None if sem is None else float(sem[i]),
                "rerank_score": None,
                # judged label for dev queries (0 = unjudged or irrelevant); None for anything else, see `split`
                "label": labels.get(p["product_id"], 0) if qid else None,
            })
        return {"query": query, "split": split, "mode": self.mode, "results": results}
