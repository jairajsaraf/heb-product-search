import { Button } from "@ui-sdk/react/button"
import { Field, FieldLabel } from "@ui-sdk/react/field"
import { Input } from "@ui-sdk/react/input"
import { Switch, SwitchThumb } from "@ui-sdk/react/switch"
import { useRef, useState, type FormEvent } from "react"
import { search, type Result, type SearchResponse } from "./api"

const SPLIT_TEXT = { dev: "train query (dev)", held_out: "held out" } as const

const fmt = (n: number) => n.toFixed(2)

function scoreRow(r: Result) {
  const parts = [`bm25 ${fmt(r.bm25_score)}`]
  if (r.semantic_score !== null) parts.push(`semantic ${fmt(r.semantic_score)}`)
  if (r.rerank_score !== null) parts.push(`rerank ${fmt(r.rerank_score)}`)
  parts.push(`final ${fmt(r.score)}`)
  return parts.join(" · ")
}

export function App() {
  const [q, setQ] = useState("")
  const [debug, setDebug] = useState(true)
  const [data, setData] = useState<SearchResponse | null>(null)
  const [error, setError] = useState("")
  const latest = useRef(0)

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    const text = q.trim()
    if (!text) return
    const mine = ++latest.current
    setError("")
    try {
      const next = await search(text)
      if (mine === latest.current) setData(next)
    } catch (err) {
      if (mine !== latest.current) return
      setData(null)
      setError(err instanceof Error ? err.message : "Search failed.")
    }
  }

  // M8: labels for dev queries only, even if the API sent one for a held-out query.
  const showLabel = data?.split === "dev"
  const split = data?.split ? SPLIT_TEXT[data.split] : ""

  return (
    <main>
      <form onSubmit={onSubmit} className="search-form">
        <Field name="q">
          <FieldLabel>Find products</FieldLabel>
          <Input type="search" value={q} onValueChange={setQ} maxLength={200} autoComplete="off" />
        </Field>
        <Button type="submit">Search</Button>
        <Field>
          <FieldLabel>Debug</FieldLabel>
          <Switch checked={debug} onCheckedChange={setDebug}>
            <SwitchThumb />
          </Switch>
        </Field>
      </form>

      <output>
        {error ||
          (data &&
            [`${data.results.length} results for “${data.query}”`, `${Math.round(data.latency_ms)} ms`, split]
              .filter(Boolean)
              .join(" · "))}
      </output>

      <ol className="results">
        {data?.results.map((r) => (
          <li key={r.product_id}>
            <p className="result-line">
              <span className="rank">{r.rank}</span>
              <span className="title">
                {r.title}
                {r.brand ? ` · ${r.brand}` : ""}
              </span>
              {showLabel && r.label !== null && <span className="label">label {r.label}</span>}
            </p>
            {debug && <p className="scores">{scoreRow(r)}</p>}
          </li>
        ))}
      </ol>
    </main>
  )
}
