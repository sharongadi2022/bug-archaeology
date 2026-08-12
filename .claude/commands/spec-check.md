Audit the current codebase against the four non-negotiable principles in CLAUDE.md.

For each principle, report: COMPLIANT / VIOLATED / NOT YET IMPLEMENTED, with file:line evidence.

1. Per-source chunking — no fixed token windows anywhere. Code split on AST boundaries,
   prose on argument boundaries with author+date+title carried, diffs at hunk level with the
   commit message prepended into the embedded text.
2. Hybrid retrieval — BM25 and vector both present, merged with RRF (k≈60), and source-aware
   (quota or query-adaptive weighting), not flat.
3. Incremental reindexing — reindex path is driven by git diff, never a full rebuild.
4. Verified citations — every cited ref is checked against the retrieved chunk set before the
   answer is returned.

Be adversarial. Do not give credit for intent. If a principle is only half-implemented, say
VIOLATED and name the gap. Do not fix anything — report only.
