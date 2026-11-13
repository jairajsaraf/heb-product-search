"""Phase 1: honest evaluation harness (5-fold CV on the 230 dev queries).

  .venv/Scripts/python scripts/eval_cv.py --make-split   # once; writes data/split_v1.json
  .venv/Scripts/python scripts/eval_cv.py                # writes reports/cv_baseline.json
  .venv/Scripts/python scripts/eval_cv.py --final        # Phase 6 only: also scores the 58 locked queries

Rankings come from cached raw BM25 scores and cosine similarities, recombined exactly as
BM25Ranker.rank / HybridRanker.rank do. Every ranking is cut at DEPTH=30.
The 58 locked queries are dropped at load time unless --final is passed.
"""
import argparse
import hashlib
import json
import platform
import random
import statistics
import sys
from importlib.metadata import version
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from baseline_ranker import load_json, preprocess_text  # noqa: E402
from tamu25.evaluate import _build_label_lookup  # noqa: E402
from tamu25.metrics import average_precision, ndcg_at_k, precision_at_k, recall_at_k  # noqa: E402

SPLIT = ROOT / "data/split_v1.json"
CACHE = ROOT / ".cache/eval_cv"
DEPTH = 30
SPLIT_SEED = 20261113
N_LOCKED, N_FOLDS, FOLD_SIZE = 58, 5, 46
MODELS = {"minilm": "all-MiniLM-L6-v2", "mpnet": "all-mpnet-base-v2"}
FIXED = {"minilm": 0.3, "mpnet": 0.2}  # Phase 0 bm25 weights (semantic = 1 - w)
GRID = [round(i * 0.05, 2) for i in range(21)]  # bm25 weight; ranking is scale-invariant so semantic = 1 - w
BOOT_N, BOOT_SEED = 10_000, 20261113
LOPSIDED_Z = 3.0


# ---------- split ----------

def load_split(path=SPLIT):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def dev_ids(split):
    return [q for f in split["dev_folds"] for q in f]


def locked_ids(split, final):
    if not final:
        raise PermissionError("locked queries are only readable with --final")
    return list(split["locked"])


def load_data(split, final=False):
    """Queries {qid: text}, labels {qid: {pid: rel}}, total_rel {qid: n}, restricted to allowed ids."""
    allowed = set(dev_ids(split)) | (set(locked_ids(split, final)) if final else set())
    queries = {q["query_id"]: q["query"] for q in load_json(ROOT / "data/queries_synth_train.json")
               if q["query_id"] in allowed}
    lookup, rel = _build_label_lookup([r for r in load_json(ROOT / "data/labels_synth_train.json")
                                       if r["query_id"] in allowed])
    return queries, {q: dict(lookup[q]) for q in queries}, {q: rel[q] for q in queries}


def _z_scores(values_by_id, folds):
    """Fold mean vs overall mean, in standard errors of a 46-query mean."""
    allv = [values_by_id[q] for f in folds for q in f]
    mu, se = statistics.fmean(allv), statistics.stdev(allv) / FOLD_SIZE ** 0.5
    return [round((statistics.fmean(values_by_id[q] for q in f) - mu) / se, 2) for f in folds]


