# Postmortem

## What went wrong

- **The "top" model scored lower than the "cheap" model.** gpt-oss-120b got 41/50 (82%)
  while gpt-oss-20b got 43/50 (86%) — the more expensive, larger model was *less* accurate
  on this task. This wasn't noise: both models failed on the exact same two items (id 7,
  "most expensive product"; id 8, "cheapest product in Office category"), which are
  superlative/extremum questions. We checked the database for price ties on those two
  questions and found none, so the failure is a real reasoning gap, not an ambiguous gold
  answer. We did not have time to inspect the actual predicted SQL for those two items to
  pin down the exact cause (wrong ORDER BY direction vs. wrong column selected vs. something
  else) — that's the first thing to check before trusting this result further.

- **Item 12's wording was an accidental trap.** "How many orders were **placed** in total?"
  uses "placed" as a plain English verb, but `'placed'` is also a literal value in the
  `status` column of our own schema. Both API models got this item wrong (mismatch, not a
  SQL error), which is consistent with — though not confirmed to be caused by — the model
  reading it as `WHERE status = 'placed'` instead of a plain `COUNT(*)`. Lesson: when the
  schema's own enum values overlap with common English words, question wording needs to be
  written defensively (e.g. "how many orders exist in total, regardless of status?").

- **The local model hallucinated schema that doesn't exist.** qwen2.5:3b generated SQL
  referencing a `categories` table (items 8, 15) and a nonexistent `order_items.product_id`
  column ordering (item 3) — errors that `sqlite3` caught immediately as `sql_error`, even
  though the correct schema was given verbatim in the same prompt used for the other two
  models. 16/50 of its failures were schema errors like this rather than logic errors,
  meaning a meaningful chunk of its lower accuracy (34/50, 68%) is "didn't read the schema
  carefully" rather than "reasoned about the question incorrectly."

- **Free-tier pricing made the cost comparison less informative than intended.** Both Groq
  models report $0.00/1k requests because they're on the free tier, and the local model is
  $0 because the hardware is already owned — so the cost columns in the results table don't
  actually differentiate the three models the way the assignment's cost analysis is meant to.
  We only found this out after the run; in hindsight we should have flagged it in the report
  setup section before running rather than after.

- **Local inference latency was far higher than expected.** p50 latency for qwen2.5:3b was
  8.3s vs. 1.6-1.9s for the two Groq-hosted models — roughly 5x slower. This wasn't a
  surprise in direction (local CPU inference vs. hosted GPU inference), but the magnitude
  affected how we read the "requests per hour" ceiling in the cost analysis (~387/hour on
  this machine), which matters for the 100x-traffic discussion.

## What we'd do differently

- Check `predicted_sql` for the two shared-failure items (7, 8) before finalizing the
  "top model is worse" claim — it might be a fixable prompt issue, not a real capability gap.
- Rewrite item 12's question to avoid the "placed" wording overlap with the status enum.
- Give the local model a shorter, more directive prompt (or a smaller/cleaner schema) to see
  whether the hallucinated-table errors are a context-length/attention issue or a genuine
  capability limit at 3B parameters.
- Decide up front whether free-tier $0 costs are acceptable for the assignment's cost
  analysis, or whether we need at least one paid-pricing comparison point to make the
  "cost at scale" discussion meaningful.

## What we learned

- Bigger/more expensive doesn't mean more accurate — this run is a direct, concrete
  demonstration of the whole point of the assignment ("which option is better, and how do
  you know?"): our assumption that the 120b model would win was wrong, and only measuring
  it caught that.
- Small local models can fail in a qualitatively different way than API models: not just
  "gets the wrong answer" but "doesn't reliably ground to the schema it was just given,"
  which shows up as outright SQL errors rather than subtle logic mistakes.
- A cost comparison built entirely on free tiers doesn't actually answer "which model would
  we choose at scale" — it just tells you free tiers are free. The real cost question only
  becomes answerable once at least one side of the comparison has real pricing.
