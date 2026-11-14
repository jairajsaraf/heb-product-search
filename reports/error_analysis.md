# Phase 2: error analysis (230 dev queries)

Source: `scripts/error_analysis.py` → `reports/error_analysis.json` (versions, model revisions, sha256 of `cv_baseline.json` and `split_v1.json` in its `meta`).

- **Ranking analysed:** the Phase 1 tuned hybrid, out of fold. Each query is ranked with its own fold's choice; all five folds chose MiniLM with a BM25 weight of 0.10–0.15.
- **Check against Phase 1:** the script asserts that all 230 per-query composites equal `cv_baseline.json` exactly.
- **Locked queries:** none of the 58 were read.
  - An earlier draft cited Phase 0's score-spread spot check as evidence.
  - That check covered the first 5 train queries, 2 of which (s79, s319) are locked. It was score spreads only, no labels.
  - The citation is removed.
- **Labels:** confirmed = counted by the script; inferred = my reading of the worst 20. The product token counts in §4 and §5 are the exception: they come from a one-off command (not committed) that counts products whose `preprocess_text(create_product_text(p))` contains the token.

## 1. Where the missing relevant items are (confirmed)

This counts every labelled relevant item (label ≥ 1) that is not in the tuned top 10, over all 230 queries:

| Position of the missing item | Items | Share | Reachable by |
|---|---|---|---|
| Hybrid rank 11–30 | 1,252 | 56% | reranking the top 50 (helps nDCG@10, P@10, AP@20) |
| Hybrid rank 31–50 | 533 | 24% | reranking the top 50 (also helps R@30) |
| Beyond 50 in the hybrid, inside BM25-only top 50 | 44 | 2% | a fusion that gives BM25 more say (RRF) |
| Beyond 50 in the hybrid and BM25, inside semantic-only top 50 | 202 | 9% | a fusion that gives semantic *more* say; plain RRF pushes these down |
| Beyond 50 everywhere | 204 | 9% | none of the four candidates |

80% of what is missing already sits in the hybrid's top 50. The ranking's problem is mostly order, not recall.

The fusion-side items lean semantic, not BM25. A pure-semantic setting (BM25 weight 0) was in the Phase 1 grid, and no fold chose it.

## 2. Buckets (confirmed)

- **Text buckets** (brand, ingredient/allergen, negation, size) use the query text only.
- **Outcome buckets** (category confusion, label hole) use the ranking.
- **Rules:** fixed in the script before any outcome was read, and listed in `meta.rules`.
- **Overlap:** a query can be in several buckets.

| Bucket | n / 230 | In worst 20 | Mean composite (rest) | Judged-irrelevant in top 10 (rest) | Missing items: rerank-reachable / fusion-BM25 / fusion-semantic / unreachable |
|---|---|---|---|---|---|
| brand | 61 | 1 | 0.733 (0.655) | 3.80 (2.38) | 279 / 11 / 24 / 25 |
| ingredient/allergen | 41 | 4 | 0.701 (0.671) | 2.29 (2.86) | 319 / 5 / 17 / 18 |
| negation | 20 | 4 | 0.658 (0.678) | 2.40 (2.79) | 128 / 2 / 8 / 12 |
| size | 15 | 0 | 0.671 (0.676) | 3.07 (2.73) | 111 / 6 / 4 / 7 |
| category confusion (≥ 3 of top 10 in a level-2 category with no relevant item) | 18 | 4 | 0.594 (0.683) | 4.39 (2.62) | 84 / 3 / 24 / 11 |
| label hole (≥ 6 of top 10 unjudged) | 7 | 6 | 0.342 (0.686) | 0.00 (2.84) | 88 / 0 / 40 / 42 |
| none of the above | 110 | 7 | 0.659 (0.691) | 2.44 (3.05) | 1,031 / 24 / 103 / 112 |

The dev mean composite is 0.6759.

- **Brand queries do better than the rest** (0.733 vs 0.655).
  - Their top 10 holds only 0.62 wrong-brand products on average.
  - Their excess judged-irrelevant items are the right brand but the wrong product.
  - That gives no case for tuning the BM25 field boosts on brand grounds.
- **Ingredient/allergen and negation queries are not worse than the rest on judged-irrelevant items** (2.29 and 2.40, against 2.86 and 2.79 for the rest).
  - A filter is meant to remove judged-irrelevant products that violate the constraint, and these numbers show no excess of them to remove.
  - Negation queries score 0.02 below the rest on 20 queries. That's too few to act on.
- **Size has no candidate.** It isn't in the worst 20, and its numbers are close to the rest.
- **Category confusion is the clearest ranking failure.** It has the largest gap below the rest (−0.089) and the most judged-irrelevant items in the top 10.
  - 84 of its 122 missing items are rerank-reachable.
  - 27 are fusion-side. 24 of those are semantic-only, which plain RRF would push further down.
- **Label holes are an evaluation problem, not a ranking problem.**
  - Only 7 queries, but 6 of them are in the worst 20.
  - Their top 10 averages 6.6 unjudged items and no judged-irrelevant item.
  - For the 6 in the worst 20, official composite is 0.26–0.37 while judged-only is 0.57–0.77.
  - A change that gains mainly here gains by surfacing labelled products, so Phase 3 must report judged-only beside it, as the spec already says.

## 3. The worst 20, read by hand (inferred)

Rule buckets come from the script. "My reading" is my own classification after looking at each top 10 and the missing items (full lists in the appendix).

