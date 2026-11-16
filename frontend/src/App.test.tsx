import { render, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, expect, test, vi } from "vitest"
import { App } from "./App"
import { keywordOnly, response, stubFetch } from "./fixtures"

afterEach(() => vi.unstubAllGlobals())

const box = () => screen.getByRole("searchbox", { name: "Find products" })
const status = () => screen.getByRole("status").textContent
const shelf = (name: string) => within(screen.getByRole("region", { name }))
const scoreLines = () => [...document.querySelectorAll(".scores")].map((node) => node.textContent)
const DEV_STATUS =
  "Top 2 results for “gluten free pasta”, ranked in 142 ms on the server. This query is in the graded development set."

async function searchFor(text: string) {
  const user = userEvent.setup()
  await user.type(box(), `${text}{Enter}`)
  return user
}

test("controls are named, and Tab visits the search box, Search, then the first example", async () => {
  const user = userEvent.setup()
  render(<App />)
  const button = screen.getByRole("button", { name: "Search" })
  screen.getByRole("switch", { name: "Show score breakdown" })
  expect(button.getAttribute("aria-disabled")).toBeNull()

  await user.tab()
  expect(document.activeElement).toBe(box())
  await user.tab()
  expect(document.activeElement).toBe(button)
  await user.tab()
  expect(document.activeElement?.textContent).toContain("protein-packed chicken salads")
})

test("before any search the page shows a worked example and the measured result, with no request", () => {
  const fetchMock = stubFetch(response())
  render(<App />)
  expect(screen.getByRole("heading", { level: 1 }).textContent).toMatch(/ranks by meaning as well as keywords/)
  screen.getByRole("heading", { name: /Results for .*protein-packed chicken salads/ })
  expect(shelf("Keyword only").getAllByRole("listitem")).toHaveLength(10)
  expect(shelf("Keyword + meaning").getAllByRole("listitem")).toHaveLength(10)
  // Ungraded is not the same as graded wrong, and the two must stay distinguishable.
  expect(shelf("Keyword only").getAllByText("Not graded")).toHaveLength(8)
  expect(shelf("Keyword + meaning").getAllByText("Grade 3")).toHaveLength(10)
  expect(document.querySelector(".claims")?.textContent).toMatch(/What was measured.*\+0\.0725.*\+0\.0063/)
  expect(fetchMock).not.toHaveBeenCalled()
})

test("an example button swaps the worked example without a request", async () => {
  const fetchMock = stubFetch(response())
  const user = userEvent.setup()
  render(<App />)
  await user.click(screen.getByRole("button", { name: /^seasoning for chicken fajitas/ }))
  screen.getByRole("heading", { name: /Results for .*seasoning for chicken fajitas/ })
  expect(shelf("Keyword + meaning").getAllByText("Graded not relevant")).toHaveLength(9)
  expect(fetchMock).not.toHaveBeenCalled()
})

test("Enter in the box and the Search button both run a search; focus stays put", async () => {
  const fetchMock = stubFetch(response())
  const user = userEvent.setup()
  render(<App />)
  await user.type(box(), "pasta{Enter}")
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2))
  expect(fetchMock.mock.calls.map((call) => call[0])).toEqual(["/search?q=pasta", "/search?q=pasta&mode=bm25"])
  expect(document.activeElement).toBe(box())

  await user.click(screen.getByRole("button", { name: "Search" }))
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(4))
})

test("an empty query makes no request", async () => {
  const fetchMock = stubFetch(response())
  const user = userEvent.setup()
  render(<App />)
  await user.click(screen.getByRole("button", { name: "Search" }))
  expect(fetchMock).not.toHaveBeenCalled()
})

test("a search shows the keyword-only ranking beside the hybrid one", async () => {
  stubFetch(response())
  render(<App />)
  await searchFor("gluten free pasta")
  await waitFor(() => expect(status()).toBe(DEV_STATUS))
  expect(shelf("Keyword only").getAllByRole("listitem")).toHaveLength(2)
  expect(shelf("Keyword + meaning").getAllByText("Same rank by keywords")).toHaveLength(2)
  screen.getByText(/0 of these 2 are not in the keyword top 2\./)
})

