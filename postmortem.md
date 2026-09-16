# Postmortem

*A postmortem with no problems loses points — be specific about what
actually went wrong, not just what you'd hypothetically improve.*

## What went wrong

- [Fill in, e.g.: the local model returned markdown-fenced SQL despite
  the prompt saying not to, until we added `clean_sql()` stripping —
  how many items did this affect before the fix?]
- [Fill in, e.g.: any items where the gold SQL itself needed a rewrite
  after a teammate caught an ambiguous question]
- [Fill in, e.g.: rate limits / timeouts hit during the full 50-item run
  against the API, and how that was handled]
- [Fill in, e.g.: local model latency variance between the first request
  (cold load) and subsequent ones]

## What we'd do differently

- [Fill in]

## What we learned

- [Fill in — e.g. about prompt sensitivity, about how "hard" the hard
  tier actually was for each model, about local vs. API tradeoffs]