| Query | Official | Judged-only | Unjudged top 10 | Rule buckets | My reading |
|---|---|---|---|---|---|
| s244 citrus seasoned pork for grilling | 0.111 | 0.180 | 1 | – | flavour modifier ignored: seasoned pork, none citrus |
| s140 non-BPA canned soup | 0.219 | 0.268 | 1 | ingredient, negation | unclear: soups ranked, most labelled 0 |
| s435 seasoning for chicken fajitas | 0.244 | 0.244 | 0 | category | product type: returns seasoned chicken, wants seasoning |
| s565 eco-friendly caught fish | 0.260 | 0.623 | 6 | label hole | label hole: wild-caught fish, unjudged |
| s563 sustainable seafood options | 0.265 | 0.677 | 6 | label hole | label hole; "responsibly raised" items at semantic rank 1–3, BM25 rank 500+ |
| s550 sustainably sourced sushi | 0.279 | 0.332 | 3 | – | unclear: sushi ranked, most labelled 0 or 1 |
| s174 delicate texture fish | 0.287 | 0.592 | 7 | label hole | label hole |
| s117 spicy seasoning for chicken | 0.296 | 0.308 | 1 | – | product type: returns spicy chicken, wants seasoning |
| s185 minimally processed beef | 0.306 | 0.569 | 6 | label hole | label hole |
| s218 zero sugar added ice cream | 0.332 | 0.571 | 5 | ingredient, negation | product type: fruit bars and non-dairy dessert above ice cream; constraint itself met |
| s369 quick seafood dinner ideas | 0.333 | 0.561 | 5 | – | near label hole; best missing items at semantic rank 1–11, BM25 rank 300+ |
| s143 mild sweet fish | 0.339 | 0.586 | 6 | label hole | label hole |
| s434 no MSG spice blends | 0.367 | 0.767 | 6 | ingredient, negation, label hole | label hole |
| s478 mild flavor white fish | 0.379 | 0.522 | 5 | – | near label hole |
| s188 cheese for tacos | 0.384 | 0.537 | 2 | category | product type: taco meat, wants cheese |
| s39 southeastern style sushi rolls | 0.393 | 0.518 | 4 | – | regional modifier (Cajun, Louisiana) only partly matched |
| s5 H-E-B mayocoba beans for chili | 0.397 | 0.427 | 0 | brand, category | product type: canned chili, wants beans |
| s119 lemon garlic spice rub | 0.398 | 0.592 | 2 | category | product type: rubbed pork, wants a rub |
| s238 gluten-free vegetable sauce | 0.399 | 0.436 | 1 | ingredient, negation | unclear: cooking sauces ranked, most labelled 0 |
| s33 ready to eat sushi with wasabi and soy sauce | 0.410 | 0.547 | 3 | – | mild; mostly ordering |

The tallies below are my own reading and overlap.

| Failure (my reading) | Worst-20 queries |
|---|---|
| Product type: the "X for Y" head noun is lost and Y's products rank first | 7 (s435, s117, s188, s5, s119, s218, and in part s244) |
| Label hole or near label hole (≥ 5 unjudged) | 9 (s565, s563, s174, s185, s143, s434, s369, s478, s218) |
| Attribute constraint, cause unclear from the top 10 | 3 (s140, s238, s550) |
| Modifier only partly matched (citrus, southeastern) | 2 (s244, s39) |

For the product-type cases, take all 75 missing relevant items of those 7 queries (`per_query[].reach`): 46 are at hybrid rank 11–30 and 13 at 31–50, so 79% are rerank-reachable. 11 are semantic-only and 5 unreachable. That share is the same as the dev-wide 80%; these queries are not unusually close. What marks them out is that the miss is a product-type ordering error inside the top 50. I infer that a model reading the query and product together, a cross-encoder, is the candidate built for it, because it can weigh "seasoning" against "chicken". BM25 and bi-encoder scores treat the query as a bag of terms or one vector.

## 4. Candidates against the evidence

| Candidate | Evidence for | Evidence against | Verdict |
|---|---|---|---|
| Cross-encoder rerank of the top 50 | 1,785 of 2,235 missing items (80%) inside the top 50. Product-type failures, the main fixable worst-20 pattern, are ordering errors inside the top 50. | Needs a model download (approval). Adds latency on CPU. Gains on label-hole queries would be scored by unjudged items, so judged-only must be watched. | **Recommend** |
| RRF fusion | 44 items (2%) are in BM25's top 50 but beyond the hybrid's 50. | 202 fusion-side items (9%) are semantic-only, and rank-based fusion with equal weights would push them down. A weighted RRF tuned in folds would be a re-parameterisation of the weight Phase 1 already tuned. | Not recommended |
| BM25 field-boost tuning | none found | Brand queries already beat the rest by 0.078 and hold 0.62 wrong-brand items per top 10. | Not recommended |
| Negation/allergen filter | negation queries 0.02 below the rest (n = 20) | Their judged-irrelevant rate is lower than the rest's, so there is little to filter. | Not recommended |

**Recommendation:** one change, the cross-encoder rerank of the top 50. The spec allows up to two. None of the other three has bucket evidence behind it, so I'm not proposing a second to fill the slot.
- **Phase 3:** test it against the tuned baseline under the keep rule, with judged-only and the unjudged rate beside it.
- **Reranker download:** Phase 3 needs your approval first. I'll name the model and size when asking.

Context, not evidence: the constraint queries I could not explain (s140, s238, s434) are not missing their terms from the index. BM25 already sees them (token `non-bpa` in 47 products, `msg` in 33, `gluten` in 321, `gluten-free` in 100).

## 5. Findings outside the candidate list (listed, not acted on)

- **`create_product_text` (`baseline_ranker.py`) drops `safety_warning`.** That field holds "Contains: …" allergen lists. Indexing it would be a new field, not "tuning existing boosts", so it isn't counted as a candidate. Note that the allergen bucket shows no excess of judged-irrelevant results.
- **`preprocess_text` keeps hyphenated words as single tokens.** So `gluten-free` (100 products) and `gluten` (321) are separate terms.
  - The 9 hyphenated negation queries average 0.631, against 0.679 for the other 11.
  - That's too few to act on, and it's not a spec candidate.
- **The catalog `brand` field holds 23 descriptors** ("Fresh", "Natural", "Wild", "Frozen", "USDA", …). They are excluded in the brand rule (`meta.rules.not_brands`). Data quality only.
- **Product titles contain HTML entities** (`&ndash;`, `&nbsp;`, `&eacute;`). `preprocess_text` turns them into tokens like `nbsp` and `eacute`.
- **Label holes cluster in broad, attribute-style queries** (sustainable, delicate texture, mild sweet). Labels per query are capped at 20–40, so these queries have more plausible products than judgements.

## Appendix: worst 20 top 10s and missing items

Rendered from `reports/error_analysis.json` (`worst20`). Label `-` = unjudged. The MISS lines are the 3 highest-labelled relevant items outside the top 10, each with its hybrid (h), BM25-only (b) and semantic-only (s) rank.


### s244 "citrus seasoned pork for grilling"

