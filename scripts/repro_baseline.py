"""Phase 0: reproduce BM25 / hybrid scores on all 288 train queries.

Uses the repo's rankers unchanged and tamu25.evaluate.evaluate_submission unchanged.
Writes reports/baseline_repro.json. Run from the repo root:
    .venv/Scripts/python scripts/repro_baseline.py
"""
import json
import os
import platform
import sys
import tempfile
from importlib.metadata import version
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import torch  # noqa: E402

from baseline_ranker import BM25Ranker, load_json  # noqa: E402
from semantic_ranker import HybridRanker  # noqa: E402
from tamu25.evaluate import evaluate_submission  # noqa: E402

DEPTHS = (30, 50)
MODELS = {
    "minilm": ("all-MiniLM-L6-v2", 0.3, 0.7),
    "mpnet": ("all-mpnet-base-v2", 0.2, 0.8),
}
SPREAD_QUERIES = 5


def revision_of(model_name):
    snaps = Path.home() / ".cache/huggingface/hub" / f"models--sentence-transformers--{model_name}" / "snapshots"
    return sorted(p.name for p in snaps.iterdir()) if snaps.exists() else []


def score(rows, labels_path):
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(rows, f)
    try:
        return evaluate_submission(f.name, labels_path)
    finally:
        os.unlink(f.name)


def to_rows(queries, rank_fn, depth):
    rows = []
    for q in queries:
        for r, (pid, _) in enumerate(rank_fn(q["query"], depth), 1):
            rows.append({"query_id": q["query_id"], "rank": r, "product_id": pid})
    return rows


def spread(ranker, queries):
    """Per-query std of the two score components over all products (confirms/refutes scale mismatch)."""
    out = []
    for q in queries[:SPREAD_QUERIES]:
        b = dict(ranker.bm25_ranker.rank(q["query"], top_k=len(ranker.products)))
        b = np.array([b[p] for p in ranker.product_ids])
        b = b / b.max() if b.max() > 0 else b
        e = ranker.model.encode([q["query"]], convert_to_numpy=True)[0]
        m = ranker.product_embeddings
        s = (m @ e / (np.linalg.norm(m, axis=1) * np.linalg.norm(e)) + 1) / 2
        out.append({"query_id": q["query_id"], "bm25_norm_std": float(b.std()), "bm25_norm_mean": float(b.mean()),
                    "semantic_norm_std": float(s.std()), "semantic_norm_mean": float(s.mean()),
                    "semantic_norm_min": float(s.min()), "semantic_norm_max": float(s.max())})
    return out


def main():
    products = load_json(ROOT / "data/products.json")
    queries = load_json(ROOT / "data/queries_synth_train.json")
    labels = str(ROOT / "data/labels_synth_train.json")

    results, spreads = {}, {}
    bm25 = BM25Ranker(products)
    for d in DEPTHS:
        results[f"bm25_depth{d}"] = score(to_rows(queries, lambda t, k: bm25.rank(t, top_k=k), d), labels)

    meta_models = {}
    for key, (name, wb, ws) in MODELS.items():
        ranker = HybridRanker(products, model_name=name)
        meta_models[key] = {"name": name, "revisions": revision_of(name), "bm25_weight": wb, "semantic_weight": ws}
        for d in DEPTHS:
            fn = lambda t, k: ranker.rank(t, top_k=k, bm25_weight=wb, semantic_weight=ws)  # noqa: E731
            results[f"{key}_depth{d}"] = score(to_rows(queries, fn, d), labels)
        spreads[key] = spread(ranker, queries)

    rel = {
        k: round(results[k]["composite"] / results[f"bm25_depth{k.split('depth')[1]}"]["composite"] - 1, 4)
        for k in results if not k.startswith("bm25")
    }
    out = {
        "n_queries": len(queries),
        "claims": {"baseline": 0.6016, "hybrid": 0.6638, "readme_improvement": 0.2567},
        "results": results,
        "relative_improvement_over_bm25_same_depth": rel,
        "score_spread": spreads,
        "models": meta_models,
        "env": {
            "python": sys.version.split()[0], "platform": platform.platform(), "device": "cpu",
            "torch_threads": torch.get_num_threads(),
            **{p: version(p) for p in ("torch", "sentence-transformers", "transformers", "numpy", "rank-bm25")},
        },
    }
    (ROOT / "reports").mkdir(exist_ok=True)
    (ROOT / "reports/baseline_repro.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps({"results": {k: v["composite"] for k, v in results.items()}, "rel": rel}, indent=2))


if __name__ == "__main__":
    main()
