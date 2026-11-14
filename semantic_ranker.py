"""
Hybrid Semantic + BM25 Ranker for TAMU-25 Challenge
Combines embedding-based semantic search with keyword matching
"""
import json
import numpy as np
from sentence_transformers import CrossEncoder, SentenceTransformer
from baseline_ranker import BM25Ranker, load_json, save_json, preprocess_text, create_product_text

# Phase 3 reranker (used only when HybridRanker is built with reranker_model and rank(rerank=True)).
RERANKER_MODEL = 'cross-encoder/ms-marco-MiniLM-L6-v2'
RERANKER_REVISION = '233902d25c440f23af6f7d6e94d2946bac0bee0a'


def tie_ranks(scores):
    """1-based descending ranks; equal scores share the best rank (1 + number of strictly greater scores)."""
    s = np.asarray(scores, dtype=float)
    return 1 + np.searchsorted(np.sort(-s), -s, side='left')


def rrf_fuse(bm25_scores, cos_similarities, k=60):
    """Reciprocal rank fusion of the BM25 and cosine rankings, with tie-aware ranks."""
    return 1.0 / (k + tie_ranks(bm25_scores)) + 1.0 / (k + tie_ranks(cos_similarities))


def rerank_text(product):
    """Product text given to the cross-encoder."""
    return (f"{product['title']}. Brand: {product.get('brand') or ''}. "
            f"Category: {product['category_path']}. {product.get('description') or ''}")


def rerank_scores(reranker, query_text, texts):
    """One predict call per query, so scores do not depend on how other queries are batched."""
    return reranker.predict([(query_text, t) for t in texts], batch_size=len(texts), show_progress_bar=False)


def rerank_order(order, ce_scores):
    """Reorder the first len(ce_scores) entries of `order` by score (descending, stable); keep the rest."""
    order = np.asarray(order)
    d = len(ce_scores)
    return np.concatenate([order[:d][np.argsort(-np.asarray(ce_scores), kind='stable')], order[d:]])


class HybridRanker:
    """
    Hybrid ranker combining semantic embeddings and BM25
    """

    def __init__(self, products, model_name='all-MiniLM-L6-v2', reranker_model=None, reranker_revision=None):
        """
        Initialize hybrid ranker

        Args:
            products: List of product dictionaries
            model_name: Sentence transformer model to use
            reranker_model: Cross-encoder to load for rank(rerank=True); None (default) loads nothing
            reranker_revision: Model revision to pin for the cross-encoder
        """
        self.products = products
        self.product_ids = [p['product_id'] for p in products]
        self.reranker = CrossEncoder(reranker_model, revision=reranker_revision) if reranker_model else None

        # Initialize BM25 ranker
        print("Initializing BM25 ranker...")
        self.bm25_ranker = BM25Ranker(products)

        # Initialize semantic model
        print(f"Loading semantic model: {model_name}...")
        self.model = SentenceTransformer(model_name)

        # Create product embeddings
        print("Generating product embeddings (this may take a few minutes)...")
        product_texts = [create_product_text(p) for p in products]
        self.product_embeddings = self.model.encode(
            product_texts,
            show_progress_bar=True,
            batch_size=32,
            convert_to_numpy=True
        )
        print(f"Generated embeddings for {len(products)} products")

    def rank(self, query_text, top_k=50, bm25_weight=0.3, semantic_weight=0.7,
             fusion='linear', rrf_k=60, rerank=False, rerank_depth=50):
        """
        Rank products using hybrid approach

        Args:
            query_text: The search query
            top_k: Number of top results to return
            bm25_weight: Weight for BM25 scores (0-1)
            semantic_weight: Weight for semantic scores (0-1)
            fusion: 'linear' (default, the weighted sum above) or 'rrf' (reciprocal rank fusion, weights unused)
            rrf_k: RRF constant, used only with fusion='rrf'
            rerank: Reorder the top rerank_depth with the cross-encoder (default off; needs reranker_model)
            rerank_depth: Number of fused results the cross-encoder reorders

        Returns:
            List of (product_id, score) tuples; with rerank, the reordered head carries cross-encoder scores
        """
        if rerank and self.reranker is None:
            raise ValueError("rerank=True needs HybridRanker(..., reranker_model=...)")
        if fusion == 'linear':
            ranked = self._linear(query_text, bm25_weight, semantic_weight)
        elif fusion == 'rrf':
            ranked = self._rrf(query_text, rrf_k)
        else:
            raise ValueError(f"unknown fusion: {fusion}")
        if rerank:
            head = ranked[:rerank_depth]
            idx = {pid: i for i, pid in enumerate(self.product_ids)}
            scores = rerank_scores(self.reranker, query_text, [rerank_text(self.products[idx[p]]) for p, _ in head])
            ranked = [(head[i][0], float(scores[i])) for i in rerank_order(range(len(head)), scores)] + ranked[rerank_depth:]
        return ranked[:top_k]

    def _rrf(self, query_text, rrf_k):
        bm25 = self.bm25_ranker.bm25.get_scores(preprocess_text(query_text))
        query_embedding = self.model.encode([query_text], convert_to_numpy=True)[0]
        similarities = np.dot(self.product_embeddings, query_embedding) / (
            np.linalg.norm(self.product_embeddings, axis=1) * np.linalg.norm(query_embedding)
        )
        fused = rrf_fuse(bm25, similarities, rrf_k)
        return [(self.product_ids[i], float(fused[i])) for i in np.argsort(-fused, kind='stable')]

    def _linear(self, query_text, bm25_weight, semantic_weight):
        """Original weighted-sum ranking, unchanged; returns the full sorted list."""
        # Get BM25 scores
        bm25_results = self.bm25_ranker.rank(query_text, top_k=len(self.products))
        bm25_scores_dict = {pid: score for pid, score in bm25_results}

        # Normalize BM25 scores
        max_bm25 = max(bm25_scores_dict.values()) if bm25_scores_dict else 1.0
        if max_bm25 > 0:
            bm25_scores_dict = {pid: score / max_bm25 for pid, score in bm25_scores_dict.items()}

        # Get semantic scores
        query_embedding = self.model.encode([query_text], convert_to_numpy=True)[0]

        # Compute cosine similarity
        similarities = np.dot(self.product_embeddings, query_embedding) / (
            np.linalg.norm(self.product_embeddings, axis=1) * np.linalg.norm(query_embedding)
        )

        # Combine scores
        combined_scores = []
        for idx, product_id in enumerate(self.product_ids):
            bm25_score = bm25_scores_dict.get(product_id, 0.0)
            semantic_score = similarities[idx]

            # Normalize semantic score to [0, 1]
            semantic_score_norm = (semantic_score + 1) / 2  # Convert from [-1, 1] to [0, 1]

            # Combined score
            combined_score = (bm25_weight * bm25_score) + (semantic_weight * semantic_score_norm)
            combined_scores.append((product_id, combined_score))

        # Sort by combined score
        combined_scores.sort(key=lambda x: x[1], reverse=True)

        return combined_scores