official 0.111 · judged-only 0.180 · BM25 0.000 · relevant labelled 7 · fold 0 (minilm, w=0.15)

| # | Label | Title | Brand | Category |
|---|---|---|---|---|
| 1 | 0 | Hill Country Fare Pork Riblets with Bar-B-Q Seasoning | Hill Country Fare | Meat |
| 2 | 0 | H-E-B Simply Seasoned Boneless Boston Butt Pork Steaks, Extra Thick Cut &ndash; Sweet TX Heat | H-E-B | Meat |
| 3 | 0 | H-E-B Natural Seasoned St. Louis-Style Pork Finger Ribs &ndash; Sweet TX Heat | H-E-B | Meat |
| 4 | 0 | H-E-B Boneless Center Loin Pork Chops, Extra Thick Cut | H-E-B | Meat |
| 5 | 0 | H-E-B Seasoned Pork for Fajitas, Value Pack | H-E-B | Meat |
| 6 | 0 | H-E-B Seasoned Pork Fajitas | H-E-B | Meat |
| 7 | 0 | H-E-B Simply Seasoned Texas Style St. Louis Pork Spareribs | H-E-B | Meat |
| 8 | 0 | H-E-B Natural Boneless Butterflied Center Loin Pork Chops, Thick Cut | H-E-B | Meat |
| 9 | 0 | H-E-B Simply Seasoned Hatch Green Chile Seasoned Diced Pork | H-E-B | Meat |
| 10 | - | H-E-B Mi Tienda Seasoned Country-Style Bone-In Pork Ribs - Achiote | H-E-B Mi Tienda | Meat |

- MISS label 3 · h11 b88 s2 · H-E-B Seasoned Pork Loin Filet - Lemon Pepper
- MISS label 3 · h24 b46 s27 · H-E-B Mi Tienda Seasoned Boneless Ribeye Pork Chops – Orange Pepper
- MISS label 3 · h26 b65 s22 · H-E-B Mi Tienda Seasoned Bone-in Pork Butt Steaks – Orange Pepper – Value Pack

### s140 "non-BPA canned soup"

official 0.219 · judged-only 0.268 · BM25 0.149 · relevant labelled 20 · fold 3 (minilm, w=0.1)

| # | Label | Title | Brand | Category |
|---|---|---|---|---|
| 1 | 0 | Hill Country Fare Hearty Chicken Noodle Soup | Hill Country Fare | Soups & chili |
| 2 | 3 | Hill Country Fare Tomato Condensed Soup | Hill Country Fare | Soups & chili |
| 3 | 0 | H-E-B Tomato Condensed Soup | H-E-B | Soups & chili |
| 4 | 0 | H-E-B Reduced Sodium Chicken & Rice Condensed Soup | H-E-B | Soups & chili |
| 5 | 0 | H-E-B Texas-Inspired Beef Taco Condensed Soup | H-E-B | Soups & chili |
| 6 | 3 | H-E-B Chicken & Rice Condensed Soup - Family Size | H-E-B | Soups & chili |
| 7 | - | Hill Country Fare 98% Fat-Free Cream of Chicken Condensed Soup | Hill Country Fare | Soups & chili |
| 8 | 0 | H-E-B Chunk White Albacore Tuna in Water | H-E-B | Canned & dried food |
| 9 | 0 | H-E-B Beef Consomme Condensed Soup | H-E-B | Soups & chili |
| 10 | 0 | H-E-B Reduced Sodium Chicken Noodle Condensed Soup | H-E-B | Soups & chili |

- MISS label 3 · h11 b31 s9 · H-E-B Chicken Noodle Condensed Soup
- MISS label 3 · h16 b60 s5 · H-E-B Organics Southwest Style Black Bean Soup
- MISS label 3 · h21 b39 s16 · H-E-B Texas-Inspired Cream of Poblano Condensed Soup

### s435 "seasoning for chicken fajitas"

official 0.244 · judged-only 0.244 · BM25 0.138 · relevant labelled 10 · fold 0 (minilm, w=0.15)

| # | Label | Title | Brand | Category |
|---|---|---|---|---|
| 1 | 0 | H-E-B Seasoned Chicken Breast Fajitas | H-E-B | Meat |
| 2 | 0 | H-E-B Seasoned Spicy Boneless Skinless Chicken Thighs for Fajitas | H-E-B | Meat |
| 3 | 0 | H-E-B Seasoned Boneless Skinless Chicken Thighs for Fajitas | H-E-B | Meat |
| 4 | 0 | H-E-B Seasoned Chicken Thighs for Fajitas | H-E-B | Meat |
| 5 | 0 | H-E-B Meat Market&nbsp;Chicken Fajita Kit - Pan Saut&eacute; | H-E-B | Meat |
| 6 | 2 | H-E-B Mi Tienda Beef Fajita Seasoning | H-E-B Mi Tienda | Spices & seasonings |
| 7 | 0 | Meal Simple by H-E-B Chicken Thigh Fajitas | Meal Simple by H-E-B | Ready meals & snacks |
| 8 | 0 | H-E-B Seasoned Chicken Breast for Fajitas | H-E-B | Meat |
| 9 | 0 | H-E-B Fully Cooked Frozen Seasoned Chicken Thigh Fajitas | H-E-B | Meat |
| 10 | 0 | H-E-B Mi Tienda Seasoned Boneless Skinless Chicken Leg Quarters for Fajitas | H-E-B Mi Tienda | Meat |

- MISS label 3 · h13 b14 s11 · Hill Country Fare Chicken Fajita Spice Blend
- MISS label 3 · h15 b15 s16 · H-E-B Mi Tienda Red Fajita Seasoning
- MISS label 3 · h23 b43 s8 · H-E-B Texas Originals Chicken Fajita Seasoning Spice Blend - Texas-Size Pack

### s565 "eco-friendly caught fish"

official 0.260 · judged-only 0.623 · BM25 0.174 · relevant labelled 35 · fold 1 (minilm, w=0.1)

