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

/** mode "bm25" asks the server for the keyword-only ranking; the default is the served hybrid. */
export async function search(query: string, signal?: AbortSignal, mode?: "bm25"): Promise<SearchResponse> {
  const url = `/search?${new URLSearchParams(mode ? { q: query, mode } : { q: query })}`
  const res = await fetch(url, { signal }).catch((err: unknown) => {
    if (err instanceof DOMException && err.name === "AbortError") throw err
    // Browsers word a dropped connection differently ("Failed to fetch", "Load failed"); say what to do instead.
    throw new Error("The search server did not answer. Check your connection and try again.")
  })
  if (!res.ok) throw new Error(res.status === 422 ? "Enter 1 to 200 characters." : `Search failed (${res.status}).`)
  return res.json()
}
