import json
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

import eval_cv  # noqa: E402
from baseline_ranker import BM25Ranker, load_json, preprocess_text  # noqa: E402
from tamu25.evaluate import evaluate_submission  # noqa: E402


@pytest.fixture(scope="module")
def split():
    return eval_cv.load_split()


def test_no_locked_id_in_any_fold(split):
    locked = set(split["locked"])
    folds = split["dev_folds"]
    assert len(locked) == len(split["locked"]) == 58
    assert [len(f) for f in folds] == [46] * 5
    dev = [q for f in folds for q in f]
    assert len(set(dev)) == 230
    assert not locked & set(dev)
    train_ids = {q["query_id"] for q in load_json(ROOT / "data/queries_synth_train.json")}
    assert locked | set(dev) == train_ids


def test_locked_queries_refused_without_final(split):
    with pytest.raises(PermissionError):
        eval_cv.locked_ids(split, final=False)
    queries, labels, _ = eval_cv.load_data(split, final=False)
    assert not set(split["locked"]) & (set(queries) | set(labels))


def test_aggregate_equals_evaluate_submission(split, tmp_path):
    queries, labels, total_rel = eval_cv.load_data(split, final=False)
    qids = split["dev_folds"][0]
    bm25 = BM25Ranker(load_json(ROOT / "data/products.json"))
    rows, per_q = [], []
    for qid in qids:  # the script's own path: raw scores -> bm25_top -> evaluate -> summary
        top = eval_cv.bm25_top(bm25.bm25.get_scores(preprocess_text(queries[qid])))
        ranked = [bm25.product_ids[i] for i in top]
        rows += [{"query_id": qid, "rank": r, "product_id": p} for r, p in enumerate(ranked, 1)]
        per_q.append(eval_cv.evaluate(ranked, labels[qid], total_rel[qid]))
    sub = tmp_path / "sub.json"
    sub.write_text(json.dumps(rows), encoding="utf-8")
    lab = tmp_path / "labels.json"
    lab.write_text(json.dumps([{"query_id": q, "product_id": p, "relevance": r}
                               for q in qids for p, r in labels[q].items()]), encoding="utf-8")
    ref = evaluate_submission(sub, lab)
    assert ref["queries_scored"] == len(qids)
    agg = eval_cv.summary(per_q)
    for m in ("nDCG@10", "AP@20", "P@10", "R@30", "composite"):
        assert agg[m] == ref[m], m


def test_bootstrap_self_is_exactly_zero():
    a = np.random.default_rng(0).random(230)
    b = eval_cv.paired_bootstrap(a, a)
    assert b["mean_diff"] == 0.0 and b["ci95"] == [0.0, 0.0]