| # | Label | Title | Brand | Category |
|---|---|---|---|---|
| 1 | 3 | H-E-B Wild Caught Atlantic Pollock Fillet | H-E-B | Seafood |
| 2 | - | H-E-B Wild Caught Fresh Grouper Fillet | H-E-B | Seafood |
| 3 | - | H-E-B Wild Caught Fresh East Coast Flounder Fillet | H-E-B | Seafood |
| 4 | - | H-E-B Wild Caught Southern Flounder Fillet | H-E-B | Seafood |
| 5 | - | H-E-B Wild Caught Fresh Haddock Fillet | H-E-B | Seafood |
| 6 | - | H-E-B Wild Caught Fresh Monkfish Fillet | H-E-B | Seafood |
| 7 | - | H-E-B Wild Caught Ocean Perch Fillet | H-E-B | Seafood |
| 8 | 3 | H-E-B Wild Caught Fresh Alaska Coho Salmon Fillet | H-E-B | Seafood |
| 9 | 3 | H-E-B Wild Caught Whole Freshwater Drum | H-E-B | Seafood |
| 10 | - | H-E-B Wild Caught Live Steamer Clams | H-E-B | Seafood |

- MISS label 3 · h12 b15 s14 · H-E-B Wild Caught Fresh Atlantic Cod Loin
- MISS label 3 · h14 b29 s11 · Frozen Smoked Whitefish Cuts, Wild Caught
- MISS label 3 · h15 b19 s15 · Previously Frozen Malabar Snapper Portion, Wild Caught

### s563 "sustainable seafood options"

official 0.265 · judged-only 0.677 · BM25 0.030 · relevant labelled 29 · fold 3 (minilm, w=0.1)

| # | Label | Title | Brand | Category |
|---|---|---|---|---|
| 1 | - | H-E-B Seasoned Wild Caught Chunk Light Tuna Pouch - Cajun-Style | H-E-B | Canned & dried food |
| 2 | 3 | H-E-B Wild Caught Shell-On Super Colossal Gulf Brown Raw Shrimp, 9 - 12 ct/lb | H-E-B | Seafood |
| 3 | - | H-E-B Wild Caught Shell-On Super Colossal Key West Pink Raw Shrimp, 9 - 12 ct/lb | H-E-B | Seafood |
| 4 | - | H-E-B Wild Caught Chunk White Albacore Tuna in Spring Water Pouch | H-E-B | Canned & dried food |
| 5 | - | H-E-B Seasoned Wild Caught Chunk Light Tuna Pouch - Thai-Style Green Curry | H-E-B | Canned & dried food |
| 6 | - | H-E-B Wild Caught Cold Water Raw Lobster Tail | H-E-B | Seafood |
| 7 | - | H-E-B Wild Caught Cold Water Frozen Lobster Tails, 3 - 4 oz | H-E-B | Seafood |
| 8 | 3 | H-E-B Wild Caught Fresh Alaska Sockeye Salmon Fillet | H-E-B | Seafood |
| 9 | 2 | Hilton's Pacific Oysters Shucked | Hilton's | Seafood |
| 10 | - | H-E-B Wild Caught Cooked & Scored Lobster Claws | H-E-B | Seafood |

- MISS label 3 · h11 b523 s1 · H-E-B Responsibly Raised Fresh Whole Tilapia – Texas-Size Pack
- MISS label 3 · h13 b639 s2 · H-E-B Responsibly Raised Fresh Whole Scored Tilapia - Texas-Size Pack
- MISS label 3 · h14 b578 s3 · H-E-B Responsibly Raised Fresh Whole Scored Tilapia

### s550 "sustainably sourced sushi"

official 0.279 · judged-only 0.332 · BM25 0.209 · relevant labelled 11 · fold 4 (minilm, w=0.1)

| # | Label | Title | Brand | Category |
|---|---|---|---|---|
| 1 | 1 | H-E-B Sushiya Kosher Vegetarian Roll | H-E-B Sushiya | Ready meals & snacks |
| 2 | 0 | H-E-B Sushiya Salmon Avocado Sushi Roll | H-E-B Sushiya | Ready meals & snacks |
| 3 | - | H-E-B Sushiya Kosher Maki Roll - Avocado | H-E-B Sushiya | Ready meals & snacks |
| 4 | 1 | H-E-B Sushiya Salmon Nigiri Sushi | H-E-B Sushiya | Ready meals & snacks |
| 5 | - | H-E-B Sushiya Tokyo Sushi Combo Pack | H-E-B Sushiya | Ready meals & snacks |
| 6 | - | H-E-B Sushiya Moonlight Sushi Combo Pack | H-E-B Sushiya | Ready meals & snacks |
| 7 | 0 | H-E-B Sushiya California Sushi Roll Value Pack | H-E-B Sushiya | Ready meals & snacks |
| 8 | 0 | H-E-B Sushiya Tuna Avocado Sushi Roll | H-E-B Sushiya | Ready meals & snacks |
| 9 | 0 | H-E-B Sushiya Louisiana Sushi Roll | H-E-B Sushiya | Ready meals & snacks |
| 10 | 0 | H-E-B Sushiya Spicy California Sushi Roll – Kosher | H-E-B Sushiya | Ready meals & snacks |

- MISS label 3 · h17 b8 s51 · H-E-B Sushiya Salmon Sashimi
- MISS label 3 · h24 b34 s34 · H-E-B California Sushi Roll – Kosher
- MISS label 3 · h25 b28 s38 · H-E-B Sushiya Ocean Trio Sushi Roll Combo Pack

### s174 "delicate texture fish"

official 0.287 · judged-only 0.592 · BM25 0.176 · relevant labelled 31 · fold 2 (minilm, w=0.15)

| # | Label | Title | Brand | Category |
|---|---|---|---|---|
| 1 | 3 | Haddock Fillet | Haddock | Seafood |
| 2 | 3 | H-E-B Wild Caught Fresh Alaska Coho Salmon Fillet | H-E-B | Seafood |
| 3 | - | H-E-B Fish Market Fresh Jumbo Rainbow Trout Fillet | H-E-B | Seafood |
| 4 | - | H-E-B Fish Market Fresh Rainbow Trout Fillet | H-E-B | Seafood |
| 5 | - | H-E-B Wild Caught Atlantic Pollock Fillet | H-E-B | Seafood |
| 6 | 3 | H-E-B Wild Caught Chilean Seabass Loin Fillet | H-E-B | Seafood |
| 7 | - | Fresh Natural Tilapia Fillet&nbsp; | Fresh | Seafood |
| 8 | - | H-E-B Responsibly Raised Fresh Live Littleneck Clams | H-E-B | Seafood |
| 9 | - | H-E-B Wild Caught Alaskan Sockeye Center Cut Salmon | H-E-B | Seafood |
| 10 | - | H-E-B Fish Market Fresh Whole Rainbow Trout | H-E-B | Seafood |

