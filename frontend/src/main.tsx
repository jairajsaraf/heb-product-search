import "@ui-sdk/core/web.css"
import "./styles.css"
import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import { registerAgentTools } from "./agent"
import { App } from "./App"

registerAgentTools()

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>
)
