# Landing page rebuild: verification

Written 2026-11-15. Branch `feat/landing-page`, cut from `main` at `29b52ee`. When this was written nothing was committed, pushed or deployed. The page was later merged (PRs 12 and 13) and redeployed to Cloud Run on 2026-11-16 UTC; see section 4.2.

Plan: `docs/plans/2026-11-14-landing-page-rebuild.md`. Each claim below is marked **confirmed** (with the command or observation), **inferred**, or **unknown**.

## 1. Result

The page is rebuilt and passes every gate. Lighthouse performance on its throttled mobile profile first fell from 1.0 to 0.69 because the server sent responses uncompressed; after adding gzip to the API it measures 0.95 on two runs (section 4). That is still below the old page's 1.0. Accessibility stayed at 1.0, which was the locked requirement.

## 2. Gates on the final tree

All run on 2026-11-15 after the last code change, unless a row says otherwise. All **confirmed**.

| Gate | Command | Result |
|---|---|---|
| Type check | `npx tsc -b` in `frontend/` | exit 0 |
| Frontend tests | `npm test` in `frontend/` | 91 passed, 3 files |
| Frontend build | `npm run build` in `frontend/` | succeeded; JS 653.81 kB (196.52 kB gzip), CSS 111.64 kB (16.76 kB gzip); Vite warns that the JS chunk is over 500 kB |
| Python tests | `.venv/Scripts/python.exe -m pytest tests -q` | 22 passed (21 plus the gzip test) |
| Contrast, dark | `contrastCheck()` from `frontend/checks/contrast.js` on the built page, Motion off, 1440 px | 221 items, 0 failing |
| Contrast, light | same | 221 items, 0 failing |
| Contrast after a live search | same, after searching `low-sodium dried beans` (status line named the query, 20 grade chips shown) | 228 items, 0 failing, in dark and in light. Run before the polish pass. |
| Horizontal overflow | `scrollWidth <= clientWidth` | no overflow at 1440 px (my run) and at 375 px in both schemes (subagent run) |
| Lighthouse | section 4 | accessibility 1.0; performance 0.95 on two runs (0.69 before gzip) |
| Docker build | `docker build -t heb-search:landing-check .` | succeeded, exit 0, on the final tree including the gzip change and the `.woff2` type fix |
| Container smoke test | `docker run -p 8089:8080`, then curl | `/health` returned `{"status":"ok","mode":"hybrid"}`; `/` 200; JS 194,697 bytes with `Accept-Encoding: gzip` and 653,814 with `identity`; font served as `content-type: font/woff2` with no `content-encoding`, 90,104 bytes with both `gzip` and `identity` (rebuilt and rerun after the font fix, section 4); `/search?q=milk&k=2&mode=bm25` returned mode `bm25` with every `semantic_score` null; `&mode=rrf` returned 422 |

Baseline before any change (2026-11-14): pytest 20 passed, vitest 13 passed, JS 304.94 kB (98.82 kB gzip).

## 3. What was built

- **API:** one additive query parameter, `mode=bm25|hybrid`, on `GET /search`. Default behaviour is unchanged. `tests/test_api.py` gained a test for keyword-only mode on a hybrid searcher, and the locked-label test now runs in both modes.
- **Data files:** `frontend/scripts/build_data.py` writes `frontend/src/evidence.json` (60 facts, each with its source file and JSON path) and `frontend/src/examples.json` (five development queries, hybrid and keyword-only top 10, with grades read from the label file so that "never graded" stays distinct from "graded 0"). `frontend/checks/evidence.test.ts` recomputes every fact from its source and fails on any difference, and fails if an example query is in the locked set.
- **Page:** hero with what it is, what was measured and what was built; a worked example on load with no request; two ranked lists side by side that re-rank; a score breakdown per row; evidence with three intervals on one axis; two worked failures; what was tried and dropped; limits.
- **Effects:** Cult UI Grid Beam, Typewriter, Rolling Number and Border Beam (MIT); Aceternity Multi Step Loader, Glowing Effect and Tracing Beam. Each copied file names its source and licence. With the page's Motion switch off, or when the visitor prefers reduced motion, none of them animate.

## 4. Lighthouse

**Confirmed.** `npx --yes lighthouse http://127.0.0.1:8000/ --output json --chrome-flags="--headless" --no-enable-error-reporting --quiet`, exit 0, Lighthouse 13.6.0, mobile form factor, simulated throttling (150 ms RTT, 1.6 Mbps, 4x CPU slowdown), no run warnings. The JSON was written to a session scratch folder outside the repo as `lighthouse_landing.json`; it is not committed.