- MISS label 3 · h19 b43 s13 · H-E-B Responsibly Raised Fresh Whole Scored Tilapia
- MISS label 3 · h21 b33 s30 · H-E-B Wild Caught Fresh West Coast Flounder Fillet
- MISS label 3 · h26 b39 s31 · H-E-B Responsibly Raised Fresh Whole Tilapia – Texas-Size Pack

### s117 "spicy seasoning for chicken"

official 0.296 · judged-only 0.308 · BM25 0.140 · relevant labelled 22 · fold 4 (minilm, w=0.1)

| # | Label | Title | Brand | Category |
|---|---|---|---|---|
| 1 | 0 | H-E-B Fully Cooked Spicy Breaded Chicken Breast Patties | H-E-B | Meat |
| 2 | 0 | H-E-B Fully Cooked Frozen Spicy Popcorn Chicken | H-E-B | Meat |
| 3 | 0 | H-E-B Seasoned Spicy Boneless Skinless Chicken Thighs for Fajitas | H-E-B | Meat |
| 4 | 3 | H-E-B Poultry Seasoning | H-E-B | Spices & seasonings |
| 5 | 0 | Hill Country Fare Fully Cooked Frozen Spicy Chicken Sandwich | Hill Country Fare | Meals & sides |
| 6 | 0 | Higher Harvest by H-E-B Lightly Breaded Spicy Chicken Breast Bites - 16g Protein | Higher Harvest by H-E-B | Meat |
| 7 | 2 | H-E-B Fish Market Spicy Asian Pepper Seasoning Spice Blend | H-E-B | Spices & seasonings |
| 8 | - | Hill Country Fare Orange Pepper Seasoned Chicken Leg Quarters | Hill Country Fare | Meat |
| 9 | 0 | H-E-B Mi Tienda Seasoned Diced Chicken Thighs for Tacos - Pollo Chile Verde | H-E-B Mi Tienda | Meat |
| 10 | 0 | H-E-B Simply Seasoned Lemon Pepper Chicken Tenderloins | H-E-B | Meat |

- MISS label 3 · h13 b20 s20 · H-E-B Texas Originals Chicken Fajita Seasoning Spice Blend - Texas-Size Pack
- MISS label 3 · h14 b34 s19 · Hill Country Fare Chicken Fajita Spice Blend
- MISS label 3 · h24 b87 s25 · H-E-B Mi Tienda Orange Pepper Seasoning - Value Size

### s185 "minimally processed beef"

official 0.306 · judged-only 0.569 · BM25 0.140 · relevant labelled 37 · fold 4 (minilm, w=0.1)

| # | Label | Title | Brand | Category |
|---|---|---|---|---|
| 1 | 3 | H-E-B Beef Chuck Steak Thin USDA Select | H-E-B | Meat |
| 2 | - | H-E-B Butterflied Beef Sirloin Fajitas | H-E-B | Meat |
| 3 | 3 | H-E-B Beef Chuck Roast Boneless Whole, USDA Select, Gold Ribbon | H-E-B | Meat |
| 4 | - | H-E-B Beef Shoulder Roast Boneless Whole, USDA Select, Gold Ribbon | H-E-B | Meat |
| 5 | - | H-E-B Beef New York Strip Steak Bone-In, USDA Select | H-E-B | Meat |
| 6 | - | H-E-B Beef Top Sirloin Steak Value Pack, USDA Select&nbsp; | H-E-B | Meat |
| 7 | 3 | H-E-B Stir Fry Beef - USDA Select | H-E-B | Meat |
| 8 | 3 | H-E-B Beef Eye of Round Steak Thin, USDA Select | H-E-B | Meat |
| 9 | - | H-E-B Beef Chuck Blade Steak Bone-In Value Pack, USDA Select | H-E-B | Meat |
| 10 | - | Fresh Beef Top Sirloin Filet | Fresh | Meat |

- MISS label 3 · h11 b11 s29 · H-E-B Beef Eye of Round  Steak Tenderized, USDA Select
- MISS label 3 · h12 b15 s23 · H-E-B Beef Boneless Small End Ribeye Roast, 4 Ribs, USDA Select
- MISS label 3 · h26 b146 s1 · H-E-B Grass Fed & Finished Beef Inside Skirt Steak

### s218 "zero sugar added ice cream"

official 0.332 · judged-only 0.571 · BM25 0.389 · relevant labelled 9 · fold 3 (minilm, w=0.1)

| # | Label | Title | Brand | Category |
|---|---|---|---|---|
| 1 | 0 | H-E-B Zero Sugar Added Frozen Fruit Bars - Strawberry | H-E-B | Ice cream & treats |
| 2 | - | Higher Harvest by H-E-B Zero Sugar Added Non-Dairy Frozen Dessert – Rich Dark Chocolate | Higher Harvest by H-E-B | Ice cream & treats |
| 3 | - | Higher Harvest by H-E-B Zero Sugar Added Non-Dairy Frozen Dessert - Minty Choco Chip | Higher Harvest by H-E-B | Ice cream & treats |
| 4 | - | Higher Harvest by H-E-B Zero Sugar Added Non-Dairy Frozen Dessert – Caramel Sea Salt Choco Chip | Higher Harvest by H-E-B | Ice cream & treats |
| 5 | 3 | H-E-B Creamy Creations No Sugar Added Light Ice Cream - Vanilla | H-E-B | Ice cream & treats |
| 6 | - | Higher Harvest by H-E-B Zero Sugar Added Non-Dairy Frozen Dessert - Buttery Pecan | Higher Harvest by H-E-B | Ice cream & treats |
| 7 | 3 | H-E-B Creamy Creations No Sugar Added Light Ice Cream - Peanut Butter Cup | H-E-B | Ice cream & treats |
| 8 | 0 | H-E-B Mootopia 10g Protein Lactose Free Light Ice Cream - Rocky Road | H-E-B | Ice cream & treats |
| 9 | 0 | H-E-B Mootopia 9g Protein Lactose Free Light Ice Cream - Mint Chocolate Chip | H-E-B | Ice cream & treats |
| 10 | - | H-E-B Mootopia 10g Protein Lactose Free Light Ice Cream - Chocolate | H-E-B | Ice cream & treats |

