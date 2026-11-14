"""FastAPI app: GET /search, GET /healthz.

Run:  uvicorn tamu25.api.app:app   (from the repo root; env HEB_DATA_DIR, HEB_INDEX, HEB_FRONTEND_DIR)
Startup loads products and the precomputed index (scripts/build_index.py) once, plus the query encoder.
"""
import json
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

import numpy as np
from fastapi import FastAPI, Query
from fastapi.staticfiles import StaticFiles

from tamu25.api.search import MODEL_NAME, MODEL_REVISION, Searcher

MAX_QUERY_CHARS = 200
MAX_K = 30


def build_searcher(data_dir, index_path):
    """Hybrid searcher from the saved index; the encoder is loaded from the local model cache."""
    from sentence_transformers import SentenceTransformer

    products = json.loads((Path(data_dir) / "products.json").read_text(encoding="utf-8"))
    idx = np.load(index_path)
    if list(idx["product_ids"]) != [p["product_id"] for p in products]:
        raise RuntimeError("index does not match products.json; rebuild with scripts/build_index.py")
    encoder = SentenceTransformer(MODEL_NAME, revision=MODEL_REVISION)
    return Searcher(products, idx["embeddings"], encoder, data_dir=data_dir)


def create_app(searcher=None, frontend_dir=None):
    @asynccontextmanager
    async def lifespan(app):
        app.state.searcher = searcher or build_searcher(
            os.environ.get("HEB_DATA_DIR", "data"), os.environ.get("HEB_INDEX", "artifacts/index.npz")
        )
        yield

    app = FastAPI(title="HEB product search", lifespan=lifespan)

    @app.get("/healthz")
    def healthz():
        return {"status": "ok", "mode": app.state.searcher.mode}

    @app.get("/search")
    def search(
        q: Annotated[str, Query(min_length=1, max_length=MAX_QUERY_CHARS)],
        k: Annotated[int, Query(ge=1, le=MAX_K)] = MAX_K,
    ):
        t0 = time.perf_counter()
        out = app.state.searcher.search(q, k)
        out["latency_ms"] = round((time.perf_counter() - t0) * 1000, 1)
        return out

    # Same-origin frontend (frontend/dist from `npm run build`). Mounted last so the API routes above win;
    # skipped when the build is absent, so the API alone still starts.
    dist = Path(frontend_dir or os.environ.get("HEB_FRONTEND_DIR", "frontend/dist"))
    if (dist / "index.html").is_file():
        app.mount("/", StaticFiles(directory=dist, html=True), name="frontend")

    return app


app = create_app()
