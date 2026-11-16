# Recruiter read-through kit

This is the check that matters most for the landing page: whether a real reader understands it. It has not been run. Run it with three people who hire or screen for AI Engineer roles and who have not seen the project.

## Setup

- Open the page on a laptop at its normal width. Do not explain anything first.
- Use the deployed page once the new version is live, or a local build until then.
- Ask the questions out loud, in order, and write down each answer in the reader's own words.
- Do not correct a wrong answer during the session. A wrong answer is the result you came for.

## Questions

**1. Five-second test.** Show the page for five seconds, then hide it. Ask: "What does this project do, and what was built?"

Expected: a grocery product search that combines keyword matching with meaning-based matching; what was built is the ranking, the evaluation and the service (API and page).

Counts as right if the reader names search over products and at least one of: combining keywords with meaning, or that it was measured against keyword search. Counts as wrong if they say it is a chatbot, an LLM product, or H-E-B's own search.

**2. Unlimited time, page visible.** Ask: "How much better is it than keyword search, and how sure is the author?"

Expected: about +0.07 on the official score on unseen queries, with the caveat that the gain mostly disappears when only graded products are counted, because ungraded products are scored as wrong.

Counts as right if the reader gives the gain (roughly +0.07, or 0.63 to 0.70) and any version of the caveat. Counts as half right if they give the gain with no caveat. Counts as wrong if they say "11% better" or "clearly better" with no qualification.

**3. Unlimited time, page visible.** Ask: "Name one thing it gets wrong."

Expected: either worked failure on the page. "seasoning for chicken fajitas" returns seasoned chicken instead of seasoning in both rankings; "H-E-B size 7 diapers" is ranked better by keyword search alone.

Counts as right if the reader names either example or describes it.

## Pass rule

- Question 1 right for all three readers.
- At least two of the three readers get two or more questions right. A half-right answer to question 2 does not count as right.

The thresholds are a judgment call made when this kit was written, not a standard.

## Record

| Reader | Role | Q1 answer | Q1 right? | Q2 answer | Q2 right? | Q3 answer | Q3 right? |
|---|---|---|---|---|---|---|---|
| 1 | | | | | | | |
| 2 | | | | | | | |
| 3 | | | | | | | |

Also note, per reader: what they looked at first, anything they misread, and any question they asked. Those notes are worth more than the pass mark.

## If it fails

- Question 1 fails: the headline or first paragraph is not doing its job. Fix the hero before anything else.
- Question 2 half right for most readers: the caveat is not reaching them. Move it closer to the headline number.
- Question 3 fails: the failure examples are too far down the page or not labelled as failures clearly enough.
