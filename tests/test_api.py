import json

import pytest

fastapi_testclient = pytest.importorskip("fastapi.testclient")

from tamu25.api.app import create_app  # noqa: E402
from tamu25.api.search import Searcher  # noqa: E402


@pytest.fixture()
def client(repo_root):
    products = json.loads((repo_root / "tests" / "data" / "products.json").read_text(encoding="utf-8"))
    # BM25-only searcher on the fixture catalog: no model needed.
    with fastapi_testclient.TestClient(create_app(Searcher(products))) as c:
        yield c, products


def test_health(client):
    c, _ = client
    assert c.get("/health").json() == {"status": "ok", "mode": "bm25"}


def test_frontend_is_served_same_origin_and_api_routes_win(repo_root, tmp_path):
    (tmp_path / "index.html").write_text("<title>Search products</title>", encoding="utf-8")
    products = json.loads((repo_root / "tests" / "data" / "products.json").read_text(encoding="utf-8"))
    with fastapi_testclient.TestClient(create_app(Searcher(products), frontend_dir=tmp_path)) as c:
        assert "Search products" in c.get("/").text
        assert c.get("/health").json() == {"status": "ok", "mode": "bm25"}
        assert c.get("/search", params={"q": products[0]["title"].split()[0]}).json()["mode"] == "bm25"
    with fastapi_testclient.TestClient(create_app(Searcher(products), frontend_dir=tmp_path / "missing")) as c:
        assert c.get("/").status_code == 404 and c.get("/health").status_code == 200


def test_search_shape_and_limits(client):
    c, products = client
    word = products[0]["title"].split()[0]
    r = c.get("/search", params={"q": word, "k": 5})
    assert r.status_code == 200
    body = r.json()
    assert body["mode"] == "bm25" and body["split"] is None and len(body["results"]) == 5
    first = body["results"][0]
    assert first["rank"] == 1 and first["semantic_score"] is None and first["label"] is None
    scores = [x["score"] for x in body["results"]]
    assert scores == sorted(scores, reverse=True)
    assert c.get("/search", params={"q": word, "k": 31}).status_code == 422
    assert c.get("/search", params={"q": ""}).status_code == 422
    assert c.get("/search", params={"q": "x" * 201}).status_code == 422


def test_locked_labels_never_served_on_real_data(repo_root):
    """Reviewer item 4: the locked-label filter, on the real data/ files. Asserts on counts only, so a failure
    cannot print a locked query text."""
    data = repo_root / "data"
    read = lambda n: json.loads((data / n).read_text(encoding="utf-8"))  # noqa: E731
    locked = set(read("split_v1.json")["locked"])
    s = Searcher(read("products.json"), data_dir=data)  # BM25-only: no model needed
    assert len(locked) == 58 and not locked & set(s.labels) and not locked & set(s.by_text.values())
    n = {"locked_ok": 0, "dev_ok": 0, "dev_with_positive": 0}
    for q in read("queries_synth_train.json"):
        out = s.search(q["query"], k=30)
        labels = [r["label"] for r in out["results"]]
        if q["query_id"] in locked:
            n["locked_ok"] += out["split"] == "held_out" and all(x is None for x in labels)
        else:
            n["dev_ok"] += out["split"] == "dev" and all(isinstance(x, int) for x in labels)
            n["dev_with_positive"] += any(labels)
    assert n["locked_ok"] == 58 and n["dev_ok"] == 230 and n["dev_with_positive"] > 200
