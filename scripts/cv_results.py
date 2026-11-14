"""Phase 3: measure the two flagged changes (RRF fusion, cross-encoder rerank) on the 230 dev queries.

  .venv/Scripts/python scripts/cv_results.py   # writes reports/cv_results.json

- Baseline: the Phase 1 tuned hybrid (per-fold model and weight), asserted equal to cv_baseline.json.
- RRF: model and k tuned on the 4 training folds per fold, scored out of fold.
- Rerank: each query's baseline top 50 (its fold's config) reordered by the cross-encoder; no new tunable.
- Combination: only if both pass alone; RRF's per-fold top 50, reranked.
- Keep rule: official composite gain over the baseline with a 95% bootstrap interval above 0. A change that
  fails while its judged-only score rises is "inconclusive" and not kept.
- Latency: end to end through HybridRanker.rank, warm, CPU, LATENCY_THREADS threads, configs interleaved.
The 58 locked queries are never loaded (load_data(final=False)).
"""
import hashlib
import json
import platform
import statistics
import sys
import time
from collections import Counter
from importlib.metadata import version
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT)]

import eval_cv as E  # noqa: E402
import semantic_ranker as sr  # noqa: E402
from baseline_ranker import load_json  # noqa: E402

OUT = ROOT / "reports/cv_results.json"
CV = ROOT / "reports/cv_baseline.json"
RRF_K = [1, 5, 10, 20, 40, 60, 100]  # fixed before any Phase 3 result was seen
RERANK_DEPTH = 50
LATENCY_THREADS = 12  # best in the Phase 3 thread check (scratch timing, 12-16 threads)
LATENCY_QUERIES = slice(0, 230, 5)  # every 5th dev query: 46 queries
EQUIV_QUERIES = slice(0, 230, 23)  # 10 dev queries: shipped HybridRanker.rank vs cached path
LIBS = ("torch", "sentence-transformers", "transformers", "numpy", "rank-bm25", "huggingface-hub")


def ce_cached(kind, query_texts, cand_texts):
    """Cross-encoder scores [query][candidate], one predict call per query (as HybridRanker.rank does).
    Keyed on the exact (query, product text) pairs, model revision and library versions."""
    h = hashlib.sha256()
    for part in [sr.RERANKER_MODEL, sr.RERANKER_REVISION, " ".join(version(p) for p in LIBS)]:
        h.update(part.encode())
    for q, cands in zip(query_texts, cand_texts):
        h.update(json.dumps([q, cands]).encode())
    path = E.CACHE / f"ce_{kind}_{h.hexdigest()[:16]}.npz"
    if path.exists():
        z = np.load(path)
        return z["scores"], str(z["device"])
    ce = sr.CrossEncoder(sr.RERANKER_MODEL, revision=sr.RERANKER_REVISION)
    scores = np.stack([sr.rerank_scores(ce, q, c) for q, c in zip(query_texts, cand_texts)]).astype(np.float32)
    E.CACHE.mkdir(parents=True, exist_ok=True)
    np.savez(path, scores=scores, device=np.array(str(ce.device)))
    return scores, str(ce.device)


def oof(evals, fold_of, dev):
    """Per-fold tuning on the other 4 folds; returns per-query OOF metrics and the per-fold choices."""
    per_q, choices = [None] * len(dev), []
    for k in range(E.N_FOLDS):
        best, score = E.tune(evals, [i for i, q in enumerate(dev) if fold_of[q] != k])
        choices.append({"fold": k, "config": list(best), "train_composite": round(score, 4)})
        for i, q in enumerate(dev):
            if fold_of[q] == k:
                per_q[i] = evals[best][i]
    return per_q, choices


def compare(cand, base):
    off = E.paired_bootstrap([x["composite"] for x in cand], [x["composite"] for x in base])
    jo = E.paired_bootstrap([x["judged_only"] for x in cand], [x["judged_only"] for x in base])
    decision = "pass" if off["ci95"][0] > 0 else ("inconclusive" if jo["mean_diff"] > 0 else "fail")
    return {"official": off, "judged_only": jo, "decision": decision}


