import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, expect, test, vi } from "vitest"
import { App } from "./App"
import { response, stubFetch } from "./fixtures"

afterEach(() => vi.unstubAllGlobals())

const box = () => screen.getByRole("searchbox", { name: "Find products" })

async function searchFor(text: string) {
  const user = userEvent.setup()
  await user.type(box(), `${text}{Enter}`)
  return user
}

test("controls are named, and Tab visits input, Search, then Debug", async () => {
  const user = userEvent.setup()
  render(<App />)
  const button = screen.getByRole("button", { name: "Search" })
  const debug = screen.getByRole("switch", { name: "Debug" })
  expect(button.getAttribute("aria-disabled")).toBeNull()

  await user.tab()
  expect(document.activeElement).toBe(box())
  await user.tab()
  expect(document.activeElement).toBe(button)
  await user.tab()
  expect(document.activeElement).toBe(debug)
})

test("Enter in the box and the Search button both run a search; focus stays put", async () => {
  const fetchMock = stubFetch(response())
  const user = userEvent.setup()
  render(<App />)
  await user.type(box(), "pasta{Enter}")
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))
  expect((fetchMock.mock.calls[0] as unknown[])[0]).toBe("/search?q=pasta")
  expect(document.activeElement).toBe(box())

  await user.click(screen.getByRole("button", { name: "Search" }))
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2))
})

test("an empty query makes no request", async () => {
  const fetchMock = stubFetch(response())
  const user = userEvent.setup()
  render(<App />)
  await user.click(screen.getByRole("button", { name: "Search" }))
  expect(fetchMock).not.toHaveBeenCalled()
})

test("Space on the Debug switch toggles the score row under every result", async () => {
  stubFetch(response())
  render(<App />)
  const user = await searchFor("gluten free pasta")
  await screen.findByText("bm25 0.81 · semantic 0.74 · final 0.87")
  expect(screen.getAllByText(/^bm25 /)).toHaveLength(2)

  const debug = screen.getByRole("switch", { name: "Debug" })
  expect(debug.getAttribute("aria-checked")).toBe("true")
  debug.focus()
  await user.keyboard(" ")
  expect(debug.getAttribute("aria-checked")).toBe("false")
  expect(screen.queryAllByText(/^bm25 /)).toHaveLength(0)
})

test("rerank is shown when present and dropped when null", async () => {
  const r = response().results[0]!
  stubFetch(response({ results: [{ ...r, rerank_score: 0.93 }] }))
  render(<App />)
  await searchFor("x")
  await screen.findByText("bm25 0.81 · semantic 0.74 · rerank 0.93 · final 0.87")
})

test("dev query shows header with split and a label per result", async () => {
  stubFetch(response())
  render(<App />)
  await searchFor("gluten free pasta")
  await waitFor(() =>
    expect(screen.getByRole("status").textContent).toBe(
      "2 results for “gluten free pasta” · 142 ms · train query (dev)"
    )
  )
  expect(screen.getByText("label 3")).toBeTruthy()
  expect(screen.getByText("label 0")).toBeTruthy()
})

test("held-out query shows 'held out' and never a label, even if the API sent one", async () => {
  stubFetch(response({ split: "held_out" }))
  render(<App />)
  await searchFor("locked query")
  await waitFor(() => expect(screen.getByRole("status").textContent).toMatch(/ · held out$/))
  expect(screen.queryByText(/^label /)).toBeNull()
})

test("a query outside both splits shows no split and no label", async () => {
  stubFetch(response({ split: null, results: response().results.map((r) => ({ ...r, label: null })) }))
  render(<App />)
  await searchFor("anything")
  await waitFor(() =>
    expect(screen.getByRole("status").textContent).toBe("2 results for “gluten free pasta” · 142 ms")
  )
  expect(screen.queryByText(/^label /)).toBeNull()
})

test("a slow earlier response does not overwrite a newer one", async () => {
  let release!: () => void
  const slow = new Promise<Response>((res) => {
    release = () => res(new Response(JSON.stringify(response({ query: "first" }))))
  })
  const fast = new Response(JSON.stringify(response({ query: "second" })))
  vi.stubGlobal("fetch", vi.fn().mockReturnValueOnce(slow).mockResolvedValueOnce(fast))
  render(<App />)
  const user = userEvent.setup()
  await user.type(box(), "first{Enter}")
  await user.clear(box())
  await user.type(box(), "second{Enter}")
  await waitFor(() => expect(screen.getByRole("status").textContent).toMatch(/“second”/))
  release()
  await new Promise((r) => setTimeout(r, 20))
  expect(screen.getByRole("status").textContent).toMatch(/“second”/)
})

test("a rejected query shows the message", async () => {
  stubFetch({ detail: [] }, 422)
  render(<App />)
  await searchFor("x")
  await waitFor(() => expect(screen.getByRole("status").textContent).toBe("Enter 1 to 200 characters."))
})
