import { Button } from "@ui-sdk/react/button"
import { Field, FieldLabel } from "@ui-sdk/react/field"
import { Input } from "@ui-sdk/react/input"
import { Switch, SwitchThumb } from "@ui-sdk/react/switch"
import { BorderBeam } from "border-beam"
import { MotionConfig } from "motion/react"
import { useEffect, useRef, useState, type FormEvent } from "react"
import { search, type Result, type SearchResponse } from "./api"
import { GridBeam } from "./components/grid-beam"
import { MultiStepLoader } from "./components/multi-step-loader"
import { Evidence, Failures, HowItScores, Limits, Pipeline, STEPS, Tried } from "./components/sections"
import { Shelf, type Row } from "./components/shelves"
import { TracingBeam } from "./components/tracing-beam"
import { Typewriter } from "./components/typewriter"
import snapshot from "./examples.json"
import { fact, fixed, MotionContext, signed } from "./utils"

const WEIGHT = snapshot.bm25_weight
const EXAMPLES = snapshot.examples
const SHOWN = 10
const LOADING_STATES = STEPS.map((text) => ({ text }))

const ROLE_TAG: Record<string, string> = {
  lead: "meaning wins",
  meaning: "meaning wins",
  keyword: "keywords win",
  fail: "both fail",
}
const ROLE_NOTE: Record<string, string> = {
  lead: "meaning beats keywords here",
  meaning: "meaning beats keywords here",
  keyword: "keywords beat the blend here",
  fail: "both rankings fail here",
}

type Stage = {
  id: number
  query: string
  role: string | null
  hybrid: Row[]
  keyword: Row[] | null
  keywordRanks: Map<string, number>
  keywordDepth: number
  status: string
}

const ranksOf = (rows: { product_id: string }[]) => new Map(rows.map((row, index) => [row.product_id, index + 1]))

function exampleStage(index: number, id: number): Stage {
  const example = EXAMPLES[index]!
  return {
    id,
    query: example.query,
    role: example.role,
    hybrid: example.hybrid,
    keyword: example.keyword,
    keywordRanks: ranksOf(example.keyword),
    keywordDepth: example.keyword.length,
    status: "A worked example from the graded development set, computed when this page was built.",
  }
}

function liveStage(hybrid: SearchResponse, keyword: SearchResponse | null, id: number): Stage {
  // Grades are shown for development queries only, even if the server sent one for a locked query.
  const graded = hybrid.split === "dev"
  const toRow = (r: Result): Row => ({ ...r, grade: graded ? r.label : undefined, zeroIsAmbiguous: true })
  const split = graded
    ? " This query is in the graded development set."
    : hybrid.split === "held_out"
      ? " This query is in the locked test set, so its grades stay hidden."
      : ""
  const shown = Math.min(SHOWN, hybrid.results.length)
  return {
    id,
    query: hybrid.query,
    role: null,
    hybrid: hybrid.results.slice(0, SHOWN).map(toRow),
    keyword: keyword ? keyword.results.slice(0, SHOWN).map(toRow) : null,
    keywordRanks: ranksOf(keyword?.results ?? []),
    keywordDepth: keyword?.results.length ?? 0,
    status: `Top ${shown} results for “${hybrid.query}”, ranked in ${Math.round(hybrid.latency_ms)} ms on the server.${split}`,
  }
}

