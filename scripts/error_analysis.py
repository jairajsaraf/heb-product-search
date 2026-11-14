"""Phase 2: error-analysis data for the 230 dev queries (never the locked 58).

  .venv/Scripts/python scripts/error_analysis.py   # writes reports/error_analysis.json

Rebuilds the tuned-hybrid out-of-fold rankings from reports/cv_baseline.json (per-fold model and
weight) and the eval_cv score cache, asserts they reproduce the Phase 1 per-query composites, then
records per-query diagnostics, rule-based buckets and the worst 20 queries. No candidate change is
scored here; that is Phase 3.
"""
import hashlib
import json
import platform
import re
import sys
from importlib.metadata import version
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT)]

import eval_cv as E  # noqa: E402
from baseline_ranker import load_json  # noqa: E402

CV = ROOT / "reports/cv_baseline.json"
OUT = ROOT / "reports/error_analysis.json"
N_WORST, CANDIDATE_DEPTH, LABEL_HOLE_MIN, CATEGORY_MISS_MIN = 20, 50, 6, 3

# Bucket rules, fixed before any per-query outcome was read. Text buckets look at the query only.
ATTR_TERMS = ["gluten", "dairy", "lactose", "nut", "nuts", "peanut", "wheat", "egg", "eggs", "sugar", "sodium",
              "msg", "bpa", "hormone", "hormones", "antibiotic", "antibiotics", "preservative", "preservatives",
              "artificial", "organic", "organics", "kosher", "vegan", "vegetarian", "plant", "grain", "cholesterol",
              "calorie", "fiber", "protein", "rbst", "fragrance"]
NEG_TERMS = ["no", "non", "not", "without", "zero", "free", "unsweetened"]
SIZE_RE = r"\d|\b(pack|count|ct|oz|lb|lbs|size|bulk|family)\b"
# Values of the catalog `brand` field that are descriptors, not brands (data-quality issue, listed only).
NOT_BRANDS = {"american", "chipotle lime", "flat", "french", "fresh", "frozen", "haddock", "jumbo", "live", "lump",
              "market", "natural", "natural pork", "natural prime", "previously frozen", "purified", "removed",
              "seasonal", "southwest", "usda", "wagyu", "whole", "wild"}


def norm_brand(s):
    return re.sub(r"\s+by h-e-b$", "", (s or "").lower().replace("&", "+")).strip()


def words_re(terms):
    return re.compile(r"\b(" + "|".join(map(re.escape, terms)) + r")\b")


def l2(product):
    parts = [c.strip() for c in product["category_path"].split("->")]
    return parts[1] if len(parts) > 1 else parts[0]


def ranks_of(order):
    r = np.empty(len(order), dtype=int)
    r[order] = np.arange(1, len(order) + 1)
    return r


