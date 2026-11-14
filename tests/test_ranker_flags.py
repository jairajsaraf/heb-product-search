"""Phase 3 flags on HybridRanker (both default off). Stub models: no download, no network."""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import semantic_ranker as sr  # noqa: E402
from baseline_ranker import preprocess_text  # noqa: E402

PRODUCTS = [
    {"product_id": "p0", "title": "apple pie", "brand": "A", "category_path": "Bakery -> Pies", "description": "apple"},
    {"product_id": "p1", "title": "pear tart", "brand": "B", "category_path": "Bakery -> Tarts", "description": "pear"},
    {"product_id": "p2", "title": "apple juice", "brand": "C", "category_path": "Drinks -> Juice", "description": ""},
    {"product_id": "p3", "title": "plum jam", "brand": "D", "category_path": "Pantry -> Jam", "description": "plum"},
]
WORDS = ["apple", "pear", "juice", "plum"]


class StubEncoder:
    def __init__(self, *args, **kwargs):
        self.device = "cpu"

    def encode(self, texts, **kwargs):
        return np.array([[t.lower().count(w) + 0.1 for w in WORDS] for t in texts], dtype=np.float32)


class StubCrossEncoder:
    SCORES = {"apple pie": 0.2, "pear tart": 0.9, "apple juice": 0.5, "plum jam": 0.7}

    def __init__(self, *args, **kwargs):
        self.device = "cpu"

    def predict(self, pairs, **kwargs):
        return np.array([next(v for k, v in self.SCORES.items() if b.startswith(k)) for _, b in pairs], dtype=np.float32)


@pytest.fixture
def ranker(monkeypatch):
    monkeypatch.setattr(sr, "SentenceTransformer", StubEncoder)
    monkeypatch.setattr(sr, "CrossEncoder", StubCrossEncoder)
    return sr.HybridRanker(PRODUCTS, model_name="stub", reranker_model="stub-ce")


def test_rrf_flag(ranker):
    # tie-aware ranks: bm25 [3,1,1,0] -> [1,2,2,4]; cos [.1,.9,.5,.2] -> [4,1,2,3]; k=1
    fused = sr.rrf_fuse(np.array([3.0, 1.0, 1.0, 0.0]), np.array([0.1, 0.9, 0.5, 0.2]), k=1)
    assert np.allclose(fused, [1 / 2 + 1 / 5, 1 / 3 + 1 / 2, 1 / 3 + 1 / 3, 1 / 5 + 1 / 4])
    assert list(np.argsort(-fused, kind="stable")) == [1, 0, 2, 3]

    q = "apple pie"
    bm = ranker.bm25_ranker.bm25.get_scores(preprocess_text(q))
    e, qv = ranker.product_embeddings, ranker.model.encode([q])[0]
    cos = np.dot(e, qv) / (np.linalg.norm(e, axis=1) * np.linalg.norm(qv))
    expected = [PRODUCTS[i]["product_id"] for i in np.argsort(-sr.rrf_fuse(bm, cos, 60), kind="stable")]
    assert [p for p, _ in ranker.rank(q, top_k=4, fusion="rrf", rrf_k=60)] == expected


def test_rerank_flag(ranker):
    assert list(sr.rerank_order(np.array([5, 2, 7, 1]), np.array([0.1, 0.9, 0.5]))) == [2, 7, 5, 1]

    q = "apple"
    base = [p for p, _ in ranker.rank(q, top_k=4)]
    got = [p for p, _ in ranker.rank(q, top_k=4, rerank=True, rerank_depth=3)]
    title = {p["product_id"]: p["title"] for p in PRODUCTS}
    assert got[:3] == sorted(base[:3], key=lambda p: -StubCrossEncoder.SCORES[title[p]])
    assert got[3] == base[3]

    plain = sr.HybridRanker.__new__(sr.HybridRanker)
    plain.reranker = None
    with pytest.raises(ValueError):
        plain.rank(q, rerank=True)