test("a server that ignores the mode parameter never has its hybrid list shown as keyword-only", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => new Response(JSON.stringify(response())))
  )
  render(<App />)
  await searchFor("gluten free pasta")
  await waitFor(() => expect(status()).toBe(DEV_STATUS))
  shelf("Keyword only").getByText("This server did not return a keyword-only ranking for this search.")
  expect(shelf("Keyword + meaning").getAllByRole("listitem")).toHaveLength(2)
})

test("Space on the score breakdown switch toggles the score line under every result", async () => {
  stubFetch(response())
  render(<App />)
  const user = await searchFor("gluten free pasta")
  await waitFor(() => expect(status()).toBe(DEV_STATUS))
  expect(scoreLines()).toEqual([
    "keyword 0.81",
    "keyword 0.81",
    "0.10 × keyword 0.81 + 0.90 × meaning 0.74 = 0.87",
    "0.10 × keyword 0.81 + 0.90 × meaning 0.74 = 0.86",
  ])

  const toggle = screen.getByRole("switch", { name: "Show score breakdown" })
  expect(toggle.getAttribute("aria-checked")).toBe("true")
  toggle.focus()
  await user.keyboard(" ")
  expect(toggle.getAttribute("aria-checked")).toBe("false")
  expect(scoreLines()).toHaveLength(0)
})

test("rerank is shown when present and dropped when null", async () => {
  const r = response().results[0]!
  stubFetch(response({ results: [{ ...r, rerank_score: 0.93 }] }))
  render(<App />)
  await searchFor("x")
  await waitFor(() => expect(scoreLines()).toContain("0.10 × keyword 0.81 + 0.90 × meaning 0.74 = 0.87, rerank 0.93"))
})

test("a development query says so and shows a grade per result", async () => {
  stubFetch(response())
  render(<App />)
  await searchFor("gluten free pasta")
  await waitFor(() => expect(status()).toBe(DEV_STATUS))
  shelf("Keyword + meaning").getByText("Grade 3")
  // The API sends 0 for both "graded not relevant" and "never graded".
  shelf("Keyword + meaning").getByText("Not relevant or not graded")
})

test("a locked query says so and never shows a grade, even if the API sent one", async () => {
  stubFetch(response({ split: "held_out" }))
  render(<App />)
  await searchFor("locked query")
  await waitFor(() => expect(status()).toMatch(/locked test set, so its grades stay hidden\.$/))
  expect(document.querySelector(".grade")).toBeNull()
})

test("a query outside both splits shows no split and no grade", async () => {
  stubFetch(response({ split: null, results: response().results.map((r) => ({ ...r, label: null })) }))
  render(<App />)
  await searchFor("anything")
  await waitFor(() => expect(status()).toBe("Top 2 results for “gluten free pasta”, ranked in 142 ms on the server."))
  expect(document.querySelector(".grade")).toBeNull()
})

test("a slow earlier response does not overwrite a newer one", async () => {
  let release!: () => void
  const gate = new Promise<void>((resolve) => {
    release = resolve
  })
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      const first = url.includes("q=first")
      if (first) await gate
      const body = response({ query: first ? "first" : "second" })
      return new Response(JSON.stringify(url.includes("mode=bm25") ? keywordOnly(body) : body))
    })
  )
  render(<App />)
  const user = userEvent.setup()
  await user.type(box(), "first{Enter}")
  await user.clear(box())
  await user.type(box(), "second{Enter}")
  await waitFor(() => expect(status()).toMatch(/“second”/))
  release()
  await new Promise((r) => setTimeout(r, 20))
  expect(status()).toMatch(/“second”/)
})

test("a rejected query shows the message and an empty state", async () => {
  stubFetch({ detail: [] }, 422)
  render(<App />)
  await searchFor("x")
  await waitFor(() => expect(status()).toBe("Enter 1 to 200 characters."))
  screen.getByText(/Nothing to show for that search/)
})