def main():
    import torch
    from repro_baseline import revision_of

    split = E.load_split()
    queries, labels, total_rel = E.load_data(split, final=False)
    dev = E.dev_ids(split)
    products = load_json(ROOT / "data/products.json")
    pids = [p["product_id"] for p in products]
    texts = [sr.rerank_text(p) for p in products]
    fold_of = {q: k for k, f in enumerate(split["dev_folds"]) for q in f}
    cv = json.loads(CV.read_text(encoding="utf-8"))

    revisions = {m: revision_of(n) for m, n in E.MODELS.items()}
    bm25, _ = E.cached("bm25_dev", dev, queries, products, "", E.bm25_scores)
    cos, devices = {}, {}
    for m, n in E.MODELS.items():
        cos[m], devices[m] = E.cached(f"cos_{m}_dev", dev, queries, products, revisions[m], E.cosine_fn(n))

    def ev(j, order):
        q = dev[j]
        return E.evaluate([pids[i] for i in order[:E.DEPTH]], labels[q], total_rel[q])

    # Baseline: Phase 1 tuned hybrid, reproduced exactly.
    lin = E.score_all(dev, bm25, cos, products, labels, total_rel)
    lin.pop("bm25")
    base, base_folds = oof(lin, fold_of, dev)
    for i, q in enumerate(dev):
        assert base[i]["composite"] == cv["per_query_oof"][q]["tuned_hybrid_oof"]["composite"], q
    base_cfg = {f["fold"]: tuple(f["config"]) for f in base_folds}
    base_top = [E.hybrid_top(bm25[j], cos[base_cfg[fold_of[q]][0]][j], base_cfg[fold_of[q]][1], k=RERANK_DEPTH)
                for j, q in enumerate(dev)]

    # RRF.
    def rrf_top(j, m, k, depth=E.DEPTH):
        return np.argsort(-sr.rrf_fuse(bm25[j], cos[m][j], k), kind="stable")[:depth]

    rrf_evals = {(m, k): [ev(j, rrf_top(j, m, k)) for j in range(len(dev))] for m in E.MODELS for k in RRF_K}
    rrf, rrf_folds = oof(rrf_evals, fold_of, dev)
    rrf_cfg = {f["fold"]: tuple(f["config"]) for f in rrf_folds}

    # Rerank of the baseline top 50.
    ce_base, ce_device = ce_cached("baseline", [queries[q] for q in dev], [[texts[i] for i in t] for t in base_top])
    rerank = [ev(j, sr.rerank_order(base_top[j], ce_base[j])) for j in range(len(dev))]

    comparisons = {"rrf_vs_baseline": compare(rrf, base), "rerank_vs_baseline": compare(rerank, base)}
    systems = {"baseline": base, "rrf": rrf, "rerank": rerank}
    combo_top = None
    if all(comparisons[c]["decision"] == "pass" for c in comparisons):
        combo_top = [rrf_top(j, *rrf_cfg[fold_of[q]], depth=RERANK_DEPTH) for j, q in enumerate(dev)]
        ce_rrf, _ = ce_cached("rrf", [queries[q] for q in dev], [[texts[i] for i in t] for t in combo_top])
        systems["rrf_rerank"] = [ev(j, sr.rerank_order(combo_top[j], ce_rrf[j])) for j in range(len(dev))]
        for other in ("baseline", "rrf", "rerank"):
            comparisons[f"rrf_rerank_vs_{other}"] = compare(systems["rrf_rerank"], systems[other])

    passed = [s for s in ("rrf", "rerank") if comparisons[f"{s}_vs_baseline"]["decision"] == "pass"]
    if "rrf_rerank" in systems and all(comparisons[f"rrf_rerank_vs_{o}"]["decision"] == "pass"
                                       for o in ("rrf", "rerank")):
        final = "rrf_rerank"
    elif passed:
        final = max(passed, key=lambda s: statistics.fmean(x["composite"] for x in systems[s]))
    else:
        final = "baseline"

    # Shipped-path check and latency, through HybridRanker.rank.
    lat_base = Counter(base_cfg.values()).most_common(1)[0][0]
    lat_rrf = Counter(rrf_cfg.values()).most_common(1)[0][0]
    rankers = {m: sr.HybridRanker(products, model_name=E.MODELS[m], reranker_model=sr.RERANKER_MODEL,
                                  reranker_revision=sr.RERANKER_REVISION) for m in {lat_base[0], lat_rrf[0]}}
    lat_cfgs = {
        "baseline": (lat_base[0], dict(bm25_weight=lat_base[1], semantic_weight=round(1 - lat_base[1], 2))),
        "rrf": (lat_rrf[0], dict(fusion="rrf", rrf_k=lat_rrf[1])),
        "rerank": (lat_base[0], dict(bm25_weight=lat_base[1], semantic_weight=round(1 - lat_base[1], 2),
                                     rerank=True, rerank_depth=RERANK_DEPTH)),
        "rrf_rerank": (lat_rrf[0], dict(fusion="rrf", rrf_k=lat_rrf[1], rerank=True, rerank_depth=RERANK_DEPTH)),
    }

    def run(name, q):
        m, kw = lat_cfgs[name]
        return [p for p, _ in rankers[m].rank(q, top_k=E.DEPTH, **kw)]

    checked = 0  # default threads, same as the cached scores
    for j in range(len(dev))[EQUIV_QUERIES]:
        q, k = dev[j], fold_of[dev[j]]
        if base_cfg[k] == lat_base:
            assert run("baseline", queries[q]) == [pids[i] for i in base_top[j][:E.DEPTH]], q
            assert run("rerank", queries[q]) == [pids[i] for i in sr.rerank_order(base_top[j], ce_base[j])[:E.DEPTH]], q
            checked += 2
        if rrf_cfg[k] == lat_rrf:
            assert run("rrf", queries[q]) == [pids[i] for i in rrf_top(j, *lat_rrf)], q
            checked += 1

    default_threads = torch.get_num_threads()
    torch.set_num_threads(LATENCY_THREADS)
    lat_q = [queries[q] for q in dev[LATENCY_QUERIES]]
    names = list(lat_cfgs)
    for n in names:
        run(n, lat_q[0])  # warm-up
    ms = {n: [] for n in names}
    for i, q in enumerate(lat_q):
        for n in names[i % len(names):] + names[:i % len(names)]:
            t0 = time.perf_counter()
            run(n, q)
            ms[n].append((time.perf_counter() - t0) * 1000)
    torch.set_num_threads(default_threads)

    out = {
        "meta": {
            "source": {"cv_baseline_sha256": hashlib.sha256(CV.read_bytes()).hexdigest(),
                       "split_sha256": hashlib.sha256(E.SPLIT.read_bytes()).hexdigest()},
            "depth": E.DEPTH,
            "rrf": {"k_grid": RRF_K, "models": list(E.MODELS), "ranks": "tie-aware (equal scores share the best "
                    "rank)", "selection": "mean official composite on the 4 training folds; first in (model, k) "
                    "order wins ties"},
            "rerank": {"model": sr.RERANKER_MODEL, "revision": sr.RERANKER_REVISION, "device": ce_device,
                       "depth": RERANK_DEPTH, "candidates": "each query's baseline top 50 (its fold's config)",
                       "product_text": "title. Brand: brand. Category: category_path. description",
                       "score": "pure cross-encoder reorder of the top 50, stable; ranks 51+ unchanged"},
            "combination": "run only if both pass alone; RRF per-fold config chosen by RRF composite, its top 50 "
                           "reranked",
            "keep_rule": "official composite 95% paired-bootstrap interval vs baseline above 0; fail with "
                         "judged-only mean diff > 0 is inconclusive; neither passes -> final is the baseline",
            "models": {m: {"name": n, "revision": revisions[m], "device": devices[m]} for m, n in E.MODELS.items()},
            "scoring_threads": default_threads,
            "env": {"python": sys.version.split()[0], "platform": platform.platform(), "cpu": platform.processor(),
                    **{p: version(p) for p in LIBS}},
        },
        "systems": {s: E.summary(v) for s, v in systems.items()},
        "folds": {"baseline": base_folds, "rrf": rrf_folds},
        "comparisons": comparisons,
        "final_system": final,
        "shipped_path_check": {"queries": dev[EQUIV_QUERIES], "rankings_compared": checked,
                               "result": "HybridRanker.rank top 30 identical to the cached path"},
        "latency_ms": {
            "threads": LATENCY_THREADS, "device": "cpu", "queries": dev[LATENCY_QUERIES],
            "method": "HybridRanker.rank(top_k=30), warm, configs interleaved per query",
            "configs": {n: {"model": lat_cfgs[n][0], **lat_cfgs[n][1]} for n in names},
            "per_query": {n: {"p50": round(float(np.percentile(v, 50)), 1),
                              "p95": round(float(np.percentile(v, 95)), 1)} for n, v in ms.items()},
        },
        "per_query_oof": {q: {s: {k: v[i][k] for k in ("composite", "judged_only", "unjudged_top10")}
                              for s, v in systems.items()} for i, q in enumerate(dev)},
    }
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("systems", "folds", "final_system", "shipped_path_check", "latency_ms")}
                     | {"comparisons": {c: {"official": v["official"]["mean_diff"], "ci95": v["official"]["ci95"],
                                            "judged_only": v["judged_only"]["mean_diff"],
                                            "decision": v["decision"]} for c, v in comparisons.items()}},
                     indent=2))


if __name__ == "__main__":
    main()