- MISS label 3 · h11 b9 s23 · H-E-B Creamy Creations No Sugar Added Light Ice Cream - Intense Chocolate
- MISS label 3 · h12 b8 s27 · H-E-B Creamy Creations No Sugar Added Light Ice Cream - Butter Pecan
- MISS label 3 · h14 b11 s18 · H-E-B Mootopia 9g Protein Lactose Free Light Ice Cream - Cookies & Cream

### s369 "quick seafood dinner ideas"

official 0.333 · judged-only 0.561 · BM25 0.131 · relevant labelled 38 · fold 0 (minilm, w=0.15)

| # | Label | Title | Brand | Category |
|---|---|---|---|---|
| 1 | 2 | H-E-B Fish Market Shrimp - Garlic Parmesan Sauce | H-E-B | Seafood |
| 2 | 2 | H-E-B Fish Market Lemon Pepper Seasoned Swordfish Steak - Garlic Butter | H-E-B | Seafood |
| 3 | - | H-E-B Fish Market Fresh Center Cut Atlantic Salmon | H-E-B | Seafood |
| 4 | 3 | H-E-B Fish Market Salmon & Crawfish Burger Patties - Creole | H-E-B | Seafood |
| 5 | 3 | Meal Simple by H-E-B Lobster & Crab Stuffed Atlantic Salmon Pinwheels | Meal Simple by H-E-B | Ready meals & snacks |
| 6 | - | H-E-B Fish Market Atlantic Salmon Burger Patties | H-E-B | Seafood |
| 7 | - | H-E-B Fish Market Easy Peel Deveined Extra Large Raw Shrimp, 26 - 30 ct/lb | H-E-B | Seafood |
| 8 | - | H-E-B Wild Caught Fresh Atlantic Cod Loin | H-E-B | Seafood |
| 9 | 3 | H-E-B Fish Market Shrimp - Honey Garlic Sauce | H-E-B | Seafood |
| 10 | - | H-E-B Fish Market Salmon Meatballs - Pesto | H-E-B | Seafood |

- MISS label 3 · h13 b532 s1 · Meal Simple by H-E-B Grilled Salmon & Lemon Garlic Pasta Bowl
- MISS label 3 · h14 b303 s4 · Meal Simple by H-E-B Seafood Rangoon Stuffed Salmon
- MISS label 3 · h22 b332 s11 · Meal Simple by H-E-B Atlantic Salmon Portions - Garlic Butter

### s143 "mild sweet fish"

official 0.339 · judged-only 0.586 · BM25 0.132 · relevant labelled 30 · fold 2 (minilm, w=0.15)

| # | Label | Title | Brand | Category |
|---|---|---|---|---|
| 1 | 3 | H-E-B Wild Caught Fresh Atlantic Cod Loin | H-E-B | Seafood |
| 2 | - | H-E-B Wild Caught Fresh Dover Sole Fillet | H-E-B | Seafood |
| 3 | 3 | Fresh Responsibly Farmed Whole Striped Bass | Fresh | Seafood |
| 4 | - | H-E-B Whole Fluke Flounder | H-E-B | Seafood |
| 5 | 3 | Previously Frozen Malabar Snapper Portion, Wild Caught | Previously Frozen | Seafood |
| 6 | - | Fresh Natural Tilapia Fillet&nbsp; | Fresh | Seafood |
| 7 | 2 | H-E-B Fish Market Fresh Whole Golden Trout | H-E-B | Seafood |
| 8 | - | Fresh Ocean Perch Fillet | Fresh | Seafood |
| 9 | - | H-E-B Responsibly Raised Fresh Whole Tilapia | H-E-B | Seafood |
| 10 | - | H-E-B Wild Caught Rockfish Fillet | H-E-B | Seafood |

- MISS label 3 · h12 b28 s16 · H-E-B Wild Caught Chilean Sea Bass Fillet
- MISS label 3 · h21 b67 s6 · H-E-B Responsibly Raised Fresh Whole Scored Tilapia
- MISS label 3 · h27 b23 s83 · H-E-B Fish Market Fresh Whole Rainbow Trout

### s434 "no MSG spice blends"

official 0.367 · judged-only 0.767 · BM25 0.313 · relevant labelled 20 · fold 4 (minilm, w=0.1)

| # | Label | Title | Brand | Category |
|---|---|---|---|---|
| 1 | 3 | Hill Country Fare Chicken Fajita Spice Blend | Hill Country Fare | Spices & seasonings |
| 2 | - | H-E-B Italian Seasoning – Texas-Size Pack | H-E-B | Spices & seasonings |
| 3 | 3 | H-E-B Lemon Pepper Spice Blend | H-E-B | Spices & seasonings |
| 4 | - | Hill Country Fare Lemon Pepper - Texas-Size Pack | Hill Country Fare | Spices & seasonings |
| 5 | - | Hill Country Fare Lemon Pepper | Hill Country Fare | Spices & seasonings |
| 6 | - | Hill Country Fare Ground Nutmeg | Hill Country Fare | Spices & seasonings |
| 7 | - | Hill Country Fare Fajita Spice | Hill Country Fare | Spices & seasonings |
| 8 | 3 | H-E-B Bagel Not Included Spice Blend - Everything + Citrus Sriracha | H-E-B | Spices & seasonings |
| 9 | - | H-E-B Texas Originals Rib Rub Coarse Seasoning Spice Blend | H-E-B | Spices & seasonings |
| 10 | - | Hill Country Fare Orange Pepper Seasoned Chicken Leg Quarters | Hill Country Fare | Meat |

- MISS label 3 · h12 b70 s4 · Central Market Ras El Hanout Spice Blend
- MISS label 3 · h14 b64 s5 · Central Market Greek Style Spice Blend
- MISS label 3 · h17 b54 s11 · H-E-B Garlic Pepper Spice Blend

### s478 "mild flavor white fish"

official 0.379 · judged-only 0.522 · BM25 0.289 · relevant labelled 24 · fold 2 (minilm, w=0.15)