test("a whitespace-only query makes no request", async () => {
  const fetchMock = stubFetch(response())
  const user = userEvent.setup()
  render(<App />)
  await user.type(box(), "   {Enter}")
  expect(fetchMock).not.toHaveBeenCalled()
})

test("a slow search shows Searching… then the pipeline strip, and both go away with the results", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      await new Promise((r) => setTimeout(r, 600))
      const body = response()
      return new Response(JSON.stringify(String(url).includes("mode=bm25") ? keywordOnly(body) : body))
    })
  )
  render(<App />)
  await searchFor("pasta")
  expect(status()).toBe("Searching…")
  expect(document.querySelector(".stage .pipeline")).toBeNull()
  await waitFor(() => expect(document.querySelector(".stage .pipeline")).not.toBeNull())
  expect(status()).toBe("Searching…")
  await waitFor(() => expect(status()).toBe(DEV_STATUS))
  await waitFor(() => expect(document.querySelector(".stage .pipeline")).toBeNull())
  expect(shelf("Keyword + meaning").getAllByRole("listitem")).toHaveLength(2)
})

test("with Motion on, the slow-search loader renders inside the results panel, not over the page", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => {
      await new Promise((r) => setTimeout(r, 600))
      return new Response(JSON.stringify(response()))
    })
  )
  render(<App />)
  const user = userEvent.setup()
  await user.click(screen.getByRole("switch", { name: "Motion" }))
  await user.type(box(), "pasta{Enter}")
  await waitFor(() => expect(document.querySelector(".stage [aria-hidden='true'].absolute.inset-0")).not.toBeNull())
  expect(document.querySelector(".fixed.inset-0")).toBeNull()
  expect(document.querySelector(".stage .pipeline")).toBeNull()
  await waitFor(() => expect(status()).toBe(DEV_STATUS))
})

test("a keyword list where nothing matched says so instead of listing arbitrary products", async () => {
  const body = response({ results: response().results.map((r) => ({ ...r, bm25_score: 0 })) })
  stubFetch(body)
  render(<App />)
  await searchFor("zzzz qqqq")
  await waitFor(() => expect(status()).toMatch(/Top 2 results/))
  shelf("Keyword only").getByText(
    "No product shares a word with this search, so keyword search has nothing to rank."
  )
  expect(shelf("Keyword only").queryAllByRole("listitem")).toHaveLength(0)
  expect(shelf("Keyword + meaning").getAllByRole("listitem")).toHaveLength(2)
})

test("a network failure shows an error and an empty state, and a later search recovers", async () => {
  const fail = vi.fn(async () => {
    throw new TypeError("Failed to fetch")
  })
  vi.stubGlobal("fetch", fail)
  render(<App />)
  const user = await searchFor("x")
  await waitFor(() => expect(status()).toBe("The search server did not answer. Check your connection and try again."))
  screen.getByText(/Nothing to show for that search/)
  expect(screen.queryByRole("region", { name: "Keyword only" })).toBeNull()

  stubFetch(response())
  await user.clear(box())
  await user.type(box(), "pasta{Enter}")
  await waitFor(() => expect(status()).toBe(DEV_STATUS))
  expect(shelf("Keyword + meaning").getAllByRole("listitem")).toHaveLength(2)
})

test("HTML entities in product titles are decoded as text", async () => {
  const r = response().results[0]!
  stubFetch(response({ results: [{ ...r, title: "Pork Ribs &ndash; Sweet &amp; Hot <b>x</b>" }] }))
  render(<App />)
  await searchFor("ribs")
  await waitFor(() => expect(shelf("Keyword + meaning").getByRole("listitem").textContent).toContain("Pork Ribs – Sweet & Hot x"))
  expect(document.querySelector(".row b")).toBeNull()
})

test("motion starts off for a visitor who prefers reduced motion", () => {
  render(<App />)
  expect(screen.getByRole("switch", { name: "Motion" }).getAttribute("aria-checked")).toBe("false")
  expect(screen.queryByRole("button", { name: "Replay the re-rank" })).toBeNull()
})
