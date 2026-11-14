export type Result = {
  rank: number
  product_id: string
  title: string
  brand: string | null
  score: number
  bm25_score: number
  semantic_score: number | null
  rerank_score: number | null
  label: number | null
}

export type SearchResponse = {
  query: string
  split: "dev" | "held_out" | null
  mode: string
  latency_ms: number
  results: Result[]
}

export async function search(query: string, signal?: AbortSignal): Promise<SearchResponse> {
  const res = await fetch(`/search?${new URLSearchParams({ q: query })}`, { signal })
  if (!res.ok) throw new Error(res.status === 422 ? "Enter 1 to 200 characters." : `Search failed (${res.status}).`)
  return res.json()
}