The earlier run in `reports/lighthouse.json` was against the deployed Cloud Run service, so the two are not the same host. The transfer sizes below make them comparable on the point that matters.

**After gzip (confirmed).** Same command, Lighthouse 13.6.0, against my own `uvicorn` on port 8010 with the gzip change, `--output-path` set to `lighthouse_landing_gzip.json` (run 1) and `lighthouse_landing_gzip2.json` (run 2) in the same scratchpad folder. Both exit 0.

| Category | New page, before gzip | New page, after gzip (both runs) | Old page, deployed |
|---|---|---|---|
| Performance | 0.69 | 0.95 | 1.0 |
| Accessibility | 1.0 | 1.0 | 1.0 |
| Best practices | 0.96 | 0.96 | 0.96 |
| SEO | 1.0 | 1.0 | 0.9 |
| Agentic browsing | 1.0 | 1.0 | 1.0 |

| Metric | New, before gzip | New, after gzip | Old |
|---|---|---|---|
| First and largest contentful paint | 4.9 s | 2.2 s (both runs) | 1.2 s |
| Total blocking time | 130 ms | 140 ms, then 130 ms | 0 ms |
| Cumulative layout shift | 0 | 0 | 0 |

Transfer size from the `network-requests` audit (bytes):

| File | Before gzip | After gzip |
|---|---|---|
| JS | 654,067 | 195,086 |
| CSS | 111,889 | 17,068 |
| Font | 90,350 | 90,477 |

**Why performance fell (confirmed from both JSON files):** neither server compressed its responses at that point. In the old run on Cloud Run the JS transferred 305,782 bytes for a 304,940-byte file. The new JS transfers 654,067 bytes, the CSS 111,889 and the font 90,350. On the 1.6 Mbps profile that is several seconds before first paint.

**Fix done (the owner approved it):** `GZipMiddleware` added in `tamu25/api/app.py` with `minimum_size=1000` and `compresslevel=6`; no new package. Following the FastAPI "Advanced Middleware" page. Measured on the local server with `curl -s -o /dev/null -w "%{size_download}"` (**confirmed**):

| Path | `Accept-Encoding: identity` | `Accept-Encoding: gzip` |
|---|---|---|
| `/` | 743 | 743 (under 1,000 bytes, not compressed) |
| JS | 653,814 | 194,697 |
| CSS | 111,643 | 16,750 |
| `/search?q=milk` | 7,077 | 1,635 |
| Font | 90,104 | 90,157 before the font fix; 90,104 after it (below) |

Performance went from 0.69 to 0.95 and first contentful paint from 4.9 s to 2.2 s (**confirmed**, two runs, same numbers). The score is still below the old page's 1.0. The remaining gap is **inferred** to be the 195 kB of JS plus the 90 kB font on the 1.6 Mbps profile; I did not test that.

**Font was gzipped by mistake, now fixed (confirmed):** the font went out with `content-encoding: gzip` and `content-type: application/octet-stream`, in both the local run and the Docker container, so it was 53 bytes larger and cost CPU. Python's `mimetypes.guess_type("a.woff2")` returns `(None, None)`, so `StaticFiles` could not label the file and the middleware's default exclusion of `font/woff2` never matched. The owner approved a fix: `tamu25/api/app.py` now calls `mimetypes.add_type("font/woff2", ".woff2")` once at import; the middleware arguments are unchanged and no `exclude_content_types` is passed. The gzip test in `tests/test_api.py` gained assertions that a 2,048-byte `.woff2` is served as `font/woff2` with no `content-encoding` (pytest still 22 passed). Measured with `curl` on my own `uvicorn` (port 8010) and on the rebuilt container (port 8089): `content-type: font/woff2`, no `content-encoding` line, 90,104 bytes with `Accept-Encoding: gzip` and 90,104 with `identity`. The JS is still gzipped in both: 194,697 bytes with gzip, 653,814 with identity, `content-encoding: gzip`. The Lighthouse scores and transfer sizes above were measured before this font fix and were not rerun.

**Best practices at 0.96 (confirmed):** the only console error is `favicon.ico` returning 404, the same as before. A favicon was not added because it was outside the task.

**SEO rose to 1.0 (confirmed):** the page now has a meta description.

