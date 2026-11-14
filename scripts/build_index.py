"""Precompute product embeddings for the API.  Usage: python scripts/build_index.py [--out artifacts/index.npz]

Uses the same product text and model revision as the evaluated system (create_product_text, MiniLM).
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from baseline_ranker import create_product_text  # noqa: E402
from tamu25.api.search import MODEL_NAME, MODEL_REVISION  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--products", default="data/products.json")
    ap.add_argument("--out", default="artifacts/index.npz")
    a = ap.parse_args()
    from sentence_transformers import SentenceTransformer

    products = json.loads(Path(a.products).read_text(encoding="utf-8"))
    model = SentenceTransformer(MODEL_NAME, revision=MODEL_REVISION)
    emb = model.encode([create_product_text(p) for p in products], batch_size=32, convert_to_numpy=True)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    np.savez(a.out, embeddings=emb.astype(np.float32), product_ids=np.array([p["product_id"] for p in products]),
             model=MODEL_NAME, revision=MODEL_REVISION)
    print(f"wrote {a.out}: {emb.shape}")


if __name__ == "__main__":
    main()
