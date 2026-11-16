// Adapted from Cult UI "Rolling Number" (MIT, Nolly Studio):
// https://github.com/nolly-studio/cult-ui/blob/main/apps/www/registry/default/ui/rolling-number.tsx
// Changed: starts at `from` and rolls to `value` when it scrolls into view; shows `value` at once when motion is off.
import { motion, useInView, useSpring, useTransform } from "motion/react"
import { useContext, useEffect, useRef } from "react"
import { MotionContext } from "../utils"

type RollingNumberProps = {
  value: number
  from?: number
  format: (value: number) => string
  mass?: number
  stiffness?: number
  damping?: number
}

export function RollingNumber({ value, from = 0, format, mass = 0.8, stiffness = 75, damping = 15 }: RollingNumberProps) {
  const moving = useContext(MotionContext)
  const ref = useRef<HTMLSpanElement>(null)
  const inView = useInView(ref, { once: true })
  const spring = useSpring(moving ? from : value, { mass, stiffness, damping })
  const display = useTransform(spring, (current) => format(current))

  useEffect(() => {
    if (!moving) spring.jump(value)
    else if (inView) spring.set(value)
  }, [moving, inView, spring, value])

  return <motion.span ref={ref}>{display}</motion.span>
}