### 4.1 Rerun after the font fix, favicon and code-splitting (2026-11-16 UTC)

**Confirmed from the Lighthouse JSON files** (session scratch folder outside the repo; not committed). Same command as above, Lighthouse 13.6.0, mobile, simulated throttling, against my own `uvicorn` on port 8010, 5 runs per set. Medians computed by me from the JSON (`categories.*.score`, and `numericValue` of the first-contentful-paint, largest-contentful-paint, total-blocking-time and cumulative-layout-shift audits).

These runs are after the `.woff2` fix (font served as `font/woff2`, 90,104 bytes, no gzip) and with the favicon in place, so the 0.96 best-practices score above no longer applies: the console-errors audit is empty in the runs I opened (first and fifth of each set).

The "before" build is the tree with the favicon and font fix and no code-splitting. It was run as two sets of 5 (`base`, `base2`; same JS file name in both, so the same build) to see the spread. The "after" build lazy-loads the below-the-fold sections through `frontend/src/components/lower.tsx`.

| Metric (median of 5) | Before, set 1 | Before, set 2 | After code-splitting |
|---|---|---|---|
| Performance | 0.93 | 0.93 | 0.95 |
| Best practices | 1.00 | 1.00 | 1.00 |
| First contentful paint | 2,248 ms | 2,237 ms | 2,146 ms |
| Largest contentful paint | 2,248 ms | 2,237 ms | 2,146 ms |
| Total blocking time | 210 ms | 204 ms | 139 ms |
| Cumulative layout shift | 0 | 0 | 0 |

Individual performance scores: before set 1 0.93, 0.93, 0.92, 0.93, 0.92; before set 2 0.95, 0.92, 0.93, 0.93, 0.92; after 0.95, 0.96, 0.95, 0.96, 0.95. First and largest contentful paint were the same value in every run. Total blocking time ranged 146 to 237 ms before and 100 to 157 ms after.

Initial JS chunk, from the Vite build output, and transfer size from the `network-requests` audit:

| Build | JS (raw / gzip, Vite) | Transfer in Lighthouse (bytes) |
|---|---|---|
| Before | 653.98 kB / 196.56 kB | 195,128 |
| After, entry chunk | 627.63 kB / 188.40 kB | 187,187 |
| After, `lower` chunk (loaded after first paint) | 27.24 kB / 9.83 kB | 10,081 |

Reading these numbers:

- The earlier 0.95 in this section was one run (two, in the gzip rerun), taken before the font fix. On this machine a 5-run baseline median is 0.93, not 0.95, and the baseline runs span 0.92 to 0.95. The 0.95 was the top of that spread, not a typical run.
- After code-splitting the median is 0.95 and the five runs span 0.95 to 0.96. The gain is about 0.02 (**confirmed** as a difference between medians; **inferred** to come from the smaller entry chunk, since nothing else differed between the two builds that I know of, and I did not test any other cause). The ranges touch at 0.95, so this is a small effect.
- The entry chunk shrank about 4%, because most of the bundle is not below the fold. The score is still below the old page's 1.0.
- All of this is a local build on one machine. The deployed service was measured after the redeploy; see 4.2.

### 4.2 Live Cloud Run, after the redeploy (2026-11-16 UTC)

**Confirmed from the 5 JSON files** in the session scratch folder outside the repo. Same Lighthouse command as above, against the live URL `https://heb-search-246501698420.us-central1.run.app/`. Lighthouse 13.6.0, mobile, simulated throttling. All 5 runs exited 0.

| Metric | Median of 5 |
|---|---|
| Performance | 0.96 (runs 0.96, 0.97, 0.96, 0.97, 0.94) |
| Accessibility | 1.0 |
| Best practices | 1.0 |
| SEO | 1.0 |
| First contentful paint = largest contentful paint | 2,033 ms |
| Total blocking time | 125 ms (124.5) |
| Cumulative layout shift | 0 |

Reading these numbers:

- The live median (0.96) is a little above the local after-splitting median in 4.1 (0.95). **Inferred:** different host and network path. Not investigated.
- The old deployed page in `reports/lighthouse.json` scored performance 1.0 with LCP 1.2 s, from one run of a much smaller page. That is not a like-for-like comparison.
- Best practices rose from 0.96 to 1.0 and SEO from 0.9 to 1.0 against that old live run. **Confirmed** by comparing the two sets of numbers.
- The instance was warm, so this is not a cold-start measurement.

## 5. Failure states