def main():
    from repro_baseline import revision_of

    cv = json.loads(CV.read_text(encoding="utf-8"))
    split = E.load_split()
    queries, labels, total_rel = E.load_data(split, final=False)
    dev = E.dev_ids(split)
    products = load_json(ROOT / "data/products.json")
    pids = [p["product_id"] for p in products]
    pidx = {p: i for i, p in enumerate(pids)}
    n = len(pids)

    revisions = {m: revision_of(name) for m, name in E.MODELS.items()}
    bm25, _ = E.cached("bm25_dev", dev, queries, products, "", E.bm25_scores)
    cos, devices = {}, {}
    for m, name in E.MODELS.items():
        cos[m], devices[m] = E.cached(f"cos_{m}_dev", dev, queries, products, revisions[m], E.cosine_fn(name))

    brands = sorted({norm_brand(p["brand"]) for p in products if p.get("brand")} - NOT_BRANDS - {""}, key=len,
                    reverse=True)
    brand_re, attr_re, neg_re, size_re = words_re(brands), words_re(ATTR_TERMS), words_re(NEG_TERMS), re.compile(SIZE_RE)
    pbrand = [norm_brand(p.get("brand")) for p in products]
    pcat = [l2(p) for p in products]

    fold_of = {q: k for k, f in enumerate(split["dev_folds"]) for q in f}
    cfg = {f["fold"]: (f["model"], f["bm25_weight"]) for f in cv["folds"]}
    rows = []
    for j, q in enumerate(dev):
        model, w = cfg[fold_of[q]]
        order = E.hybrid_top(bm25[j], cos[model][j], w, k=n)
        top30 = [pids[i] for i in order[:E.DEPTH]]
        ev = E.evaluate(top30, labels[q], total_rel[q])
        assert ev["composite"] == cv["per_query_oof"][q]["tuned_hybrid_oof"]["composite"], q
        r_h = ranks_of(order)
        r_b = ranks_of(bm25[j].argsort()[::-1])  # BM25Ranker order, full depth
        r_s = ranks_of(E.hybrid_top(bm25[j], cos[model][j], 0.0, k=n))  # semantic only, same model
        top10 = order[:10]
        lab = labels[q]

        reach = {"rank_11_30": 0, "rank_31_50": 0, "fusion_bm25": 0, "fusion_semantic_only": 0, "unreachable": 0}
        missing = []
        for pid, rel in lab.items():
            if rel < 1:
                continue
            i = pidx[pid]
            if r_h[i] <= 10:
                continue
            if r_h[i] <= 30:
                reach["rank_11_30"] += 1
            elif r_h[i] <= CANDIDATE_DEPTH:
                reach["rank_31_50"] += 1
            elif r_b[i] <= CANDIDATE_DEPTH:
                reach["fusion_bm25"] += 1
            elif r_s[i] <= CANDIDATE_DEPTH:
                reach["fusion_semantic_only"] += 1
            else:
                reach["unreachable"] += 1
            missing.append({"product_id": pid, "label": rel, "hybrid_rank": int(r_h[i]), "bm25_rank": int(r_b[i]),
                            "semantic_rank": int(r_s[i]), "title": products[i]["title"]})

        text = queries[q].lower().replace("&", "+")
        bm = brand_re.search(text)
        rel_cats = {pcat[pidx[p]] for p, rel in lab.items() if rel >= 1}
        cat_miss = sum(pcat[i] not in rel_cats for i in top10)
        buckets = [b for b, hit in (("brand", bm), ("ingredient_allergen", attr_re.search(text)),
                                    ("negation", neg_re.search(text)), ("size", size_re.search(text)),
                                    ("category_confusion", cat_miss >= CATEGORY_MISS_MIN),
                                    ("label_hole", sum(pids[i] not in lab for i in top10) >= LABEL_HOLE_MIN)) if hit]
        rows.append({
            "query_id": q, "query": queries[q], "fold": fold_of[q], "model": model, "bm25_weight": w,
            "composite": ev["composite"], "judged_only": ev["judged_only"],
            "bm25_composite": cv["per_query_oof"][q]["bm25"]["composite"],
            "top10_relevant": sum(lab.get(pids[i], 0) >= 1 for i in top10),
            "top10_judged_irrelevant": sum(lab.get(pids[i], -1) == 0 for i in top10),
            "top10_unjudged": sum(pids[i] not in lab for i in top10),
            "total_relevant": total_rel[q], "reach": reach, "category_miss_top10": cat_miss,
            "brand": bm.group(0) if bm else None,
            "top10_wrong_brand": sum(bm.group(0) not in pbrand[i] for i in top10) if bm else None,
            "buckets": buckets,
            "_top10": [{"rank": r, "product_id": pids[i], "title": products[i]["title"], "brand": products[i]["brand"],
                        "category": pcat[i], "label": lab.get(pids[i])} for r, i in enumerate(top10, 1)],
            "_missing_top3": sorted(missing, key=lambda x: (-x["label"], x["hybrid_rank"]))[:3],
        })

    def bucket_stats(sel, worst_ids):
        def mean(key, rs):
            return round(sum(r[key] for r in rs) / len(rs), 4) if rs else None
        rest = [r for r in rows if r not in sel]
        return {"n": len(sel), "n_in_worst20": sum(r["query_id"] in worst_ids for r in sel),
                "mean_composite": mean("composite", sel), "mean_composite_rest": mean("composite", rest),
                "mean_top10_judged_irrelevant": mean("top10_judged_irrelevant", sel),
                "mean_top10_judged_irrelevant_rest": mean("top10_judged_irrelevant", rest),
                "mean_top10_unjudged": mean("top10_unjudged", sel),
                "reach_totals": {k: sum(r["reach"][k] for r in sel) for k in rows[0]["reach"]}}

    worst = sorted(rows, key=lambda r: r["composite"])[:N_WORST]
    worst_ids = {r["query_id"] for r in worst}
    names = ["brand", "ingredient_allergen", "negation", "size", "category_confusion", "label_hole"]
    brand_rows = [r for r in rows if r["brand"]]
    out = {
        "meta": {
            "source": {"cv_baseline_sha256": hashlib.sha256(CV.read_bytes()).hexdigest(),
                       "split_sha256": hashlib.sha256(E.SPLIT.read_bytes()).hexdigest()},
            "ranking": "tuned hybrid, out-of-fold: each query ranked with its fold's (model, bm25_weight) from "
                       "cv_baseline.json; composites asserted equal to Phase 1",
            "rules": {"ingredient_allergen_terms": ATTR_TERMS, "negation_terms": NEG_TERMS, "size_regex": SIZE_RE,
                      "brand": "longest catalog brand (lowercased, & -> +, ' by H-E-B' stripped) found as whole words "
                               "in the query, excluding not_brands", "not_brands": sorted(NOT_BRANDS),
                      "category_confusion": f">= {CATEGORY_MISS_MIN} of top 10 in a level-2 category holding none "
                                            "of the query's relevant (label >= 1) items",
                      "label_hole": f">= {LABEL_HOLE_MIN} of top 10 unjudged",
                      "reach": "each relevant item outside the hybrid top 10: hybrid rank 11-30, 31-50; beyond hybrid "
                               "50 but within BM25-only top 50 (fusion_bm25); beyond both but within semantic-only "
                               "top 50, same model (fusion_semantic_only); or unreachable"},
            "models": {m: {"name": nm, "revision": revisions[m], "device": devices[m]} for m, nm in E.MODELS.items()},
            "env": {"python": sys.version.split()[0], "platform": platform.platform(),
                    **{p: version(p) for p in ("torch", "sentence-transformers", "transformers", "numpy",
                                               "rank-bm25", "huggingface-hub")}},
        },
        "dev_mean_composite": round(sum(r["composite"] for r in rows) / len(rows), 4),
        "reach_totals_all": {k: sum(r["reach"][k] for r in rows) for k in rows[0]["reach"]},
        "buckets": {b: bucket_stats([r for r in rows if b in r["buckets"]], worst_ids) for b in names}
                   | {"none": bucket_stats([r for r in rows if not r["buckets"]], worst_ids)},
        "brand_queries_top10_wrong_brand_mean": round(sum(r["top10_wrong_brand"] for r in brand_rows)
                                                      / len(brand_rows), 4),
        "worst20": [{k.lstrip("_"): v for k, v in r.items()} for r in worst],
        "per_query": [{k: v for k, v in r.items() if not k.startswith("_")} for r in rows],
    }
    OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("dev_mean_composite", "reach_totals_all", "buckets",
                                          "brand_queries_top10_wrong_brand_mean")}, indent=2))


if __name__ == "__main__":
    main()
