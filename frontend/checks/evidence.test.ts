import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
const load = (rel: string) => JSON.parse(readFileSync(resolve(root, rel), "utf-8"));

const sys2 = ["bm25", "hybrid"];
const cmp = ["diff", "ci_low", "ci_high"];
const required = [
  "catalog.products", "split.locked", "split.dev", "config.bm25_weight", "config.model",
  "holdout.n_queries", "holdout.resamples",
  ...["official", "judged"].flatMap((m) => [...sys2, ...cmp].map((s) => `holdout.${m}.${s}`)),
  ...["unjudged_top10", "ndcg10", "ap20", "p10", "r30"].flatMap((m) => sys2.map((s) => `holdout.${m}.${s}`)),
  "cv.n_queries", ...["bm25", "hybrid", ...cmp].map((s) => `cv.official.${s}`),
  ...["official", "judged", "unjudged_top10"].map((m) => `tried.baseline.${m}`),
  ...["rrf", "rerank"].flatMap((s) =>
    ["official", "judged", "unjudged_top10", ...cmp, "decision"].map((m) => `tried.${s}.${m}`)),
  "tried.rerank.judged_diff", "tried.rerank.judged_ci_low", "tried.rerank.judged_ci_high",
  ...["hybrid", "bm25"].flatMap((s) => ["p50", "p95"].map((p) => `latency.${s}.${p}`)),
  "latency.n_queries", "latency.logical_cpus", "latency.torch_threads",
];

type Fact = { value: unknown; source: string; path: (string | number)[]; op: string };
const facts: Record<string, Fact> = load("frontend/src/evidence.json").facts;

describe("evidence.json", () => {
  it("has exactly the required keys", () => {
    expect(Object.keys(facts).sort()).toEqual([...required].sort());
  });
  for (const [key, f] of Object.entries(facts)) {
    it(`${key} matches ${f.source}`, () => {
      let v = load(f.source);
      for (const p of f.path) v = v[p];
      const actual =
        f.op === "len" ? v.length : f.op === "sum_len" ? v.reduce((a: number, x: unknown[]) => a + x.length, 0) : v;
      expect(f.op).toMatch(/^(value|len|sum_len)$/);
      expect(actual).toStrictEqual(f.value);
    });
  }
});

describe("examples.json", () => {
  const ex = load("frontend/src/examples.json").examples;
  const locked: string[] = load("data/split_v1.json").locked;
  it("has the five examples in order", () => {
    expect(ex.map((e: any) => [e.id, e.role])).toEqual([
      ["s530", "lead"], ["s98", "meaning"], ["s4", "meaning"], ["s206", "keyword"], ["s435", "fail"],
    ]);
  });
  it("uses no locked query", () => {
    for (const e of ex) expect(locked).not.toContain(e.id);
  });
  for (const e of ex) {
    it(`${e.id} rows are well formed`, () => {
      for (const list of [e.hybrid, e.keyword]) {
        expect(list.map((r: any) => r.rank)).toEqual([1, 2, 3, 4, 5, 6, 7, 8, 9, 10]);
        for (const r of list) expect([0, 1, 2, 3, null]).toContain(r.grade);
      }
      for (const r of e.keyword) expect(r.semantic_score).toBeNull();
      for (const r of e.hybrid) expect(typeof r.semantic_score).toBe("number");
    });
  }
});
