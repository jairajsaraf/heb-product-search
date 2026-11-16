import { vi } from "vitest"
import type { SearchResponse } from "./api"

export function response(over: Partial<SearchResponse> = {}): SearchResponse {
  const result = (rank: number, title: string, label: number | null) => ({
    rank,
    product_id: `p${rank}`,
    title,
    brand: "H-E-B",
    score: 0.88 - rank / 100,
    bm25_score: 0.81,
    semantic_score: 0.74,
    rerank_score: null,
    label,
  })
  return {
    query: "gluten free pasta",
    split: "dev",
    mode: "hybrid",
    latency_ms: 141.7,
    results: [result(1, "Gluten Free Penne", 3), result(2, "Plain Spaghetti", 0)],
    ...over,
  }
}

/** The keyword-only answer the server gives for `mode=bm25`: same products, no meaning score. */
export function keywordOnly(body: SearchResponse): SearchResponse {
  return {
    ...body,
    mode: "bm25",
    results: body.results.map((r) => ({ ...r, score: r.bm25_score, semantic_score: null })),
  }
}

export function stubFetch(body: unknown, status = 200) {
  const fn = vi.fn(async (url: string) => {
    const keyword = status === 200 && String(url).includes("mode=bm25")
    return new Response(JSON.stringify(keyword ? keywordOnly(body as SearchResponse) : body), { status })
  })
  vi.stubGlobal("fetch", fn)
  return fn
}