def make_split():
    if SPLIT.exists():
        sys.exit(f"{SPLIT} exists; refusing to overwrite")
    queries = load_json(ROOT / "data/queries_synth_train.json")
    ids = sorted(q["query_id"] for q in queries)
    random.Random(SPLIT_SEED).shuffle(ids)
    locked, dev = ids[:N_LOCKED], ids[N_LOCKED:]
    folds = [dev[i * FOLD_SIZE:(i + 1) * FOLD_SIZE] for i in range(N_FOLDS)]
    # Balance check uses dev labels only; locked queries are compared on query length alone.
    dev_set = set(dev)
    n_labels, n_pos = dict.fromkeys(dev, 0), dict.fromkeys(dev, 0)
    for r in load_json(ROOT / "data/labels_synth_train.json"):
        if r["query_id"] in dev_set:
            n_labels[r["query_id"]] += 1
            n_pos[r["query_id"]] += r["relevance"] >= 1
    qlen = {q["query_id"]: len(preprocess_text(q["query"])) for q in queries}
    z = {"positives_per_query": _z_scores(n_pos, folds), "labels_per_query": _z_scores(n_labels, folds),
         "query_tokens": _z_scores(qlen, folds)}
    lopsided = any(abs(v) > LOPSIDED_Z for vs in z.values() for v in vs)
    out = {
        "version": 1,
        "method": f"sorted train query_ids, random.Random({SPLIT_SEED}).shuffle, first {N_LOCKED} locked, "
                  f"rest cut into {N_FOLDS} consecutive folds of {FOLD_SIZE}",
        "seed": SPLIT_SEED,
        "python": sys.version.split()[0],
        "models": "none used",
        "balance_check": {
            "rule": f"stratify only if a dev fold mean is more than {LOPSIDED_Z} standard errors "
                    "(sd/sqrt(46)) from the dev mean",
            "fold_z": z,
            "locked_vs_dev_mean_query_tokens": [round(statistics.fmean(qlen[q] for q in locked), 2),
                                                round(statistics.fmean(qlen[q] for q in dev), 2)],
            "lopsided": lopsided,
            "stratified": False,
        },
        "locked": locked,
        "dev_folds": folds,
    }
    if lopsided:
        sys.exit(f"plain shuffle is lopsided: {z}; stratification needed, nothing written")
    SPLIT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out["balance_check"], indent=2))


# ---------- metrics ----------

def query_metrics(ranked, qlabels, total_rel):
    """Same per-query numbers as tamu25.evaluate.evaluate_submission (unjudged = 0)."""
    rels = [qlabels.get(p, 0) for p in ranked]
    bins = [1 if r >= 1 else 0 for r in rels]
    m = {"nDCG@10": ndcg_at_k(rels, 10), "AP@20": average_precision(bins, total_rel, 20),
         "P@10": precision_at_k(bins, 10), "R@30": recall_at_k(bins, total_rel, 30)}
    m["composite"] = 0.30 * m["nDCG@10"] + 0.30 * m["AP@20"] + 0.25 * m["R@30"] + 0.15 * m["P@10"]
    return m


def evaluate(ranked, qlabels, total_rel):
    m = query_metrics(ranked, qlabels, total_rel)
    m["judged_only"] = query_metrics([p for p in ranked if p in qlabels], qlabels, total_rel)["composite"]
    m["unjudged_top10"] = sum(p not in qlabels for p in ranked[:10]) / 10
    return m


def paired_bootstrap(a, b, n=BOOT_N, seed=BOOT_SEED):
    d = np.asarray(a, dtype=float) - np.asarray(b, dtype=float)
    idx = np.random.default_rng(seed).integers(0, len(d), size=(n, len(d)))
    means = d[idx].mean(axis=1)
    lo, hi = np.percentile(means, [2.5, 97.5])
    return {"mean_diff": float(d.mean()), "ci95": [float(lo), float(hi)],
            "frac_resamples_gt0": float((means > 0).mean()), "n_queries": len(d), "resamples": n, "seed": seed}


# ---------- rankings from cached scores ----------

def bm25_top(scores, k=DEPTH):
    return scores.argsort()[-k:][::-1]  # identical to BM25Ranker.rank (unstable sort kept on purpose)


def hybrid_top(bm25_scores, cos, w, k=DEPTH):
    """HybridRanker.rank with bm25_weight=w, semantic_weight=1-w, same dtypes and tie order."""
    mx = bm25_scores.max()
    b = bm25_scores / mx if mx > 0 else bm25_scores
    combined = w * b + round(1 - w, 2) * ((cos + 1) / 2)
    return np.argsort(-combined, kind="stable")[:k]


