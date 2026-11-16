// Colour-contrast check for a real browser. Paste into the console (or the browser tool) on the running app.
// Reads the colours that are painted (computed styles, alpha and opacity composited over the real backdrop), not
// the tokens. Every element that directly holds text needs 4.5:1, or 3:1 when large (WCAG 1.4.3); placeholders
// count as text; control edges need 3:1 (WCAG 1.4.11). Canvas and gradient backdrops are not read: check those by eye.
// Switch "Motion" off on the page first: a row that is still fading in reads as failing. Then run once per
// colour scheme: contrastCheck(). For focus rings, press Tab to a control with a real key, then call contrastFocus().
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
  const opacity = (el) => {
    let o = 1
    for (let n = el; n; n = n.parentElement) o *= parseFloat(getComputedStyle(n).opacity)
    return o
  }
  const row = (name, fg, bg, min) => {
    const r = ratio(fg, bg)
    return { name, ratio: +r.toFixed(2), min, pass: r >= min }
  }
  const label = (el, text) =>
    `${el.tagName.toLowerCase()}${el.classList[0] ? "." + el.classList[0] : ""} “${text.trim().slice(0, 32)}”`
  const scheme = () => (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light")
  const isLarge = (cs) => {
    const px = parseFloat(cs.fontSize)
    return px >= 24 || (px >= 18.66 && (parseInt(cs.fontWeight, 10) || 400) >= 700)
  }
  const textRow = (el, text, color) => {
    const cs = getComputedStyle(el)
    const bg = backdrop(el)
    const [r, g, b, a] = rgba(color)
    return row(label(el, text), over([r, g, b, a * opacity(el)], bg), bg, isLarge(cs) ? 3 : 4.5)
  }
  const edge = (el) => {
    const page = backdrop(el.parentElement)
    const cs = getComputedStyle(el)
    const name = `edge of ${label(el, el.getAttribute("aria-label") || el.textContent || el.type || "")}`
    const bordered = cs.borderTopStyle !== "none" && parseFloat(cs.borderTopWidth) > 0
    // A control with no border is found by its fill instead.
    const paint = bordered ? cs.borderTopColor : cs.backgroundColor
    return row(name, over(rgba(paint), page), page, 3)
  }

  window.contrastCheck = () => {
    const rows = []
    const seen = new Set()
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT)
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
      const el = node.parentElement
      if (!node.nodeValue.trim() || seen.has(el)) continue
      seen.add(el)
      if (el.closest("[aria-hidden=true], .sr-only, script, style") || !el.getClientRects().length) continue
      if (getComputedStyle(el).visibility === "hidden") continue
      rows.push(textRow(el, node.nodeValue, getComputedStyle(el).color))
    }
    for (const input of document.querySelectorAll("input[placeholder]")) {
      rows.push(textRow(input, `placeholder ${input.placeholder}`, getComputedStyle(input, "::placeholder").color))
    }
    // A switch keeps a visually hidden checkbox for forms; its painted edge is the [role=switch] element.
    const controls = "input:not([type=checkbox], [type=hidden]), button:not([role=switch]), [role=switch]"
    for (const control of document.querySelectorAll(controls)) rows.push(edge(control))
    return { scheme: scheme(), checked: rows.length, failing: rows.filter((r) => !r.pass) }
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
