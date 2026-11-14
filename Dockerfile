# API image (Phase 5a: backend only; the frontend stage comes in 5b).
FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1

COPY requirements-api.txt .
RUN pip install torch==2.15.0 --index-url https://download.pytorch.org/whl/cpu \
 && pip install -r requirements-api.txt

COPY baseline_ranker.py ./
COPY tamu25 ./tamu25
COPY scripts/build_index.py ./scripts/build_index.py
COPY data/products.json data/queries_synth_train.json data/labels_synth_train.json data/split_v1.json ./data/

# Bake the model and the product index into the image; the running container then needs no network.
RUN python scripts/build_index.py
ENV HF_HUB_OFFLINE=1 HEB_DATA_DIR=data HEB_INDEX=artifacts/index.npz

# Cloud Run supplies $PORT; 8080 locally.
CMD ["sh", "-c", "uvicorn tamu25.api.app:app --host 0.0.0.0 --port ${PORT:-8080}"]