| # | Label | Title | Brand | Category |
|---|---|---|---|---|
| 1 | 3 | H-E-B Wild Caught Fresh Atlantic Cod Loin | H-E-B | Seafood |
| 2 | 3 | H-E-B Whole Fluke Flounder | H-E-B | Seafood |
| 3 | - | H-E-B Wild Caught Atlantic Pollock Fillet | H-E-B | Seafood |
| 4 | 2 | H-E-B Fish Market Fresh Whole Golden Trout | H-E-B | Seafood |
| 5 | 0 | H-E-B Fish Market Fresh Whole Red Rainbow Trout - Texas-Size Pack | H-E-B | Seafood |
| 6 | - | H-E-B Wild Caught Fresh Dover Sole Fillet | H-E-B | Seafood |
| 7 | - | H-E-B Fish Market Fresh Rainbow Trout Fillets - Texas-Size Pack | H-E-B | Seafood |
| 8 | 3 | Whole Rainbow Trout | Whole | Seafood |
| 9 | - | H-E-B Fish Market Fresh Jumbo Rainbow Trout Fillet | H-E-B | Seafood |
| 10 | - | H-E-B Fish Market Fresh Rainbow Trout Fillet | H-E-B | Seafood |

- MISS label 3 · h15 b24 s33 · H-E-B Wild Caught Chilean Sea Bass Fillet
- MISS label 3 · h17 b59 s12 · H-E-B Fish Market Fresh Catfish Fillet
- MISS label 3 · h19 b15 s65 · H-E-B Fish Market Fresh Catfish Nuggets

### s188 "cheese for tacos"

official 0.384 · judged-only 0.537 · BM25 0.256 · relevant labelled 14 · fold 2 (minilm, w=0.15)

| # | Label | Title | Brand | Category |
|---|---|---|---|---|
| 1 | 3 | H-E-B Queso Oaxaca Mexican-Style Mozzarella Cheese - Texas-Size Pack | H-E-B | Cheese |
| 2 | 0 | H-E-B Fully Cooked Seasoned Ground Beef for Tacos | H-E-B | Ready meals & snacks |
| 3 | 0 | H-E-B Mi Tienda Mexican-Style Pork for Tacos - Carne Al Pastor | H-E-B Mi Tienda | Meat |
| 4 | - | H-E-B Mi Tienda Seasoned Diced Chicken Thighs for Tacos - Pollo Guajillo | H-E-B Mi Tienda | Meat |
| 5 | - | H-E-B Mi Tienda Seasoned Diced Chicken Thighs for Tacos - Pollo Chile Verde | H-E-B Mi Tienda | Meat |
| 6 | 2 | Meal Simple by H-E-B Chorizo Queso Dip | Meal Simple by H-E-B | Ready meals & snacks |
| 7 | - | H-E-B Deli Post Oak Smoked Havarti Shredded Cheese | H-E-B | Cheese |
| 8 | 0 | H-E-B Mi Tienda Jalapeno Oaxaca Cheese Tamales de Jalapeno y Queso | H-E-B Mi Tienda | Ready meals & snacks |
| 9 | 0 | Meal Simple by H-E-B Mexican Street Corn Salad | Meal Simple by H-E-B | Ready meals & snacks |
| 10 | 3 | H-E-B Mi Tienda Sliced Queso Quesadilla Mexican-Style Melting Cheese | H-E-B Mi Tienda | Cheese |

- MISS label 3 · h12 b63 s15 · H-E-B Mi Tienda Queso Cotija Grated Cheese
- MISS label 3 · h15 b25 s31 · H-E-B Natural Shredded Cheese, Thick Cut - Cowboy Kick
- MISS label 3 · h22 b190 s13 · H-E-B Queso Asadero Mexican-Style Provolone Cheese

### s39 "southeastern style sushi rolls"

official 0.393 · judged-only 0.518 · BM25 0.330 · relevant labelled 19 · fold 2 (minilm, w=0.15)

| # | Label | Title | Brand | Category |
|---|---|---|---|---|
| 1 | 3 | H-E-B Sushiya Cajun California Sushi Roll | H-E-B Sushiya | Ready meals & snacks |
| 2 | 0 | H-E-B Sushiya Picante Roll | H-E-B Sushiya | Ready meals & snacks |
| 3 | - | H-E-B Sushiya North Texas Sushi Roll Combo Pack | H-E-B Sushiya | Ready meals & snacks |
| 4 | 2 | H-E-B Sushiya Austin Sushi Roll | H-E-B Sushiya | Ready meals & snacks |
| 5 | - | H-E-B Sushiya Temptation Sushi Roll | H-E-B Sushiya | Ready meals & snacks |
| 6 | - | H-E-B Sushiya Crunchy Temptation Sushi Roll | H-E-B Sushiya | Ready meals & snacks |
| 7 | 2 | H-E-B California Sushi Roll – Kosher | H-E-B | Ready meals & snacks |
| 8 | 2 | H-E-B Sushiya South Texas Sushi Roll Combo Pack | H-E-B Sushiya | Ready meals & snacks |
| 9 | 0 | H-E-B Sushiya Musubi Roll | H-E-B Sushiya | Ready meals & snacks |
| 10 | - | H-E-B Sushiya Texas Trio Sushi Combo Pack | H-E-B Sushiya | Ready meals & snacks |

- MISS label 3 · h14 b98 s5 · H-E-B Sushiya Cajun Combo Sushi Roll Combo Pack
- MISS label 3 · h24 b61 s16 · H-E-B Sushiya Louisiana Sushi Roll
- MISS label 3 · h94 b132 s80 · H-E-B Sushiya Gulf Coast Sushi Roll

### s5 "H-E-B mayocoba beans for chili"

official 0.397 · judged-only 0.427 · BM25 0.334 · relevant labelled 12 · fold 2 (minilm, w=0.15)

| # | Label | Title | Brand | Category |
|---|---|---|---|---|
| 1 | 3 | H-E-B Mayocoba Beans | H-E-B | Canned & dried food |
| 2 | 0 | H-E-B Texas Style Chili - No Beans - Value Size | H-E-B | Soups & chili |
| 3 | 0 | H-E-B Texas Style Chili with Beans - Value Pack | H-E-B | Soups & chili |
| 4 | 0 | H-E-B Texas Style Chili with Beans | H-E-B | Soups & chili |
| 5 | 0 | H-E-B Texas Style Chili - No Beans | H-E-B | Soups & chili |
| 6 | 0 | H-E-B Texas Style Chili - No Beans - Value Pack | H-E-B | Soups & chili |
| 7 | 0 | H-E-B Refried Beans with Tomatoes & Chili | H-E-B | Canned & dried food |
| 8 | 0 | H-E-B Black Beans With Lime & Jalapenos | H-E-B | Canned & dried food |
| 9 | 2 | H-E-B Caribbean Style Black Beans | H-E-B | Canned & dried food |
| 10 | 0 | H-E-B Texas Style Spicy Charro Beans | H-E-B | Canned & dried food |

