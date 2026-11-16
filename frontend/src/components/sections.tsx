import { Button } from "@ui-sdk/react/button"
import { motion } from "motion/react"
import { useContext, type CSSProperties } from "react"
import { decodeEntities, fact, fixed, MotionContext, percent, REPO, signed, sourceUrl } from "../utils"
import { GlowingEffect } from "./glowing-effect"
import { RollingNumber } from "./rolling-number"
import type { Row } from "./shelves"

function Source({ path }: { path: string }) {
  return (
    <a className="source" href={sourceUrl(path)}>
      Source: {path}
    </a>
  )
}

// The glow follows the pointer round the card's border; the card must be position: relative.
function CardGlow() {
  const moving = useContext(MotionContext)
  return moving ? <GlowingEffect disabled={false} spread={40} proximity={64} inactiveZone={0.01} borderWidth={2} /> : null
}

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

export function HowItScores({ row, weight }: { row: Row; weight: number }) {
  const meaning = row.semantic_score ?? 0
  return (
    <section className="band" aria-labelledby="how-title">
      <h2 id="how-title">How one score is made</h2>
      <p className="band-lede">
        Every product gets two scores for a query, each between 0 and 1. The keyword score is BM25 word overlap. The
        meaning score is how close the product's embedding sits to the query's. The final score is{" "}
        {fixed(weight)} × keyword + {fixed(1 - weight)} × meaning.
      </p>
      <div className="formula card">
        <CardGlow />
        <p className="formula-title">{decodeEntities(row.title)}</p>
        <div className="formula-track" aria-hidden="true">
          <span data-part="keyword" style={{ "--v": weight * row.bm25_score } as CSSProperties} />
          <span data-part="meaning" style={{ "--v": (1 - weight) * meaning } as CSSProperties} />
        </div>
        <p className="formula-sum">
          <span data-part="keyword">
            {fixed(weight)} × {fixed(row.bm25_score)}
          </span>{" "}
          +{" "}
          <span data-part="meaning">
            {fixed(1 - weight)} × {fixed(meaning)}
          </span>{" "}
          = <strong>{fixed(row.score)}</strong>
        </p>
      </div>
      <Pipeline />
      <p className="band-note">
        No language model reads or rewrites anything, and nothing was trained: both parts are used as published. The
        weight was chosen by cross-validation on {fact("split.dev").value} development queries.{" "}
        <Source path="reports/cv_results.md" />
      </p>
    </section>
  )
}

const D0 = -0.04
const D1 = 0.12
const at = (value: number) => `${((value - D0) / (D1 - D0)) * 100}%`

type IntervalProps = { label: string; diff: number; low: number; high: number; tone: "clear" | "unclear"; note: string }

function Interval({ label, diff, low, high, tone, note }: IntervalProps) {
  const moving = useContext(MotionContext)
  return (
    <div className="interval" data-tone={tone}>
      <p className="interval-label">{label}</p>
      <div className="interval-track" aria-hidden="true">
        <span className="interval-zero" style={{ left: at(0) }} />
        <motion.span
          className="interval-bar"
          style={{ left: at(low), width: `${((high - low) / (D1 - D0)) * 100}%` }}
          initial={moving ? { scaleX: 0 } : false}
          whileInView={{ scaleX: 1 }}
          viewport={{ once: true }}
          transition={{ duration: 0.9, ease: "easeOut" }}
        />
        <span className="interval-dot" style={{ left: at(diff) }} />
      </div>
      <p className="interval-text">
        <strong>{signed(diff)}</strong>, 95% interval {signed(low)} to {signed(high)}. {note}
      </p>
    </div>
  )
}