Checked by a subagent on 2026-11-14, then its diff read and its tests rerun. All **confirmed** unless noted.

| State | Result |
|---|---|
| Empty or whitespace-only query | No request is sent. Tests cover both. |
| Rejected query (422) | API returns 422 for an empty `q`, a 201-character `q` and `mode=rrf`. The page shows "Enter 1 to 200 characters." and an empty state. |
| Slow request | Status reads "Searching…"; after 300 ms the pipeline steps show; both go when results arrive. Test added. |
| No keyword overlap (`zzzz qqqq`) | Was wrong: the keyword list showed ten arbitrary products with score 0. Fixed: it now says no product shares a word with the search. Test added. |
| Network failure | Was showing the browser's raw "Failed to fetch". Fixed: it now says the server did not answer and to try again. A later search recovers. Test added. |
| 375 px width, both schemes | No horizontal overflow. Both switches drew 18 px tall; their hit area is now about 40 by 26. |
| Keyboard only | Tab order is search box, Search, five example buttons, two switches, then links and buttons below. Focus ring contrast 4.23 against a minimum of 3. Enter searches; Space toggles both switches. |
| Reduced motion | With Motion off, final states show at once and the replay button is absent. |

## 6. Fresh reviewer

An Opus subagent with no session context was given only the page's visible text and the three kit questions. This is weaker evidence than a real reader; `reports/recruiter_kit.md` is the real check and has not been run. Its answers, verbatim:

**Question 1 (first screen only): What does it do, and what was built?**

> It's a product search over about 3,300 H-E-B grocery items. It mixes plain keyword matching with embedding similarity, so a query can match on meaning and not only on the exact words. It's a datathon project, not H-E-B's real search. It uses no LLM and nothing was trained. The author built the ranker, an evaluation setup with a test set that was locked and scored once, a search API, and the demo page. The headline number is that the official score went from about 0.63 to 0.70. A second line says the gain "cannot be told apart from zero" when only graded products are counted, and from the first screen alone I didn't know what to make of that.

**Question 2 (whole page): How much better than keyword search, and how sure is the author?**

> On the official datathon metric it's about 0.07 better (0.627 to 0.700) on 58 held-out queries, and the confidence interval is clearly above zero. Cross-validation on the 230 development queries gives almost the same number. The author is open that this may not mean better rankings. Counting only products that have grades, the gain is about 0.006 and could be zero. Much of the official gain seems to come from keyword search putting far more ungraded products in its top 10 (24.5% against 6.9%), and the official metric scores every ungraded product as wrong. No human has compared the two rankings yet. So the author is sure the metric went up, but not sure the search is actually better, and says so.

**Question 3 (whole page): One thing it gets wrong**

> For "H-E-B size 7 diapers" the hybrid ranks a size 6 pack at #5. It has 4 not-relevant results in its top 10, against 1 for keyword search. Exact attributes like size get blurred by the meaning score. It also fails on "seasoning for chicken fajitas", where both methods return seasoned chicken instead of seasoning.

Against the kit's expected answers, all three count as right.

What it found unclear, and what was done:

| Its note | Action |
|---|---|
| On the first screen, could not tell whether "counting only graded products" undercut the headline | Fixed: the hero now says first that the official score counts every ungraded product as wrong. |
| "Composite of four ranking metrics" never names them | Fixed: the evidence section gives the formula, with a link to `tamu25/evaluate.py`. |
| The worked example could read as keyword search returning junk | Fixed: the legend says "Not graded" means nobody labelled the product, not that it is a bad result. |
| "288 queries" and "never sent to this page" needed working out | Fixed in the limits. |
| Two hybrid results show keyword 0.86 yet sit outside the keyword top 10, whose last entry also shows 0.86 | Left. Read as a rounding tie; not checked against unrounded scores (**inferred**). |
| No bars or search times in the text | An artefact of a text-only review; both are on the page. |

The reviewer answered before those copy fixes, so the fixes themselves have not been read by a fresh reader.

## 7. Test changes

Decision 3A in the plan allowed strings and tab order to change as long as every behaviour stayed asserted.

`frontend/src/App.test.tsx`: 10 tests before, 20 now.

