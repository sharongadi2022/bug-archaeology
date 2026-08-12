# Bug Archaeology Assistant

A retrieval system that answers **why** code is the way it is, by indexing a repository's
full history — code, commits, diffs, PR threads, and issue threads — not just its current source.

**One-liner:** "It's not search. Search finds where something is. This tells you *why* it's there."

**Target questions:**
1. "Why does this wait two seconds? It looks unnecessary." → names the incident, the root cause, links the original bug report.
2. "Has this problem happened before?" → yes, 2021 and 2023, same cause, here's the fix.

---

## Non-negotiable principles

Do not compromise on these without explicitly raising the conflict first.

1. **Per-source chunking.** Never fixed token windows.
   - Code → AST boundaries via tree-sitter (function/class/method). Never split mid-function.
   - Prose (PR/issue threads) → argument boundaries, always carrying author + date + thread title.
   - Diffs → hunk-level, with the commit message prepended into the embedded text. The message is the valuable half and the hunk is meaningless without it.

2. **Hybrid retrieval.** BM25 + vector similarity, merged with Reciprocal Rank Fusion (k≈60).
   Never collapse to a single method unless explicitly asked for a simplified version.
   Because sources are heterogeneous, RRF must be source-aware (quotas or query-adaptive weights) —
   flat RRF lets one source type starve the others.

3. **Incremental reindexing.** Only re-parse/re-chunk/re-embed what a commit actually changed, via git diff. Never full re-index on push.

4. **Verified citations.** Every claim cites a source. Every cited ref is checked against the
   retrieved chunk set before the answer ships. Untraceable claims do not ship — a system that
   sounds certain and makes things up is worse than no system.

5. **Abstention over confabulation.** "Insufficient information" is a correct answer and is
   explicitly tested in the eval set.

---

## Citation formats

| source_type | format |
|---|---|
| `code` | `src/models.py:Request.prepare:120-145 @a3f9c21` |
| `diff` | `commit a3f9c21 — src/models.py hunk 2 (2022-03-14)` |
| `pr_thread` | `PR #1234 — @author, 2022-03-14` |
| `issue_thread` | `issue #987 — @author, 2021-08-02` |

---

## Stack

- Python 3.11+
- Parsing: tree-sitter + tree-sitter-python (official grammar binding, Python only for now).
  Not tree-sitter-languages — it's unmaintained against current tree-sitter releases. Added in Phase 2.
- Embeddings: `bge-small-en-v1.5` local for iteration, `text-embedding-3-small` for final index
- Keyword search: `rank_bm25`
- Vector DB: LanceDB
- Raw store + index state + link graph: SQLite
- Generation: Claude via the Anthropic Python SDK
- Backend: FastAPI · Frontend: Streamlit (MVP)
- Reindex trigger: GitHub webhook or Action

---

## Git identity

All commits on this project are authored and committed as:

```
Sharon <186576786+sharongadi2022@users.noreply.github.com>
```

GitHub account: `sharongadi2022`. This is set **repo-local only** (`git config user.name` /
`user.email` inside this repo, never `--global`) — the machine this project is developed on
has other projects under a different identity. Do not guess a different name or email for
commits here, and do not set this globally.

---

## Build order

See `PLAN_PART_1_WHAT.md` for full detail and exit criteria. Do not skip ahead; confirm the
prior phase's exit criteria are met before starting the next.

0. Foundation · 1. Ingestion · 2. Per-source chunking ⭐ · 3. Eval set ·
4. Indexing + hybrid retrieval · 5. Generation + citation verification ·
6. Link-hop retrieval · 7. FastAPI + Streamlit · 8. Incremental reindex · 9. Polish + MCP server

`PLAN_PART_2_HOW.md` covers tooling and execution per phase.

---

## Working agreements

- **Give complete file contents** when writing or editing code, not fragments or partial diffs,
  unless a diff is specifically requested.
- **State which phase** a new component belongs to before implementing it, and confirm the prior
  phase works.
- **Make reasonable assumptions and proceed**, stating them in one line — don't stall on
  ambiguity unless it would send the architecture the wrong way.
- **Flag deviations.** If something isn't in the plan, implement it but say so explicitly.
- **Correctness of retrieval and citations beats speed.** The project's whole value is retrieval
  quality. There is no prize for shipping fast.
- **Explain the reasoning behind design choices** when asked for explanations — why AST over token
  windows, why hybrid over vector-only. These get defended in interviews.

---

## Repo layout

```
bug-archaeology/
├── README.md
├── pyproject.toml
├── CLAUDE.md
├── .cursorrules                  # mirror of this file
├── .claude/
│   ├── commands/                 # /chunk-review /run-eval /adr /spec-check
│   ├── agents/                   # chunk-critic, eval-writer, retrieval-debugger
│   └── settings.json             # hooks: ruff + pytest on write
├── .github/workflows/reindex.yml
├── src/bug_archaeology/
│   ├── ingestion/{git_walker.py, github_client.py, raw_store.py, link_extractor.py}
│   ├── chunking/{base.py, code_chunker.py, diff_chunker.py, thread_chunker.py, models.py}
│   ├── indexing/{embedder.py, vector_store.py, bm25_store.py, incremental.py}
│   ├── retrieval/{hybrid_retriever.py, link_hop.py}
│   ├── generation/{answer_generator.py, citation_verifier.py}
│   ├── api/main.py
│   ├── mcp/server.py             # Phase 9 — expose as MCP tools
│   └── db/state.py
├── eval/{eval_set.json, run_eval.py, scorecards/}
├── frontend/streamlit_app.py
└── tests/
```

Package root is `src/bug_archaeology/`, not flat `src/` — avoids generic top-level names
(`api`, `db`, `indexing`) colliding with real PyPI packages. Import as
`from bug_archaeology.chunking.base import Chunk`.