export function Evidence() {
  const official = fact("holdout.official.diff")
  const four = (n: number) => n.toFixed(4)
  return (
    <section className="band" aria-labelledby="evidence-title">
      <h2 id="evidence-title">What was measured</h2>
      <p className="band-lede">
        {fact("holdout.n_queries").value} queries were set aside before any tuning and scored once, with the settings
        fixed in advance. The score is the datathon's official composite, from 0 to 1: 0.30 × nDCG@10 + 0.30 × AP@20 +
        0.25 × Recall@30 + 0.15 × Precision@10. Each line below is the hybrid's score minus keyword search alone.{" "}
        <Source path="tamu25/evaluate.py" />
      </p>

      <div className="intervals card">
        <CardGlow />
        <Interval
          label={`Official score, ${fact("holdout.n_queries").value} unseen queries`}
          diff={official.value}
          low={fact("holdout.official.ci_low").value}
          high={fact("holdout.official.ci_high").value}
          tone="clear"
          note="The whole interval is above zero."
        />
        <Interval
          label="Same queries, counting only products that were graded"
          diff={fact("holdout.judged.diff").value}
          low={fact("holdout.judged.ci_low").value}
          high={fact("holdout.judged.ci_high").value}
          tone="unclear"
          note="The interval includes zero, so this gain cannot be told apart from no gain."
        />
        <Interval
          label={`Official score, ${fact("cv.n_queries").value} development queries, cross-validated`}
          diff={fact("cv.official.diff").value}
          low={fact("cv.official.ci_low").value}
          high={fact("cv.official.ci_high").value}
          tone="clear"
          note="The earlier estimate agrees with the unseen set."
        />
        <div className="interval-axis" aria-hidden="true">
          {[-0.04, 0, 0.04, 0.08, 0.12].map((tick) => (
            <span key={tick} style={{ left: at(tick) }}>
              {tick === 0 ? "0" : signed(tick, 2)}
            </span>
          ))}
        </div>
        <Source path={official.source} />
      </div>

      <div className="cards">
        <article className="card">
          <CardGlow />
          <h3>Official score</h3>
          <p className="figure">
            <RollingNumber
              from={fact("holdout.official.bm25").value}
              value={fact("holdout.official.hybrid").value}
              format={four}
            />
          </p>
          <p>
            Keyword search alone scored {four(fact("holdout.official.bm25").value)}. This score counts every ungraded
            product as wrong.
          </p>
        </article>
        <article className="card">
          <CardGlow />
          <h3>Graded products only</h3>
          <p className="figure">
            <RollingNumber
              from={fact("holdout.judged.bm25").value}
              value={fact("holdout.judged.hybrid").value}
              format={four}
            />
          </p>
          <p>
            Keyword search alone scored {four(fact("holdout.judged.bm25").value)}. With ungraded products left out, the
            two are close.
          </p>
        </article>
        <article className="card">
          <CardGlow />
          <h3>Ungraded products in the top 10</h3>
          <p className="figure figure-pair">
            <span>
              {percent(fact("holdout.unjudged_top10.bm25").value)} <small>keyword</small>
            </span>
            <span>
              {percent(fact("holdout.unjudged_top10.hybrid").value)} <small>hybrid</small>
            </span>
          </p>
          <p>
            Keyword search returns far more products nobody graded. Part of the official gain comes from the hybrid
            returning products that have grades. Whether the ungraded ones were bad is unknown.
          </p>
        </article>
        <article className="card">
          <CardGlow />
          <h3>Human comparison</h3>
          <p className="figure">Not run</p>
          <p>
            A blind side-by-side kit is written and waiting for readers. Until it is run, no person has judged these
            rankings. <Source path="reports/human_kit.md" />
          </p>
        </article>
      </div>
    </section>
  )
}

type Example = { id: string; query: string; role: string; hybrid: Row[]; keyword: Row[] }

const FAILURE_COPY: Record<string, string> = {
  fail: "Both rankings return seasoned chicken, not seasoning. The words match and so does the meaning, but the shopper wanted a different aisle.",
  keyword: "Exact attributes such as a size favour plain keyword matching. The blend lets a near-identical product with the wrong size climb.",
}

