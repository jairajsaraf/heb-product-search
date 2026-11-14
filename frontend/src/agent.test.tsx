import { render, screen, waitFor } from "@testing-library/react"
import { afterEach, expect, test, vi } from "vitest"
import { agent, registerAgentTools } from "./agent"
import { App } from "./App"
import { response, stubFetch } from "./fixtures"

afterEach(() => {
  vi.unstubAllGlobals()
  Reflect.deleteProperty(document, "modelContext")
})

test("an agent can find and change every control", async () => {
  const fetchMock = stubFetch(response())
  render(<App />)

  const components = agent.snapshot().filter((entry) => !entry.offPage && entry.component !== "more")
  for (const entry of components) {
    expect(entry.label, `${entry.component} ${entry.ref} has no name`).toBeTruthy()
  }
  const labels = components.map((entry) => entry.label)
  for (const label of ["Find products", "Search", "Debug"]) {
    expect(labels, `${label} is missing from the snapshot`).toContain(label)
  }

  const result = await agent.act({
    steps: [
      { ref: "Find products", action: "setValue", args: ["gluten free pasta"] },
      { ref: "Debug", action: "setChecked", args: [false] },
      { ref: "Search", action: "press" },
    ],
  })
  expect(result.ok, result.error?.message).toBe(true)
  expect((screen.getByRole("searchbox", { name: "Find products" }) as HTMLInputElement).value).toBe(
    "gluten free pasta"
  )
  expect(screen.getByRole("switch", { name: "Debug" }).getAttribute("aria-checked")).toBe("false")
  await waitFor(() => expect(fetchMock).toHaveBeenCalledWith("/search?q=gluten+free+pasta", expect.anything()))
  await screen.findByText("label 3")
  expect(screen.queryAllByText(/^bm25 /)).toHaveLength(0)
})

test("search_products is registered read-only through document.modelContext and returns the API body", async () => {
  const tools = new Map<string, { annotations?: { readOnlyHint?: boolean }; execute: (i: object) => Promise<unknown> }>()
  Object.assign(document, {
    modelContext: {
      registerTool: async (tool: { name: string; execute: (i: object) => Promise<unknown> }) => {
        tools.set(tool.name, tool)
      },
      unregisterTool: (name: string) => tools.delete(name),
    },
  })
  const fetchMock = stubFetch(response())
  const unregister = registerAgentTools()

  expect([...tools.keys()].sort()).toEqual(["act", "query", "search_products", "snapshot"])
  const tool = tools.get("search_products")!
  expect(tool.annotations?.readOnlyHint).toBe(true)
  const body = (await tool.execute({ query: "gluten free pasta" })) as ReturnType<typeof response>
  expect(body.results).toHaveLength(2)
  expect((fetchMock.mock.calls[0] as unknown[])[0]).toBe("/search?q=gluten+free+pasta")
  await expect(tool.execute({ query: "  " })).rejects.toThrow("non-empty")
  expect(fetchMock).toHaveBeenCalledTimes(1)

  unregister()
  expect(tools.has("search_products")).toBe(false)
})

test("without document.modelContext registration does nothing and does not throw", () => {
  expect(typeof (document as unknown as { modelContext?: { registerTool?: unknown } }).modelContext?.registerTool).toBe(
    "undefined"
  )
  expect(() => registerAgentTools()()).not.toThrow()
})
