"""Phase 6b (spec M13): latency of the served search path on the 191 unlabelled test queries, warm, CPU.

  .venv/Scripts/python scripts/build_index.py   # once: artifacts/index.npz
  .venv/Scripts/python scripts/latency.py       # writes reports/latency.json

Times Searcher.search(q, 30), the function behind GET /search (no HTTP layer), at torch's default thread count,
which is what uvicorn runs with. Also checks, on the 230 dev queries, that Searcher.search returns the same top 30
as the harness ranking scored in reports/holdout_final.json (needs the dev score cache written by eval_cv.py).
Locked queries are never read.
"""
import json
import os
import platform
import sys
import time
from importlib.metadata import version
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import eval_cv as E  # noqa: E402
from tamu25.api.app import build_searcher  # noqa: E402
from tamu25.api.search import BM25_WEIGHT, MODEL_NAME, MODEL_REVISION, Searcher  # noqa: E402

OUT = ROOT / "reports/latency.json"
K = 30


def main():
    import torch

    hybrid = build_searcher(ROOT / "data", ROOT / "artifacts/index.npz")
    systems = {"final_hybrid": hybrid, "bm25_only": Searcher(hybrid.products)}

    # Served path == scored path, on dev queries.
    split = E.load_split()
    queries, _, _ = E.load_data(split)
    dev = E.dev_ids(split)
    model = next(m for m, n in E.MODELS.items() if n == MODEL_NAME)
    bm25, _ = E.cached("bm25_dev", dev, queries, hybrid.products, "", E.bm25_scores)
    cos, _ = E.cached(f"cos_{model}_dev", dev, queries, hybrid.products, MODEL_REVISION, E.cosine_fn(MODEL_NAME))
    pids = [p["product_id"] for p in hybrid.products]
    overlap = []
    for j, q in enumerate(dev):
        served = [r["product_id"] for r in hybrid.search(queries[q], K)["results"]]
        scored = [pids[i] for i in E.hybrid_top(bm25[j], cos[j], BM25_WEIGHT)]
        overlap.append(K + 1 if served == scored else len(set(served) & set(scored)))  # K+1 marks same order too

    texts = [q["query"] for q in E.load_json(ROOT / "data/queries_synth_test.json")]
    names = list(systems)
    for t in texts:  # warm-up: one untimed pass over every query
        for n in names:
            systems[n].search(t, K)
    ms = {n: [] for n in names}
    for i, t in enumerate(texts):
        for n in names[i % len(names):] + names[:i % len(names)]:  # interleaved, order rotated per query
            t0 = time.perf_counter()
            systems[n].search(t, K)
            ms[n].append((time.perf_counter() - t0) * 1000)

    out = {
        "method": f"Searcher.search(q, {K}) per query, no HTTP layer; one untimed warm-up pass over all queries, "
                  "then one timed pass with the two systems interleaved",
        "queries": {"file": "data/queries_synth_test.json", "n": len(texts)},
        "config": {"model": MODEL_NAME, "revision": MODEL_REVISION, "bm25_weight": BM25_WEIGHT,
                   "index": "artifacts/index.npz (scripts/build_index.py)"},
        "machine": {"cpu": platform.processor(), "logical_cpus": os.cpu_count(), "platform": platform.platform(),
                    "device": str(hybrid.encoder.device), "torch_threads": torch.get_num_threads()},
        "env": {"python": sys.version.split()[0],
                **{p: version(p) for p in ("torch", "sentence-transformers", "numpy", "rank-bm25")}},
        "latency_ms": {n: {"p50": round(float(np.percentile(v, 50)), 1), "p95": round(float(np.percentile(v, 95)), 1),
                           "mean": round(float(np.mean(v)), 1), "max": round(float(np.max(v)), 1)}
                       for n, v in ms.items()},
        "served_path_check": {"queries": "230 dev", "depth": K,
                              "identical_order": sum(o == K + 1 for o in overlap),
                              "same_set_different_order": sum(o == K for o in overlap),
                              "min_shared_products": min(min(o, K) for o in overlap)},
    }
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("machine", "latency_ms", "served_path_check")}, indent=2))


if __name__ == "__main__":
    main()
