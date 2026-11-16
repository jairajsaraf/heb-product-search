import { useContext } from "react"
import examples from "../examples.json"
import { MotionContext } from "../utils"
import { Evidence, Failures, HowItScores, Limits, Tried } from "./sections"
import { TracingBeam } from "./tracing-beam"

// Everything below the first screen. App loads this chunk lazily so it stays out of the first paint.
export default function Lower({ onShow }: { onShow: (id: string) => void }) {
  const motionOn = useContext(MotionContext)
  const content = (
    <>
      <HowItScores row={examples.examples[0]!.hybrid[0]!} weight={examples.bm25_weight} />
      <Evidence />
      <Failures examples={examples.examples} onShow={onShow} />
      <Tried />
      <Limits />
    </>
  )
  return motionOn ? <TracingBeam className="max-w-none">{content}</TracingBeam> : content
}
