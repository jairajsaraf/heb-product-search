"""Writes frontend/src/evidence.json and frontend/src/examples.json. Run from the repo root."""
import json
import os
import sys
from pathlib import Path

os.environ["HF_HUB_OFFLINE"] = "1"
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from tamu25.api.app import build_searcher  # noqa: E402
from tamu25.api.search import BM25_WEIGHT  # noqa: E402

HO, CV, CR, LAT = "reports/holdout_final.json", "reports/cv_baseline.json", "reports/cv_results.json", "reports/latency.json"
SPLIT = "data/split_v1.json"
FACTS = {  # key: (source, path, op)
    "catalog.products": ("data/products.json", [], "len"),
    "split.locked": (SPLIT, ["locked"], "len"),
    "split.dev": (SPLIT, ["dev_folds"], "sum_len"),
    "config.bm25_weight": (LAT, ["config", "bm25_weight"], "value"),
    "config.model": (LAT, ["config", "model"], "value"),
    "latency.n_queries": (LAT, ["queries", "n"], "value"),
    "latency.logical_cpus": (LAT, ["machine", "logical_cpus"], "value"),
    "latency.torch_threads": (LAT, ["machine", "torch_threads"], "value"),
}
BH = ["bootstrap_tuned_vs_bm25"]
FACTS["holdout.n_queries"] = (HO, BH + ["composite", "n_queries"], "value")
FACTS["holdout.resamples"] = (HO, BH + ["composite", "resamples"], "value")
for name, (sec, bk) in {"official": ("composite", "composite"), "judged": ("judged_only", "judged_only")}.items():
    FACTS[f"holdout.{name}.bm25"] = (HO, ["systems", "bm25", sec], "value")
    FACTS[f"holdout.{name}.hybrid"] = (HO, ["systems", "tuned_hybrid", sec], "value")
    FACTS[f"holdout.{name}.diff"] = (HO, BH + [bk, "mean_diff"], "value")
    FACTS[f"holdout.{name}.ci_low"] = (HO, BH + [bk, "ci95", 0], "value")
    FACTS[f"holdout.{name}.ci_high"] = (HO, BH + [bk, "ci95", 1], "value")
for k, sys_ in (("bm25", "bm25"), ("hybrid", "tuned_hybrid")):
    FACTS[f"holdout.unjudged_top10.{k}"] = (HO, ["systems", sys_, "unjudged_top10"], "value")
    for fk, m in (("ndcg10", "nDCG@10"), ("ap20", "AP@20"), ("p10", "P@10"), ("r30", "R@30")):
        FACTS[f"holdout.{fk}.{k}"] = (HO, ["systems", sys_, m], "value")
CB = ["bootstrap_tuned_hybrid_vs_bm25"]
FACTS["cv.n_queries"] = (CV, CB + ["n_queries"], "value")
FACTS["cv.official.bm25"] = (CV, ["systems", "bm25", "composite"], "value")
FACTS["cv.official.hybrid"] = (CV, ["systems", "tuned_hybrid_oof", "composite"], "value")
FACTS["cv.official.diff"] = (CV, CB + ["mean_diff"], "value")
FACTS["cv.official.ci_low"] = (CV, CB + ["ci95", 0], "value")
FACTS["cv.official.ci_high"] = (CV, CB + ["ci95", 1], "value")
for m, s in (("official", "composite"), ("judged", "judged_only"), ("unjudged_top10", "unjudged_top10")):
    FACTS[f"tried.baseline.{m}"] = (CR, ["systems", "baseline", s], "value")
for sysn in ("rrf", "rerank"):
    cmp_ = ["comparisons", f"{sysn}_vs_baseline"]
    for m, s in (("official", "composite"), ("judged", "judged_only"), ("unjudged_top10", "unjudged_top10")):
        FACTS[f"tried.{sysn}.{m}"] = (CR, ["systems", sysn, s], "value")
    FACTS[f"tried.{sysn}.diff"] = (CR, cmp_ + ["official", "mean_diff"], "value")
    FACTS[f"tried.{sysn}.ci_low"] = (CR, cmp_ + ["official", "ci95", 0], "value")
    FACTS[f"tried.{sysn}.ci_high"] = (CR, cmp_ + ["official", "ci95", 1], "value")
    FACTS[f"tried.{sysn}.decision"] = (CR, cmp_ + ["decision"], "value")
FACTS["tried.rerank.judged_diff"] = (CR, ["comparisons", "rerank_vs_baseline", "judged_only", "mean_diff"], "value")
FACTS["tried.rerank.judged_ci_low"] = (CR, ["comparisons", "rerank_vs_baseline", "judged_only", "ci95", 0], "value")
FACTS["tried.rerank.judged_ci_high"] = (CR, ["comparisons", "rerank_vs_baseline", "judged_only", "ci95", 1], "value")
for k, sysn in (("hybrid", "final_hybrid"), ("bm25", "bm25_only")):
    for p in ("p50", "p95"):
        FACTS[f"latency.{k}.{p}"] = (LAT, ["latency_ms", sysn, p], "value")

EXAMPLES = [("s530", "lead"), ("s98", "meaning"), ("s4", "meaning"), ("s206", "keyword"), ("s435", "fail")]


def load(rel):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def compute(doc, path, op):
    for p in path:
        doc = doc[p]  # raises KeyError/IndexError naming the bad step
    if op == "len":
        return len(doc)
    if op == "sum_len":
        return sum(len(x) for x in doc)
    return doc


def write(rel, obj):
    (ROOT / rel).write_text(json.dumps(obj, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def main():
    cache, facts = {}, {}
    for key, (src, path, op) in FACTS.items():
        doc = cache.setdefault(src, load(src))
        try:
            val = compute(doc, path, op)
        except (KeyError, IndexError, TypeError) as e:
            raise SystemExit(f"missing path for {key}: {src} {path} ({e!r})")
        facts[key] = {"value": val, "source": src, "path": path, "op": op}
    write("frontend/src/evidence.json", {"facts": facts})

    ids = [i for i, _ in EXAMPLES]
    locked = set(load(SPLIT)["locked"])
    if locked & set(ids):
        raise SystemExit("example id is in locked split")
    texts = {q["query_id"]: q["query"] for q in load("data/queries_synth_train.json") if q["query_id"] in ids}
    grades = {}
    for r in load("data/labels_synth_train.json"):
        if r["query_id"] in ids:
            grades[(r["query_id"], r["product_id"])] = r["relevance"]
    searcher = build_searcher("data", "artifacts/index.npz")
    assert searcher.mode == "hybrid"

    def rows(qid, res):
        return [{"rank": r["rank"], "product_id": r["product_id"], "title": r["title"], "brand": r["brand"],
                 "score": r["score"], "bm25_score": r["bm25_score"], "semantic_score": r["semantic_score"],
                 "grade": grades.get((qid, r["product_id"]))} for r in res["results"]]

    out = []
    for qid, role in EXAMPLES:
        q = texts[qid]
        out.append({"id": qid, "query": q, "role": role,
                    "hybrid": rows(qid, searcher.search(q, 10)),
                    "keyword": rows(qid, searcher.search(q, 10, mode="bm25"))})
    write("frontend/src/examples.json", {"bm25_weight": BM25_WEIGHT, "examples": out})
    print(len(facts), "facts;", len(out), "examples")
    for e in out:
        g = lambda rs: "".join("U" if r["grade"] is None else str(r["grade"]) for r in rs)
        print(e["id"], e["role"], "hybrid", g(e["hybrid"]), "keyword", g(e["keyword"]))


main()