def cached(kind, qids, queries, products, revision, compute):
    h = hashlib.sha256()
    libs = " ".join(version(p) for p in ("torch", "sentence-transformers", "transformers", "numpy", "rank-bm25"))
    for part in ((ROOT / "data/products.json").read_bytes(), (ROOT / "baseline_ranker.py").read_bytes(),
                 (ROOT / "semantic_ranker.py").read_bytes(), libs.encode(),
                 kind.encode(), revision.encode(), "\n".join(qids).encode()):
        h.update(hashlib.sha256(part).digest())
    path = CACHE / f"{kind}_{h.hexdigest()[:16]}.npz"
    if path.exists():
        z = np.load(path)
        return z["scores"], str(z["device"])
    scores, device = compute([queries[q] for q in qids], products)
    CACHE.mkdir(parents=True, exist_ok=True)
    np.savez(path, scores=scores, device=np.array(device))
    return scores, device


def bm25_scores(texts, products):
    from baseline_ranker import BM25Ranker
    r = BM25Ranker(products)
    return np.stack([r.bm25.get_scores(preprocess_text(t)) for t in texts]), "n/a"


def cosine_fn(model_name):
    def compute(texts, products):
        from semantic_ranker import HybridRanker
        r = HybridRanker(products, model_name=model_name)
        e = r.product_embeddings
        out = []
        for t in texts:  # one at a time, exactly as HybridRanker.rank encodes
            q = r.model.encode([t], convert_to_numpy=True)[0]
            out.append(np.dot(e, q) / (np.linalg.norm(e, axis=1) * np.linalg.norm(q)))
        return np.stack(out), str(r.model.device)
    return compute


# ---------- main ----------

def score_all(qids, bm25, cos, products, labels, total_rel):
    """{config: [per-query metrics]} for bm25 and every (model, w) in GRID."""
    pids = [p["product_id"] for p in products]
    out = {"bm25": [evaluate([pids[i] for i in bm25_top(bm25[j])], labels[q], total_rel[q])
                    for j, q in enumerate(qids)]}
    for m in MODELS:
        for w in GRID:
            out[(m, w)] = [evaluate([pids[i] for i in hybrid_top(bm25[j], cos[m][j], w)], labels[q], total_rel[q])
                           for j, q in enumerate(qids)]
    return out


def tune(evals, rows):
    """Best (model, w) by mean official composite over `rows`; first in grid order wins ties."""
    cands = [c for c in evals if c != "bm25"]
    best = max(cands, key=lambda c: sum(evals[c][i]["composite"] for i in rows) / len(rows))
    return best, sum(evals[best][i]["composite"] for i in rows) / len(rows)