export function App() {
  const [q, setQ] = useState("")
  const [showBreakdown, setShowBreakdown] = useState(true)
  const [motionOn, setMotionOn] = useState(() => !window.matchMedia("(prefers-reduced-motion: reduce)").matches)
  const [stage, setStage] = useState<Stage | null>(() => exampleStage(0, 0))
  const [exampleIndex, setExampleIndex] = useState(0)
  const [autoplay, setAutoplay] = useState(true)
  const [blendedId, setBlendedId] = useState<number | null>(null)
  const [error, setError] = useState("")
  const [pending, setPending] = useState(false)
  const [slow, setSlow] = useState(false)
  const ids = useRef(0)
  const latest = useRef(0)
  const stageRef = useRef<HTMLElement>(null)

  function showExample(index: number) {
    latest.current++
    setPending(false)
    setError("")
    setExampleIndex(index)
    setStage(exampleStage(index, ++ids.current))
  }

  // Until the visitor touches anything, walk through the worked examples.
  useEffect(() => {
    if (!motionOn || !autoplay) return
    const timer = setTimeout(() => showExample((exampleIndex + 1) % EXAMPLES.length), 9000)
    return () => clearTimeout(timer)
  }, [motionOn, autoplay, exampleIndex])

  // The right-hand shelf starts in keyword order, then re-ranks once meaning is added.
  const stageId = stage?.id
  const isExample = stage?.role != null
  useEffect(() => {
    if (!motionOn || stageId === undefined) return
    const timer = setTimeout(() => setBlendedId(stageId), isExample ? 1900 : 600)
    return () => clearTimeout(timer)
  }, [motionOn, stageId, isExample])
  const blended = !motionOn || !stage?.keyword || blendedId === stage.id

  useEffect(() => {
    if (!pending) {
      setSlow(false)
      return
    }
    const timer = setTimeout(() => setSlow(true), 300)
    return () => clearTimeout(timer)
  }, [pending])

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    const text = q.trim()
    if (!text) return
    setAutoplay(false)
    const mine = ++latest.current
    setError("")
    setPending(true)
    try {
      const [hybrid, keyword] = await Promise.all([search(text), search(text, undefined, "bm25").catch(() => null)])
      if (mine !== latest.current) return
      // A server without the mode parameter answers with the hybrid ranking; never show that as keyword-only.
      setStage(liveStage(hybrid, keyword?.mode === "bm25" ? keyword : null, ++ids.current))
    } catch (err) {
      if (mine !== latest.current) return
      setStage(null)
      setError(err instanceof Error ? err.message : "Search failed.")
    } finally {
      if (mine === latest.current) setPending(false)
    }
  }

  function showById(id: string) {
    setAutoplay(false)
    showExample(EXAMPLES.findIndex((example) => example.id === id))
    stageRef.current?.scrollIntoView({ behavior: motionOn ? "smooth" : "auto", block: "start" })
  }

  const official = fact("holdout.official.diff").value
  const lower = (
    <>
      <HowItScores row={EXAMPLES[0]!.hybrid[0]!} weight={WEIGHT} />
      <Evidence />
      <Failures examples={EXAMPLES} onShow={showById} />
      <Tried />
      <Limits />
    </>
  )
  const nextExample = EXAMPLES[(exampleIndex + 1) % EXAMPLES.length]!

  return (
    <MotionContext.Provider value={motionOn}>
      <MotionConfig reducedMotion={motionOn ? "never" : "always"}>
        <main className="page" data-motion={motionOn ? "on" : "off"}>
          {/* overflow-clip, not hidden: a hidden box would become the scroll container and stop the hero sticking. */}
          <GridBeam className="overflow-clip" rows={5} cols={8} colorVariant="shelf" theme="auto" active={motionOn}>
            <div className="wrap top">
              <header className="hero">
                <h1>Product search that ranks by meaning as well as keywords</h1>
                <p className="lede">
                  A hybrid of BM25 keyword scoring and sentence-embedding similarity over{" "}
                  {fact("catalog.products").value.toLocaleString("en-US")} H-E-B grocery products. It is a datathon
                  project, not H-E-B's production search. It uses no language model, and nothing was trained.
                </p>
                <dl className="claims">
                  <div>
                    <dt>What was measured</dt>
                    <dd>
                      On {fact("holdout.n_queries").value} queries held back until the end, the official score rose
                      from {fact("holdout.official.bm25").value.toFixed(4)} to{" "}
                      {fact("holdout.official.hybrid").value.toFixed(4)} ({signed(official)}, 95% interval{" "}
                      {signed(fact("holdout.official.ci_low").value)} to{" "}
                      {signed(fact("holdout.official.ci_high").value)}). That score counts every ungraded product as
                      wrong. Counting only graded products, the gain is{" "}
                      {signed(fact("holdout.judged.diff").value)}, which cannot be told apart from zero.
                    </dd>
                  </div>
                  <div>
                    <dt>What was built</dt>
                    <dd>
                      The ranker, an evaluation harness with a locked test set that was scored once, the search API,
                      and this page.
                    </dd>
                  </div>
                </dl>

                <form onSubmit={onSubmit} className="search-form">
                  <BorderBeam className="beam-field" colorVariant="gold" theme="auto" active={motionOn}>
                    <Field name="q">
                      <FieldLabel>Find products</FieldLabel>
                      <Input
                        type="search"
                        value={q}
                        onValueChange={(value) => {
                          setQ(value)
                          setAutoplay(false)
                        }}
                        maxLength={200}
                        autoComplete="off"
                        placeholder={`Try “${nextExample.query}”`}
                      />
                    </Field>
                  </BorderBeam>
                  <Button type="submit">Search</Button>
                </form>

                <div className="chips" role="group" aria-label="Worked examples">
                  {EXAMPLES.map((example, index) => (
                    <Button
                      key={example.id}
                      aria-pressed={stage?.role != null && stage.query === example.query}
                      onClick={() => {
                        setAutoplay(false)
                        showExample(index)
                      }}
                    >
                      {example.query} <span className="chip-tag">{ROLE_TAG[example.role]}</span>
                    </Button>
                  ))}
                </div>

                <div className="toggles">
                  <Field>
                    <FieldLabel>Show score breakdown</FieldLabel>
                    <Switch checked={showBreakdown} onCheckedChange={setShowBreakdown}>
                      <SwitchThumb />
                    </Switch>
                  </Field>
                  <Field>
                    <FieldLabel>Motion</FieldLabel>
                    <Switch checked={motionOn} onCheckedChange={setMotionOn}>
                      <SwitchThumb />
                    </Switch>
                  </Field>
                  {motionOn && stage && (
                    <Button
                      onClick={() => {
                        setAutoplay(false)
                        setStage({ ...stage, id: ++ids.current })
                      }}
                    >
                      Replay the re-rank
                    </Button>
                  )}
                </div>
              </header>

              <section className="stage" ref={stageRef} aria-labelledby="stage-title">
                <h2 id="stage-title">
                  {stage ? (
                    <>
                      Results for{" "}
                      <q>
                        <span className="sr-only">{stage.query}</span>
                        <Typewriter key={stage.id} text={stage.query} instant={!motionOn || stage.role === null} />
                      </q>
                    </>
                  ) : (
                    "No results"
                  )}
                </h2>
                {stage?.role != null && <p className="stage-tag">Worked example: {ROLE_NOTE[stage.role]}.</p>}
                <output className="status">{error || (pending ? "Searching…" : (stage?.status ?? ""))}</output>
                {motionOn ? <MultiStepLoader loadingStates={LOADING_STATES} loading={slow} /> : slow && <Pipeline running />}
                {stage ? (
                  <div className="shelves" aria-busy={pending || undefined}>
                    <Shelf
                      kind="keyword"
                      heading="Keyword only"
                      caption="Word overlap (BM25). The baseline."
                      rows={stage.keyword}
                      weight={WEIGHT}
                      showBreakdown={showBreakdown}
                    />
                    <Shelf
                      kind="hybrid"
                      heading="Keyword + meaning"
                      caption={
                        blended
                          ? `${fixed(WEIGHT)} × keyword + ${fixed(1 - WEIGHT)} × meaning. What this site serves.`
                          : "Starting from the keyword order, then adding meaning."
                      }
                      rows={blended ? stage.hybrid : stage.keyword}
                      weight={WEIGHT}
                      showBreakdown={showBreakdown}
                      keywordRanks={blended && stage.keyword ? stage.keywordRanks : undefined}
                      keywordDepth={stage.keywordDepth}
                    />
                  </div>
                ) : (
                  <p className="stage-empty">
                    Nothing to show for that search. Pick one of the examples to see the ranker at work.
                  </p>
                )}
                <p className="legend">
                  Grades are the datathon's relevance labels: 3 is exactly what the shopper asked for, 2 a good
                  alternative, 1 related, 0 not relevant. They exist only for {fact("split.dev").value} development
                  queries, and for any one query most products were never graded. “Not graded” means nobody labelled
                  that product for this query, not that it is a bad result. The yellow bar is the keyword score
                  and the pink bar is the meaning score.
                </p>
              </section>
            </div>
          </GridBeam>

          <div className="wrap">
            {motionOn ? <TracingBeam className="max-w-none">{lower}</TracingBeam> : lower}
          </div>
        </main>
      </MotionConfig>
    </MotionContext.Provider>
  )
}
