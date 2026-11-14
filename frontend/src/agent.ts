import { createAgent, registerTools } from "@ui-sdk/react/agent"
import { search } from "./api"

type Tool = {
  name: string
  description: string
  inputSchema: object
  annotations: { readOnlyHint: boolean }
  execute: (input: { query?: unknown }) => Promise<unknown>
}
type ModelContext = { registerTool?: (tool: Tool) => unknown; unregisterTool?: (name: string) => void }

const searchProducts: Tool = {
  name: "search_products",
  description:
    "Search the product catalog. Returns the top 30 products with their final, BM25 and semantic scores. Read-only.",
  inputSchema: {
    type: "object",
    properties: { query: { type: "string", minLength: 1, maxLength: 200 } },
    required: ["query"],
  },
  annotations: { readOnlyHint: true },
  execute: async ({ query }) => {
    if (typeof query !== "string" || !query.trim()) throw new Error("query must be a non-empty string")
    return search(query.trim().slice(0, 200))
  },
}

export const agent = createAgent()

export function registerAgentTools(doc: Document = document) {
  const unregisterBridge = registerTools(agent, { allow: () => true })
  const ctx = (doc as Document & { modelContext?: ModelContext }).modelContext
  let registered = false
  if (typeof ctx?.registerTool === "function") {
    try {
      Promise.resolve(ctx.registerTool(searchProducts)).catch(() => {})
      registered = true
    } catch {
      // A browser whose WebMCP throws on registration must not break the page.
    }
  }
  return () => {
    unregisterBridge()
    if (registered) ctx?.unregisterTool?.(searchProducts.name)
  }
}