def summary(per_q):
    keys = ("composite", "judged_only", "unjudged_top10", "nDCG@10", "AP@20", "P@10", "R@30")
    return {k: round(sum(x[k] for x in per_q) / len(per_q), 4) for k in keys} | {"n_queries": len(per_q)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--final", action="store_true", help="Phase 6 only: score the locked queries")
    ap.add_argument("--make-split", action="store_true")
    args = ap.parse_args()
    if args.make_split:
        return make_split()

    import torch
    from repro_baseline import revision_of

    split = load_split()
    queries, labels, total_rel = load_data(split, args.final)
    products = load_json(ROOT / "data/products.json")
    revisions = {m: revision_of(n) for m, n in MODELS.items()}

    def scores_for(qids, tag):
        bm25, _ = cached(f"bm25_{tag}", qids, queries, products, "", bm25_scores)
        cos, devices = {}, {}
        for m, n in MODELS.items():
            cos[m], devices[m] = cached(f"cos_{m}_{tag}", qids, queries, products, revisions[m], cosine_fn(n))
        return bm25, cos, devices

    dev = dev_ids(split)
    bm25, cos, devices = scores_for(dev, "dev")
    evals = score_all(dev, bm25, cos, products, labels, total_rel)

    fold_of = {q: k for k, f in enumerate(split["dev_folds"]) for q in f}
    folds, tuned = [], [None] * len(dev)
    for k in range(N_FOLDS):
        train = [i for i, q in enumerate(dev) if fold_of[q] != k]
        best, train_score = tune(evals, train)
        folds.append({"fold": k, "model": best[0], "bm25_weight": best[1], "semantic_weight": round(1 - best[1], 2),
                      "train_composite": round(train_score, 4)})
        for i, q in enumerate(dev):
            if fold_of[q] == k:
                tuned[i] = evals[best][i]

    systems = {"bm25": evals["bm25"], "minilm_0.3_0.7": evals[("minilm", FIXED["minilm"])],
               "mpnet_0.2_0.8": evals[("mpnet", FIXED["mpnet"])], "tuned_hybrid_oof": tuned}
    meta = {
        "depth": DEPTH,
        "split": {"file": "data/split_v1.json", "sha256": hashlib.sha256(SPLIT.read_bytes()).hexdigest()},
        "metrics": {
            "composite": "official: tamu25.metrics with evaluate.py weights 0.30 nDCG@10 + 0.30 AP@20 + 0.25 R@30 "
                         "+ 0.15 P@10, unjudged products count as relevance 0",
            "judged_only": "same composite after removing unjudged products from the depth-30 list (no refill); "
                           "total relevant unchanged",
            "unjudged_top10": "per query, fraction of the top 10 with no label for that query (any relevance, "
                              "including 0, counts as judged); averaged over queries",
        },
        "tuning": {"grid_bm25_weight": GRID, "semantic_weight": "1 - bm25_weight", "models": list(MODELS),
                   "criterion": "mean official composite on the 4 training folds; first in (model, weight) order "
                                "wins ties"},
        "models": {m: {"name": n, "revision": revisions[m], "device": devices[m]} for m, n in MODELS.items()},
        "env": {"python": sys.version.split()[0], "platform": platform.platform(),
                "torch_threads": torch.get_num_threads(),
                **{p: version(p) for p in ("torch", "sentence-transformers", "transformers", "numpy", "rank-bm25",
                                           "huggingface-hub")}},
    }

    if args.final:
        locked = locked_ids(split, True)
        lb, lc, _ = scores_for(locked, "locked")
        best, train_score = tune(evals, range(len(dev)))
        levals = score_all(locked, lb, lc, products, labels, total_rel)
        out = {"meta": meta, "config_tuned_on_all_dev": {"model": best[0], "bm25_weight": best[1],
                                                         "dev_composite": round(train_score, 4)},
               "systems": {"bm25": summary(levals["bm25"]), "tuned_hybrid": summary(levals[best])},
               "bootstrap_tuned_vs_bm25": paired_bootstrap([x["composite"] for x in levals[best]],
                                                           [x["composite"] for x in levals["bm25"]])}
        (ROOT / "reports/holdout_final.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
        print(json.dumps(out["systems"], indent=2))
        return

    keep = ("composite", "judged_only", "unjudged_top10")
    out = {
        "meta": meta,
        "systems": {s: summary(v) for s, v in systems.items()},
        "folds": folds,
        "bootstrap_tuned_hybrid_vs_bm25": paired_bootstrap([x["composite"] for x in tuned],
                                                           [x["composite"] for x in evals["bm25"]]),
        "per_query_oof": {q: {"fold": fold_of[q], **{s: {k: v[i][k] for k in keep} for s, v in systems.items()}}
                          for i, q in enumerate(dev)},
    }
    (ROOT / "reports/cv_baseline.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps({"systems": out["systems"], "folds": folds,
                      "bootstrap": out["bootstrap_tuned_hybrid_vs_bm25"]}, indent=2))


if __name__ == "__main__":
    main()