| Original test | What changed in its assertions |
|---|---|
| Controls named, Tab order | Third tab stop was the Debug switch; it is now the first example button. The switch is named "Show score breakdown". |
| Enter and Search both search | One request per search became two: `/search?q=pasta` and `/search?q=pasta&mode=bm25`. |
| Empty query makes no request | Unchanged. |
| Debug switch toggles score rows | `bm25 0.81 · semantic 0.74 · final 0.87` became `0.10 × keyword 0.81 + 0.90 × meaning 0.74 = 0.87`, plus a `keyword 0.81` line per keyword-only row. |
| Rerank shown when present | Now `… = 0.87, rerank 0.93`. |
| Dev query shows split and labels | Status became `Top 2 results for “gluten free pasta”, ranked in 142 ms on the server. This query is in the graded development set.` `label 3` became `Grade 3`; `label 0` became `Not relevant or not graded`. |
| Held-out query never shows a label | Status now ends `locked test set, so its grades stay hidden.`; no grade chip is rendered. |
| Query outside both splits | New status string; no grade chip. |
| Slow earlier response does not overwrite | The fetch stub is keyed by URL, because each search makes two requests. |
| Rejected query shows the message | Also asserts the empty state. |

New tests: the worked example and headline result show before any search with no request; an example button swaps the example with no request; keyword-only list beside the hybrid one; a server that ignores `mode` never has its hybrid list shown as keyword-only; whitespace-only query; slow search; no keyword overlap; network failure and recovery; HTML entities decoded as text; motion off for reduced-motion visitors.

`frontend/src/agent.test.tsx`: the control named "Debug" is now "Show score breakdown", "Motion" is added to the expected controls, and the result check reads the status line and grade chips.

`frontend/checks/evidence.test.ts`: new, 68 tests.

## 8. Deviations from the plan

- **Aceternity:** dropped at first over its licence's re-distribution clause, without asking; the owner overruled that and the components are in.
- **One more package:** `border-beam@1.4.1` (MIT), approved by the owner. Six packages were added in total: `tailwindcss`, `@tailwindcss/vite`, `motion`, `clsx`, `tailwind-merge`, `border-beam`.
- **Border Beam colour:** the package takes preset colours only, so the search box uses its `gold` preset, not the page's exact yellow and pink.
- **Subagents:** seven ran, not four, after the owner asked for coding to go to a cheaper model. One gate run was cut off by a usage limit and restarted.
- **Unslop pass:** run in polish mode. A full pass would have removed the effects the owner asked for. Only `styles.css` changed: spacing put on a 4px grid, score bars animate a transform and no longer `width`, grade chips and pipeline steps lost their pill shape, tabular figures added, one hover state added.
- **`frontend/checks/contrast.js`:** rewritten, because it pointed at the old page's selectors. It now checks every element that holds text, placeholders and control edges.
- **`frontend/src/utils.ts`:** the helper file first lived at `frontend/src/lib/utils.ts`, where the root `.gitignore` rule `lib/` (line 13, a Python packaging rule) hid it from git. A commit would have left it out and broken the build on a fresh clone. It was moved and its eight imports updated; type check, the 91 tests and the build were rerun afterwards. The Docker image was built before the move.
- **Gzip in the API:** `tamu25/api/app.py` now adds `GZipMiddleware` (`minimum_size=1000`, `compresslevel=6`), with one new test in `tests/test_api.py`. The owner approved it ("Yes, add gzip"). A follow-up fix registers `.woff2` as `font/woff2` in the same file (one `mimetypes.add_type` line) so the font is no longer gzipped; the same test covers it.
- **`.claude/launch.json`:** added to start the local servers for browser checks. It is untracked and should not be committed.

## 9. Not verified

- **Animation by eye (unknown):** the re-rank, typewriter and beams were checked for their final states. Much of the session ran with the browser pane hidden, which throttles animation. The card glow was triggered with a scripted pointer event, not a real hover.
- **The deployed service (unknown):** nothing here ran against Cloud Run. The new parameter is not live until a deploy.
- **A real reader (unknown):** the recruiter kit has not been run.
- **Hover states:** read from the stylesheet, not hovered in a browser.

## 10. Adjacent issues, listed and not fixed

- No favicon, so one console 404 (section 4).
- The multi step loader covers the whole page while a slow search runs. That is how the component is built.
- The four evidence cards are equal in size; the unslop skill would vary them.
- README "Frontend" section and `reports/frontend_screenshot.jpg` describe the old page.
- The API's `label: 0` still means both "graded not relevant" and "never graded"; the page words around it for live searches.
- The README's own example query, `gluten free pasta`, returns pasta salad, parmesan and tortelloni. That is a ranking issue.
