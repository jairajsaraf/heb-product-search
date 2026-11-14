// Colour-contrast check for a real browser. Paste into the console (or the browser tool) on the running app.
// Reads the colours that are painted (computed styles, alpha composited over the real backdrop), not the tokens.
// Text needs 4.5:1 (WCAG 1.4.3); control edges, switch fills and focus rings need 3:1 (WCAG 1.4.11).
// Run once per colour scheme, after a search so results exist: contrastCheck(). For focus rings, press Tab to a
// control with a real key, then call contrastFocus().
;(() => {
  const ctx = Object.assign(document.createElement("canvas"), { width: 1, height: 1 }).getContext("2d", {
    willReadFrequently: true,
  })
  const rgba = (css) => {
    ctx.clearRect(0, 0, 1, 1)
    ctx.fillStyle = "#000"
    ctx.fillStyle = css
    ctx.fillRect(0, 0, 1, 1)
    const [r, g, b, a] = ctx.getImageData(0, 0, 1, 1).data
    return [r, g, b, a / 255]
  }
  const over = ([r, g, b, a], [R, G, B]) => [r * a + R * (1 - a), g * a + G * (1 - a), b * a + B * (1 - a)]
  const lum = ([r, g, b]) => {
    const f = (v) => ((v /= 255) <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4)
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)
  }
  const ratio = (a, b) => {
    const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p)
    return (x + 0.05) / (y + 0.05)
  }
  const backdrop = (el) => {
    const layers = []
    for (let n = el; n; n = n.parentElement) {
      const c = rgba(getComputedStyle(n).backgroundColor)
      if (c[3] > 0) layers.push(c)
      if (c[3] === 1) break
    }
    let acc = [255, 255, 255]
    for (const c of layers.reverse()) acc = over(c, acc)
    return acc
  }
  const row = (name, fg, bg, min) => {
    const r = ratio(fg, bg)
    return { name, ratio: +r.toFixed(2), min, pass: r >= min }
  }
  const q = (s) => document.querySelector(s)
  const scheme = () => (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light")
  const text = (name, el) => {
    if (!el) return { name, ratio: null, min: 4.5, pass: true, skipped: "not on the page (Debug off)" }
    const bg = backdrop(el)
    return row(name, over(rgba(getComputedStyle(el).color), bg), bg, 4.5)
  }
  const edge = (name, el) => {
    const page = backdrop(el.parentElement)
    const cs = getComputedStyle(el)
    if (cs.borderTopStyle === "none" || parseFloat(cs.borderTopWidth) === 0) return { name, ratio: null, min: 3, pass: false }
    return row(name, over(rgba(cs.borderTopColor), page), page, 3)
  }

  window.contrastCheck = () => {
    const input = q("input[type=search]")
    const button = q("form button[type=submit]")
    const sw = q("[role=switch]")
    const page = backdrop(sw.parentElement)
    const rows = [
      text("label “Find products” on page", q("label")),
      text("typed text in the search box", input),
      text("search button text", button),
      text("results header", q("output")),
      text("result title", q(".result-line .title")),
      text("score row (muted)", q(".scores")),
      text("result label (muted)", q(".result-line .label")),
      edge("search box border vs page", input),
      edge("search button border vs page", button),
      edge("Debug switch edge vs page", sw),
      // Off, the track is the page colour on purpose: the edge and the thumb carry that state.
      sw.getAttribute("aria-checked") === "true"
        ? row("Debug switch fill (on) vs page", over(rgba(getComputedStyle(sw).backgroundColor), page), page, 3)
        : { name: "Debug switch fill (off): edge and thumb rows apply", ratio: null, min: 3, pass: true, skipped: "off" },
      row(
        "Debug switch thumb vs track",
        over(rgba(getComputedStyle(sw.firstElementChild).backgroundColor), over(rgba(getComputedStyle(sw).backgroundColor), page)),
        over(rgba(getComputedStyle(sw).backgroundColor), page),
        3
      ),
    ]
    return { scheme: scheme(), rows, failing: rows.filter((r) => !r.pass).map((r) => r.name) }
  }

  window.contrastFocus = () => {
    const el = document.activeElement
    const cs = getComputedStyle(el)
    const page = backdrop(el.parentElement ?? el)
    return {
      scheme: scheme(),
      el: el.tagName + (el.getAttribute("type") ? "[" + el.getAttribute("type") + "]" : ""),
      focusVisible: el.matches(":focus-visible"),
      outline: cs.outlineStyle + " " + cs.outlineWidth,
      outlineVsPage: row("focus outline", over(rgba(cs.outlineColor), page), page, 3),
      borderVsPage: row("border while focused", over(rgba(cs.borderTopColor), page), page, 3),
    }
  }
})()
