import { AnimatePresence, motion } from "motion/react"
import { useContext, type CSSProperties } from "react"
import { decodeEntities, fixed, MotionContext } from "../utils"

export type Row = {
  product_id: string
  title: string
  brand: string | null
  score: number
  bm25_score: number
  semantic_score: number | null
  rerank_score?: number | null
  /** undefined: this query has no grades. null: this product was never graded. */
  grade?: number | null
  /** Live responses send 0 for both "graded not relevant" and "never graded". */
  zeroIsAmbiguous?: boolean
}

function gradeText(row: Row) {
  if (row.grade === undefined) return null
  if (row.grade === null) return "Not graded"
  if (row.grade === 0) return row.zeroIsAmbiguous ? "Not relevant or not graded" : "Graded not relevant"
  return `Grade ${row.grade}`
}

function Breakdown({ row, weight }: { row: Row; weight: number }) {
  if (row.semantic_score === null) return <p className="scores">keyword {fixed(row.bm25_score)}</p>
  return (
    <p className="scores">
      {fixed(weight)} ×{" "}
      <span data-part="keyword">
        <span className="sr-only">keyword </span>
        {fixed(row.bm25_score)}
      </span>{" "}
      + {fixed(1 - weight)} ×{" "}
      <span data-part="meaning">
        <span className="sr-only">meaning </span>
        {fixed(row.semantic_score)}
      </span>{" "}
      = <strong>{fixed(row.score)}</strong>
      {row.rerank_score != null && `, rerank ${fixed(row.rerank_score)}`}
    </p>
  )
}

type ShelfProps = {
  kind: "keyword" | "hybrid"
  heading: string
  caption: string
  rows: Row[] | null
  weight: number
  showBreakdown: boolean
  /** Where each product sits in the keyword-only ranking, to show how far the blend moved it. */
  keywordRanks?: Map<string, number>
  keywordDepth?: number
}

const spring = { type: "spring", stiffness: 300, damping: 32, mass: 0.8 } as const

export function Shelf({ kind, heading, caption, rows, weight, showBreakdown, keywordRanks, keywordDepth }: ShelfProps) {
  const moving = useContext(MotionContext)
  const Item = moving ? motion.li : "li"
  const motionProps = moving
    ? { layout: "position" as const, initial: { opacity: 0, x: 28 }, animate: { opacity: 1, x: 0 }, exit: { opacity: 0, x: -28 }, transition: spring }
    : {}

  const items = rows?.map((row, index) => {
    const title = decodeEntities(row.title)
    const chip = gradeText(row)
    const from = keywordRanks?.get(row.product_id)
    const moved = from === undefined ? null : from === index + 1 ? "Same rank by keywords" : `Keyword rank ${from}`
    return (
      <Item key={row.product_id} className="row" {...motionProps}>
        <span className="rank">{index + 1}</span>
        <div className="row-body">
          <p className="row-title">
            {title}
            {row.brand && !title.startsWith(row.brand) && <span className="row-brand"> {row.brand}</span>}
          </p>
          {showBreakdown && (
            <>
              <div className="bars" aria-hidden="true">
                <span className="bar" data-part="keyword" style={{ "--v": row.bm25_score } as CSSProperties} />
                {row.semantic_score !== null && (
                  <span className="bar" data-part="meaning" style={{ "--v": row.semantic_score } as CSSProperties} />
                )}
              </div>
              <Breakdown row={row} weight={weight} />
            </>
          )}
          {moved && <p className="moved">{moved}</p>}
        </div>
        {chip && (
          <span className="grade" data-grade={row.grade === null ? "none" : row.grade}>
            {chip}
          </span>
        )}
      </Item>
    )
  })

  return (
    <section className="shelf" data-kind={kind} aria-label={heading}>
      <h3>{heading}</h3>
      <p className="shelf-caption">
        {caption}
        {rows && keywordRanks && keywordDepth
          ? ` ${rows.filter((row) => !keywordRanks.has(row.product_id)).length} of these ${rows.length} are not in the keyword top ${keywordDepth}.`
          : ""}
      </p>
      {rows === null ? (
        <p className="shelf-empty">This server did not return a keyword-only ranking for this search.</p>
      ) : kind === "keyword" && rows.length > 0 && rows.every((row) => row.bm25_score === 0) ? (
        <p className="shelf-empty">No product shares a word with this search, so keyword search has nothing to rank.</p>
      ) : (
        <ol className="rows">
          {moving ? (
            <AnimatePresence initial={false} mode="popLayout">
              {items}
            </AnimatePresence>
          ) : (
            items
          )}
        </ol>
      )}
    </section>
  )
}
