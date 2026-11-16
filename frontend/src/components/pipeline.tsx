import type { CSSProperties } from "react"

export const STEPS = [
  "Split the query into words",
  "Score word overlap with each product (BM25)",
  "Turn the query into an embedding (MiniLM)",
  "Compare it with every product embedding",
  "Blend the two scores and sort",
]

export function Pipeline({ running = false }: { running?: boolean }) {
  return (
    <ol className="pipeline" data-running={running || undefined}>
      {STEPS.map((step, index) => (
        <li key={step} style={{ "--i": index } as CSSProperties}>
          {step}
        </li>
      ))}
    </ol>
  )
}