export function Failures({ examples, onShow }: { examples: Example[]; onShow: (id: string) => void }) {
  const zeros = (rows: Row[]) => rows.filter((row) => row.grade === 0).length
  return (
    <section className="band" aria-labelledby="fail-title">
      <h2 id="fail-title">Where it fails</h2>
      <div className="cards">
        {examples
          .filter((example) => example.role in FAILURE_COPY)
          .map((example) => {
            const miss = example.hybrid.findIndex((row) => row.grade === 0)
            return (
              <article className="card" key={example.id}>
                <CardGlow />
                <h3>“{example.query}”</h3>
                <p>{FAILURE_COPY[example.role]}</p>
                <p>
                  Graded not relevant in the top 10: {zeros(example.hybrid)} for the hybrid, {zeros(example.keyword)}{" "}
                  for keyword search.
                  {miss >= 0 && ` Hybrid rank ${miss + 1}: ${decodeEntities(example.hybrid[miss]!.title)}.`}
                </p>
                <Button onClick={() => onShow(example.id)}>Show “{example.query}”</Button>
              </article>
            )
          })}
      </div>
      <p className="band-note">
        The error analysis sorts all {fact("split.dev").value} development queries by failure type.{" "}
        <Source path="reports/error_analysis.md" />
      </p>
    </section>
  )
}

export function Tried() {
  const base = fact("tried.baseline.official").value
  return (
    <section className="band" aria-labelledby="tried-title">
      <h2 id="tried-title">Tried and not kept</h2>
      <p className="band-lede">
        Two common upgrades were tested on the {fact("split.dev").value} development queries against the blend above,
        which scores {base.toFixed(4)} there. A change was kept only if its whole interval was above zero.
      </p>
      <div className="cards">
        <article className="card">
          <CardGlow />
          <h3>Reciprocal rank fusion</h3>
          <p className="figure">{signed(fact("tried.rrf.diff").value)}</p>
          <p>
            Scored {fact("tried.rrf.official").value.toFixed(4)}. Interval {signed(fact("tried.rrf.ci_low").value)} to{" "}
            {signed(fact("tried.rrf.ci_high").value)}. It did not beat the simple weighted sum.
          </p>
        </article>
        <article className="card">
          <CardGlow />
          <h3>Cross-encoder reranking</h3>
          <p className="figure">{signed(fact("tried.rerank.diff").value)}</p>
          <p>
            Scored {fact("tried.rerank.official").value.toFixed(4)}. Interval{" "}
            {signed(fact("tried.rerank.ci_low").value)} to {signed(fact("tried.rerank.ci_high").value)}. On graded
            products only it moved {signed(fact("tried.rerank.judged_diff").value)}, interval{" "}
            {signed(fact("tried.rerank.judged_ci_low").value)} to {signed(fact("tried.rerank.judged_ci_high").value)}.
            It pulled more ungraded products into the top 10 ({percent(fact("tried.rerank.unjudged_top10").value)}{" "}
            against {percent(fact("tried.baseline.unjudged_top10").value)}), so these grades cannot say whether it
            ranks better. Not kept.
          </p>
        </article>
      </div>
      <Source path={fact("tried.rrf.diff").source} />
    </section>
  )
}

export function Limits() {
  const graded = fact("split.dev").value + fact("split.locked").value
  return (
    <section className="band" aria-labelledby="limits-title">
      <h2 id="limits-title">Limits</h2>
      <ul className="limits">
        <li>
          This is a project for the TAMU-25 H-E-B Datathon over {fact("catalog.products").value.toLocaleString("en-US")}{" "}
          products. It is not H-E-B's production search.
        </li>
        <li>
          The queries and grades are synthetic, not shopper logs. Grades exist for {graded} queries (
          {fact("split.dev").value} for development and {fact("split.locked").value} locked), and many returned products
          were never graded.
        </li>
        <li>
          The {fact("split.locked").value} locked queries were scored once. Their grades are never sent to this page, so
          it cannot be used to tune against them.
        </li>
        <li>
          On a laptop, without the web layer, a search took {fact("latency.hybrid.p50").value} ms at the median and{" "}
          {fact("latency.hybrid.p95").value} ms at the 95th percentile over {fact("latency.n_queries").value} queries.
          This server is smaller, so every search above shows the time the server reported.
        </li>
        <li>No personalisation, query expansion or fine-tuning has been built or measured.</li>
      </ul>
      <p className="band-note">
        Code, data and every report: <a href={REPO}>{REPO.replace("https://", "")}</a>
      </p>
    </section>
  )
}
