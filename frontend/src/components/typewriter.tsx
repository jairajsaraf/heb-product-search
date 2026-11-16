// Adapted from Cult UI "Typewriter" (MIT, Nolly Studio):
// https://github.com/nolly-studio/cult-ui/blob/main/apps/www/registry/default/ui/typewriter.tsx
// Changed: types one string once instead of cycling a list, and can render the finished text at once.
import { animate, motion, useMotionValue, useTransform } from "motion/react"
import { useEffect } from "react"

type TypewriterProps = { text: string; duration?: number; instant?: boolean }

/** Decorative: give assistive tech the full text beside it. Remount with a `key` to type a new string. */
export function Typewriter({ text, duration = 1, instant = false }: TypewriterProps) {
  const count = useMotionValue(instant ? text.length : 0)
  const shown = useTransform(count, (latest) => text.slice(0, Math.round(latest)))

  useEffect(() => {
    if (instant) {
      count.set(text.length)
      return
    }
    const controls = animate(count, text.length, { type: "tween", duration, ease: [0.42, 0, 0.58, 1] })
    return () => controls.stop()
  }, [count, text, duration, instant])

  return (
    <span aria-hidden="true">
      <motion.span>{shown}</motion.span>
      {!instant && <span className="type-cursor" />}
    </span>
  )
}