- MISS label 2 · h11 b26 s11 · H-E-B Texas-Style Ranch Beans
- MISS label 2 · h15 b22 s22 · H-E-B Great Northern Beans
- MISS label 2 · h19 b20 s43 · H-E-B Navy Beans

### s119 "lemon garlic spice rub"

official 0.398 · judged-only 0.592 · BM25 0.125 · relevant labelled 15 · fold 1 (minilm, w=0.1)

| # | Label | Title | Brand | Category |
|---|---|---|---|---|
| 1 | 0 | Central Market Garlic-Lemon Pepper Dry Rubbed Natural Boneless Pork | Central Market | Meat |
| 2 | - | H-E-B Texas Originals Rib Rub Coarse Seasoning Spice Blend | H-E-B | Spices & seasonings |
| 3 | 1 | H-E-B Garlic, Sea Salt & Parsley Seasoning Blend | H-E-B | Spices & seasonings |
| 4 | 2 | H-E-B Lemon Pepper Spice Blend | H-E-B | Spices & seasonings |
| 5 | 0 | Central Market Garlic Lemon Pepper Dry Rubbed Natural Bone In Pork | Central Market | Meat |
| 6 | 2 | Hill Country Fare Lemon Pepper | Hill Country Fare | Spices & seasonings |
| 7 | - | H-E-B Texas Originals Brisket Rub Spice Blend | H-E-B | Spices & seasonings |
| 8 | - | Hill Country Fare Lemon Pepper - Texas-Size Pack | Hill Country Fare | Spices & seasonings |
| 9 | 2 | H-E-B Lemon Pepper Grinder | H-E-B | Spices & seasonings |
| 10 | 0 | Central Market Lemon Rosemary Chicken Breast | Central Market | Ready meals & snacks |

- MISS label 2 · h11 b26 s13 · H-E-B Fish Market Garlic Onion Rosemary Seasoning Spice Blend
- MISS label 2 · h15 b81 s6 · H-E-B Garlic Salt Seasoning
- MISS label 2 · h16 b51 s10 · H-E-B Garlic Pepper Spice Blend

### s238 "gluten-free vegetable sauce"

official 0.399 · judged-only 0.436 · BM25 0.465 · relevant labelled 9 · fold 4 (minilm, w=0.1)

| # | Label | Title | Brand | Category |
|---|---|---|---|---|
| 1 | 0 | H-E-B Cooking Sauce - Rosemary & Garlic | H-E-B | Sauces & marinades |
| 2 | 2 | H-E-B Cooking Sauce - Mongolian Style | H-E-B | Sauces & marinades |
| 3 | 0 | H-E-B Cooking Sauce - Bacon & Chives | H-E-B | Sauces & marinades |
| 4 | 0 | H-E-B Cooking Sauce - Herb Butter | H-E-B | Sauces & marinades |
| 5 | 0 | H-E-B Cooking Sauce - Beef Stew | H-E-B | Sauces & marinades |
| 6 | 0 | H-E-B Sloppy Joe Sauce | H-E-B | Sauces & marinades |
| 7 | 0 | H-E-B Cooking Sauce - Butter Chicken | H-E-B | Sauces & marinades |
| 8 | - | H-E-B Texas-Style Ranch Beans | H-E-B | Canned & dried food |
| 9 | 2 | H-E-B Cooking Sauce - Toasted Sesame | H-E-B | Sauces & marinades |
| 10 | 0 | H-E-B Organics Sloppy Joe Sauce | H-E-B | Sauces & marinades |

- MISS label 3 · h12 b7 s42 · H-E-B Cooking Sauce - Marsala
- MISS label 3 · h14 b8 s55 · H-E-B Cooking Sauce - Chinese Stir Fry
- MISS label 2 · h11 b168 s3 · H-E-B Spaghetti Sauce Mix

### s33 "ready to eat sushi with wasabi and soy sauce"

official 0.410 · judged-only 0.547 · BM25 0.195 · relevant labelled 32 · fold 2 (minilm, w=0.15)

| # | Label | Title | Brand | Category |
|---|---|---|---|---|
| 1 | 2 | H-E-B Sushiya Houstonian Sushi Roll | H-E-B Sushiya | Ready meals & snacks |
| 2 | 2 | H-E-B Sushiya Philadelphia Sushi Roll with Smoked Salmon | H-E-B Sushiya | Ready meals & snacks |
| 3 | - | H-E-B Sushiya Tuna Avocado Sushi Roll | H-E-B Sushiya | Ready meals & snacks |
| 4 | - | H-E-B Sushiya Salmon Avocado Sushi Roll | H-E-B Sushiya | Ready meals & snacks |
| 5 | 2 | H-E-B Sushiya Houstonian Sushi Roll - Kosher | H-E-B Sushiya | Ready meals & snacks |
| 6 | 3 | H-E-B Sushiya Crunchy Temptation Sushi Roll | H-E-B Sushiya | Ready meals & snacks |
| 7 | 0 | H-E-B Sushiya Original Poke Sauce | H-E-B Sushiya | Ready meals & snacks |
| 8 | 1 | H-E-B Sushiya Austin Sushi Roll | H-E-B Sushiya | Ready meals & snacks |
| 9 | 3 | H-E-B Sushiya Spicy Tuna Sushi Roll | H-E-B Sushiya | Ready meals & snacks |
| 10 | 0 | H-E-B Sushiya Musubi | H-E-B Sushiya | Ready meals & snacks |

- MISS label 3 · h14 b39 s12 · H-E-B Sushiya Spicy California Sushi Roll
- MISS label 3 · h24 b19 s29 · H-E-B Sushiya California Sushi Roll Value Pack
- MISS label 3 · h25 b51 s19 · H-E-B Sushiya Rio Grande Sushi Roll