def generate_submission(ranker, queries, output_file, top_k=50, bm25_weight=0.3, semantic_weight=0.7):
    """
    Generate submission file using hybrid ranker

    Args:
        ranker: HybridRanker instance
        queries: List of query dicts
        output_file: Path to save submission
        top_k: Number of products to rank per query
        bm25_weight: Weight for BM25 component
        semantic_weight: Weight for semantic component
    """
    submission = []

    print(f"\nGenerating rankings for {len(queries)} queries...")
    print(f"Weights: BM25={bm25_weight}, Semantic={semantic_weight}")

    for i, query in enumerate(queries, 1):
        if i % 20 == 0:
            print(f"  Processed {i}/{len(queries)} queries...")

        query_id = query['query_id']
        query_text = query['query']

        # Rank products
        rankings = ranker.rank(query_text, top_k=top_k, bm25_weight=bm25_weight, semantic_weight=semantic_weight)

        # Create submission entries
        for rank, (product_id, score) in enumerate(rankings, 1):
            submission.append({
                'query_id': query_id,
                'rank': rank,
                'product_id': product_id
            })

    print(f"Generated {len(submission)} ranked results")

    # Save submission
    save_json(submission, output_file)
    print(f"Submission saved to {output_file}")

    return submission

def main():
    """Main function"""
    print("=" * 80)
    print("HYBRID SEMANTIC + BM25 RANKER")
    print("=" * 80)

    # Load data
    print("\nLoading data...")
    products = load_json('data/products.json')
    queries_test = load_json('data/queries_synth_test.json')

    print(f"[OK] Loaded {len(products)} products")
    print(f"[OK] Loaded {len(queries_test)} test queries")

    # Initialize hybrid ranker
    ranker = HybridRanker(products, model_name='all-MiniLM-L6-v2')

    # Generate submission with optimized weights
    # Semantic weight higher because it captures meaning better
    submission = generate_submission(
        ranker,
        queries_test,
        'teams/team-gsr/submission.json',
        top_k=50,
        bm25_weight=0.3,      # 30% keyword matching
        semantic_weight=0.7    # 70% semantic similarity
    )

    print("\n" + "=" * 80)
    print("HYBRID RANKER COMPLETE")
    print("=" * 80)
    print("\nNext steps:")
    print("1. Validate: py -m tamu25.cli.main validate ...")
    print("2. Evaluate on training set to compare with baseline")
    print("3. Submit to leaderboard if performance is improved")

if __name__ == '__main__':
    main()
