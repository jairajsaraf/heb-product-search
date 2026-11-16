import { act, render } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { GridBeam } from "./grid-beam"

const originalGetContext = HTMLCanvasElement.prototype.getContext
// Every property is a no-op function that returns the same fake, so gradients have addColorStop.
const fakeCtx: unknown = new Proxy(
  {},
  { get: () => () => fakeCtx, set: () => true }
)

let pending: Map<number, FrameRequestCallback>
let nextId: number
let cancelSpy: ReturnType<typeof vi.fn>

// Runs the frames requested so far, at the current fake time, and returns how many were run.
function step(): number {
  const frames = [...pending.values()]
  pending.clear()
  for (const frame of frames) {
    frame(performance.now())
  }
  return frames.length
}

beforeEach(() => {
  vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout", "performance"] })
  pending = new Map()
  nextId = 1
  cancelSpy = vi.fn((id: number) => {
    pending.delete(id)
  })
  vi.stubGlobal("requestAnimationFrame", (cb: FrameRequestCallback) => {
    pending.set(nextId, cb)
    return nextId++
  })
  vi.stubGlobal("cancelAnimationFrame", cancelSpy)
  HTMLCanvasElement.prototype.getContext = (() =>
    fakeCtx) as unknown as typeof HTMLCanvasElement.prototype.getContext
})

afterEach(() => {
  HTMLCanvasElement.prototype.getContext = originalGetContext
  vi.unstubAllGlobals()
  vi.useRealTimers()
})

describe("GridBeam frame loop", () => {
  it("stops requesting frames when rendered inactive", () => {
    render(<GridBeam active={false} />)
    expect(pending.size).toBe(1)
    step()
    expect(pending.size).toBe(0)
  })

  it("restarts when it becomes active and keeps going", () => {
    const { rerender } = render(<GridBeam active={false} />)
    step()
    expect(pending.size).toBe(0)

    rerender(<GridBeam active />)
    expect(pending.size).toBe(1)
    for (let i = 0; i < 5; i++) {
      vi.advanceTimersByTime(16)
      step()
      expect(pending.size).toBe(1)
    }
  })

  it("keeps drawing through the fade-out, then stops", () => {
    const { rerender } = render(<GridBeam active />)
    vi.advanceTimersByTime(16)
    step()

    rerender(<GridBeam active={false} />)
    for (let i = 0; i < 5; i++) {
      vi.advanceTimersByTime(100)
      step()
      expect(pending.size).toBe(1)
    }

    // Past the 600 ms fade and the 700 ms timer that clears `fadingOut`.
    act(() => {
      vi.advanceTimersByTime(300)
    })
    step()
    expect(pending.size).toBe(0)
  })

  it("cancels the pending frame on unmount", () => {
    const { unmount } = render(<GridBeam active />)
    step()
    expect(pending.size).toBe(1)
    const [id] = [...pending.keys()]
    unmount()
    expect(cancelSpy).toHaveBeenCalledWith(id)
    expect(pending.size).toBe(0)
  })
})
