import { clsx, type ClassValue } from "clsx"
import { createContext } from "react"
import { twMerge } from "tailwind-merge"
import evidence from "./evidence.json"

export const cn = (...inputs: ClassValue[]) => twMerge(clsx(inputs))

/** False when the visitor prefers reduced motion or has switched motion off on the page. */
export const MotionContext = createContext(true)

type Facts = typeof evidence.facts

/** A measured value and the report file it was copied from (checked by checks/evidence.test.ts). */
export function fact<K extends keyof Facts>(key: K): Facts[K] {
  return evidence.facts[key]
}

export const REPO = "https://github.com/jairajsaraf/heb-product-search"
export const sourceUrl = (path: string) => `${REPO}/blob/main/${path}`

const MINUS = "−"
export const fixed = (n: number, digits = 2) => n.toFixed(digits).replace("-", MINUS)
export const signed = (n: number, digits = 4) => (n >= 0 ? "+" : MINUS) + Math.abs(n).toFixed(digits)
export const percent = (n: number) => `${(n * 100).toFixed(1)}%`

// Catalog titles carry HTML entities (&ndash;, &eacute;). Reading textContent decodes them without creating markup.
export function decodeEntities(text: string) {
  if (!text.includes("&")) return text
  return new DOMParser().parseFromString(text, "text/html").documentElement.textContent ?? text
}
