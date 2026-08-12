# Bug Archaeology Assistant — Part 1: What We're Building

**One-liner:** "It's not search. Search finds where something is. This tells you *why* it's there."

**Where things stand on 2026-08-07:** nothing built yet. Empty folder. This document replaces the build order in `project_rag_assistant_build_spec.md`, which was written before the pivot and still describes a code-only tool.

---

## What I'm assuming

If any of these are wrong, tell me and I'll re-cut the plan around it.

| # | Assumption | Why |
|---|---|---|
| 1 | **Target repo: `psf/requests`** | 13 years of history, Python, ~6,700 issues and PRs full of real arguments, and every interviewer recognizes it. Small enough to index on a laptop. |
| 2 | **Six weeks, roughly 12 hours a week** | If that's wrong, stretch the phases — don't reorder them. |
| 3 | **You're building solo, for interviews** | This is what drives moving the eval set earlier. |
| 4 | **Stack unchanged** | Python 3.11, tree-sitter, LanceDB, rank_bm25, FastAPI, Streamlit, Claude for answers. |
| 5 | **Second repo indexed: this project itself** | Free demo data that's always fresh, and it forces you to write decent commit messages. |

---

## Four places I've departed from your original spec

### 1. The test set gets built in Phase 3, not Phase 5

**You can't improve a number you never wrote down.**

Your original order was: build the retrieval system, get it working, then at the end write some questions to check it. The trouble is that between "start building retrieval" and "finish building retrieval" you'll make forty small decisions. Should RRF's k be 60 or 30? Should the BM25 index include docstrings? Should code chunks win ties against issue comments? Every one of those is a fork in the road, and without a scorecard you'll pick whichever one made the last answer you happened to look at feel a bit better.

That's not tuning. That's superstition with extra steps.

So the test set moves earlier: 20 questions, written by hand, with the correct source marked down before you've built anything that could bias you. Then every change produces a number that moved or didn't. This is also the difference between telling an interviewer "my hybrid search works well" and telling them "vector-only got 61% recall, hybrid got 78%, and here's the query type that explains the gap." The first is an opinion about your own work. The second is evidence.

### 2. Getting the data is its own phase now

**Downloading and chopping up have to be separate jobs, or you'll re-download 13 years of history every time you change your mind about chopping.**

The old spec had one quick step — clone the repo — and then went straight to parsing. That was fine when the only material was current source code. It isn't fine now.

Do the arithmetic. `requests` has around 6,700 issues and pull requests. GitHub's API gives you 5,000 requests an hour once you're authenticated. Pull each comment thread individually and you've blown the hourly budget before you've touched a single commit. Then somewhere around hour two, a request times out, the script dies, and if downloading and parsing live in the same script you've just lost the download too.

So Phase 1 does nothing but fetch, and it writes everything into a local SQLite store in raw form. Phase 2 reads from that store. You will rewrite your chunking logic thirty or forty times before you're satisfied — that's not a sign of failure, that's Phase 2 working correctly — and none of those rewrites should cost you another overnight download.

### 3. A table of what connects to what

**"Has this bug happened before?" isn't a similarity question, it's a trail-following question.**

Here's the actual shape of the answer you want. Someone points at a line of code. That line was last touched by commit `a3f9c21`. That commit belongs to PR #1450. That PR's description says "fixes #987." Issue #987, from 2021, says "this is the same thing we saw in #412." And #412 is from 2019.

Now you can say: this has happened three times, here's the root cause, here's what finally fixed it.

Nothing in that chain came from finding text that looked similar. Every step was following an arrow. Your original data model had no arrows — each chunk was a standalone record with no idea what it was related to. So I'm adding a table that stores nothing but those connections: this commit mentions that PR, this PR closes that issue, this issue references that issue.

Deliberately boring. A SQLite table, not a graph database. But without it, one of your two headline questions simply doesn't work.

### 4. Citations carry the commit ID — and this one's your call

**"Line 120" means nothing on its own once you're indexing history.**

Your stated format is `file_path:function_name:start_line-end_line`. That's exactly right for a tool that only looks at code as it exists today. But this tool looks at thirteen years, and `models.py` changed hundreds of times over those thirteen years. Line 120 in 2019 and line 120 today are different lines, in a different function, possibly in a file that's since been split in two.

So I appended the short commit hash: `src/models.py:Request.prepare:120-145 @a3f9c21`. It reads as "these lines, as of this specific version." The practical payoff is that the hash is what lets you build a GitHub link that lands on the right lines — without it, every link you generate silently rots as soon as the file shifts.

Small change, but it's your format and you specified it precisely. Say the word and I'll drop it.

---

## The data model

### Every chunk shares a spine

Whatever the source, each chunk carries the same core fields plus a bag of type-specific extras. The reason for a shared spine: retrieval has to rank a function definition against an issue comment against a diff hunk, and it can only do that if they're comparable objects.

```
Chunk
├─ chunk_id          hash(source_type + natural_key)
├─ repo
├─ source_type       code | diff | pr_thread | issue_thread
├─ text              what gets embedded and BM25-indexed
├─ display_text      what the model actually sees, including a provenance header
├─ authored_at       date — this is what makes temporal reasoning possible
├─ author
├─ links             connections to other chunks
└─ extras            type-specific fields
```

Note that `text` and `display_text` are different on purpose. What you search over and what you show the model aren't the same thing — a diff hunk gets its commit message folded into the embedded text so it's findable, and gets a readable header when it's shown.

### Per-type fields and citation formats

| source_type | extras | citation format |
|---|---|---|
| `code` | file_path, node_type, name, parent_class, start_line, end_line, docstring, commit_sha | `src/models.py:Request.prepare:120-145 @a3f9c21` |
| `diff` | commit_sha, file_path, hunk_index, commit_message, insertions, deletions | `commit a3f9c21 — src/models.py hunk 2 (2022-03-14)` |
| `pr_thread` | pr_number, title, state, merged, comment_ids, participants | `PR #1234 — @kennethreitz, 2022-03-14` |
| `issue_thread` | issue_number, title, state, labels, closed_by_commit | `issue #987 — @user, 2021-08-02` |

### The connection table

```
LinkRef: (from_chunk_id, to_ref_type, to_ref_value, relation)
```

Arrows worth extracting:

- commit message mentions `#1234` → commit points at PR or issue
- PR body says "Fixes #987" → PR closes issue
- PR's merge commit hash → PR points at commit
- a diff touches a file → diff points at file
- an issue comment names another issue → issue references issue
- a code chunk's file has diff history → code points at its own past

---

## The nine phases

### Phase 0 — Foundation *(2 days)*

**Get the rules written down before you write any code, because otherwise the rules quietly stop applying.**

Here's the failure this prevents. Three weeks in, you open a fresh session and ask for help adding the diff chunker. The agent — with no memory of anything you decided — proposes splitting diffs into 512-token windows, because that's the common approach and nothing in the project said otherwise. You either catch it and lose twenty minutes, or you don't catch it and lose a week.

`CLAUDE.md` is the fix. It's read at the start of every session, so the four non-negotiables travel with the code instead of living in your head.

**Deliverables:** repo scaffold, `pyproject.toml`, populated `CLAUDE.md` and `AGENTS.md`, path-scoped rules, pre-commit hooks, target repo cloned.

**Done when:** `pytest` passes on a trivial test, and `/context` in Claude Code confirms your memory files actually loaded. That second check matters more than it sounds — a silently unloaded `CLAUDE.md` looks exactly like a loaded one until you notice the agent ignoring you.

---

### Phase 1 — Ingestion *(Week 1)*

**Fetch everything into a local store and don't chop anything up yet.**

Four kinds of material to pull:

1. Full commit history via GitPython — hash, message, author, date, parent
2. Per-file diff hunks for every commit
3. Every PR with its full comment thread and review comments
4. Every issue with its full comment thread and labels

Then scan all that text for `#\d+`, `Fixes`, `Closes`, `Refs`, and bare commit hashes, and build the connection table out of what you find.

The single most important property here is **resumability**. Not "nice to have" — the thing will fail partway through, probably more than once, and a fetcher that starts from zero every time it crashes is a fetcher you'll never successfully run. Checkpoint after every batch. Make re-running it a no-op for anything already stored.

Batch through GraphQL rather than hitting REST once per comment thread. Then kick the whole thing off before bed.

**Deliverables:** `raw.db` with tables for commits, diff hunks, PR threads, issue threads, and links. A CLI that's resumable and idempotent.

**Done when:** a full ingest of `psf/requests` completes, running it a second time fetches nothing new, and you can answer "show me every issue that mentions commit X" in plain SQL.

---

### Phase 2 — Per-source chunking *(Week 2)* ⭐

**This is the phase the whole project lives or dies on, and it's the one interviewers will actually dig into.**

Four kinds of material, four strategies, one shared interface.

**Code — cut at AST boundaries.** tree-sitter, function and class and method nodes, full source span, enclosing class name, the docstring or comment sitting above it. Plus a summary chunk per class holding the docstring and method list, for when someone asks a high-level question. Any function over 1,500 tokens gets flagged rather than quietly truncated — silent truncation is how you end up with a chunk that confidently describes the first half of a function and has no idea the second half exists.

**Diffs — the hunk is useless without the message.** One chunk per commit-file-hunk, and the commit message gets folded *into the embedded text*, not filed away as metadata.

Why this matters, concretely. A hunk that reads `+ time.sleep(2)` tells you nothing. Nobody will ever find it, and if they do it won't help. The same hunk with "workaround for upstream connection reset, see #987" sitting on top of it is the entire product. Your own framing was right: the note is the valuable half, and the hunk is meaningless on its own.

Guardrail: some commits are worthless in bulk. A mass reformat touching 400 files, a vendored dependency update, generated files. These generate hundreds of chunks that say nothing and dilute everything around them. Filter by hunk count and path pattern.

**PR and issue threads — cut at argument boundaries.** Two obvious approaches both fail. One chunk per comment fragments the discussion into pieces too small to mean anything — half of them are "+1" and "same here." One chunk per thread goes too far the other way; a 60-comment thread averaged into one embedding is a smear that matches everything vaguely and nothing well.

So: cut where the argument turns. Consecutive comments from the same person merge together. A topic shift or a rebuttal starts a new chunk. Every chunk keeps a header with the thread title, who's involved, and when — so a fragment pulled out of context is never orphaned.

Each thread also gets one **resolution chunk**: title, final state, the closing comment, and the commit that closed it. That's the chunk that answers "what did they actually decide," which is usually the real question.

**Everywhere — a provenance header.** Every chunk's `display_text` opens with one line saying what it is and where it came from. The model should never see a naked fragment with no idea whether it's looking at code, an argument, or a change.

**Deliverables:** `src/chunking/` with a base interface and four chunkers. A stats report showing count and token distribution per source type.

**Done when:** you've read 20 random chunks of each type by hand and every one makes sense standing alone. No chunk splits a function mid-body or an argument mid-sentence.

---

### Phase 3 — The test set *(first half of Week 3)*

**Twenty questions, answers marked by hand, written before you've built anything that could bias you.**

For each one: the question, which chunk or chunks genuinely contain the answer, which source types are needed, and a one-line version of the right answer.

Spread them deliberately across question shapes, because a test set that's all one shape will tell you your system is great at exactly one thing:

| Shape | Example | What it's testing |
|---|---|---|
| Why is this here | "Why does `send()` retry three times?" | diffs and threads |
| Has this happened before | "Have we had connection-reset bugs before?" | trail-following and dates |
| Exact identifier | "What raises `ChunkedEncodingError`?" | BM25's strength |
| Vague paraphrase | "Why is this slow?" finding "performance was terrible" | embeddings' strength |
| What was decided | "Why was urllib3 vendored?" | resolution chunks |
| Should refuse to answer | something genuinely not in the corpus | abstention |

That last row does more work than it looks like. A system that invents a plausible answer rather than saying "I don't have this" fails your own stated bar — sounding certain about restaurant history you made up is worse than nobody being there at all. So it gets tested like any other behaviour.

**What to measure:** recall@6, MRR, citation precision (what fraction of cited sources actually exist in what was retrieved), and abstention accuracy.

**Done when:** the harness runs end to end against a stub retriever and prints a scorecard. Also: **write five questions you expect to fail.** If your first run scores 95% across the board, the test set is too easy and it's lying to you.

---

### Phase 4 — Indexing and hybrid retrieval *(second half of Week 3)*

**Embed everything, keep BM25 and the vector index in sync, merge with RRF — and then deal with the problem RRF has when your sources are this different from each other.**

The standard hybrid setup: top 20 from vector similarity, top 20 from BM25, merge with Reciprocal Rank Fusion at k≈60, keep the best 6 to 10.

Here's what the original spec didn't have to worry about. Compare two chunks. A code chunk is forty lines of dense identifiers and punctuation. An issue comment is "yeah, this broke for me too, on 3.9." Different lengths by an order of magnitude, completely different vocabulary, and similarity scores that aren't really comparable between them.

Run flat RRF over that mixture and one source type sweeps the board. Concretely: you ask "why does `send()` retry three times," and you get back six code chunks — all of them showing you the retry logic, none of them telling you why it exists. Which is the exact failure the entire project was built to fix.

Two fixes to build and race against each other:

- **Quotas** — run RRF separately within each source type, then take a fixed budget from each. Three code, three diff, four thread.
- **Query-adaptive weights** — a cheap classifier notices that "why" and "when" and "who" questions want prose and diffs, while "where" and "what" questions want code, and shifts the weights.

Measure both against flat RRF. Whichever wins, you now have a second real finding to talk about.

**Done when:** you have a table comparing vector-only, BM25-only, flat RRF, quota RRF, and adaptive RRF across all four metrics. **This table is the project.** Everything before it exists to make the numbers trustworthy; everything after exists to make them presentable.

---

### Phase 5 — Writing answers with citations that hold up *(first half of Week 4)*

**A confident wrong answer with a well-formatted fake citation is worse than no answer at all.**

The failure mode is specific and it will happen. The model writes "this was fixed in PR #1450." It's fluent, it's formatted correctly, it looks exactly like every real citation in the answer. And there is no PR #1450. It made it up, because a number was needed and one appeared.

So: low temperature. A prompt that restricts the model to the retrieved excerpts and nothing else. The per-source citation formats from the table above. And an explicit path for saying "I don't have enough here."

Then two layers of checking:

1. Every citation must point at something that's actually in the retrieved set. If it doesn't, reject the answer and regenerate once. If it fails again, downgrade to "insufficient information."
2. Every factual sentence must carry at least one citation. Uncited claims don't ship.

**Done when:** zero fabricated citations across the whole test set, and the question designed to be unanswerable actually gets refused.

---

### Phase 6 — Following the trail *(second half of Week 4)*

**This is what makes "has this happened before" work rather than just sort of work.**

Two rounds. First, retrieve normally. Then take the top results, follow their arrows — commit to PR, PR to issue, issue to sibling issues — and pull the neighbours in as a second batch of candidates. Re-rank the combined pile.

Stop at one hop. Two hops mostly drags in noise; by then you're three arrows from the question and everything is loosely related to everything.

Also worth doing here: notice when things cluster in time. If three retrieved items describe the same root cause in 2021, 2022 and 2024, the answer should say "this has recurred three times" rather than listing them as three unrelated facts.

**Done when:** the has-this-happened-before questions score better than they did in Phase 4. And if they don't — cut this phase and write up why in the README. A candidate who removed a clever feature because the numbers said it didn't help is more convincing than one who kept it because it sounded good.

---

### Phase 7 — Making it usable *(first half of Week 5)*

FastAPI with `POST /chat`, `POST /index/full`, `POST /index/incremental`, `GET /status/{repo}`. Streamlit on top: chat, citations as clickable GitHub links, a filter by source type, and a panel that shows the retrieved chunks.

**That debug panel isn't a developer convenience — it's the demo.** Anyone can show a chatbot producing an answer. Showing the four sources it drew from, one of them a 2021 bug report nobody remembered, is what makes the point land.

---

### Phase 8 — Only reindexing what changed *(second half of Week 5)*

**Re-embedding thirteen years of history because someone fixed a typo is absurd, and the fact that it's absurd is a resume line.**

Git diff tells you which files a commit actually touched. Only those get re-parsed, re-chunked, re-embedded. New commits, PRs, and comments append. SQLite tracks the last indexed hash per repo and the last indexed time per thread. A GitHub webhook or Action pulls the trigger.

**Done when:** you push a commit to your own repo and within a minute the assistant can answer a question about it. Log the wall-clock time and the cost, both ways. "Incremental reindex costs about 4% of a full rebuild" is a much better sentence when it's measured rather than estimated.

---

### Phase 9 — Making it land *(Week 6)*

- README built on the kitchen-note analogy, not on an architecture diagram
- The Phase 4 comparison table, high up, where nobody can miss it
- A side-by-side of AST chunking versus fixed-token chunking on one specific real function
- One query where BM25 found what embeddings missed, and one where it went the other way
- A 90-second demo video
- An MCP server wrapper, so the tool is callable from inside Claude Code and Cursor

---

## What's likely to go wrong

| Risk | Odds | What to do |
|---|---|---|
| Rate limits stall ingestion | High | GraphQL batching, checkpoint constantly, run it overnight |
| Prose chunks drown out code, or the reverse | High | Quotas — already in Phase 4 |
| Test set is too easy, everything scores 95% | Medium | Write five questions you expect to fail. If none fail, the set is wrong |
| Scope creep into other languages | Medium | Python only until Phase 9 ships. No exceptions |
| Embedding cost on 13 years of history | Low | `bge-small` locally while iterating, OpenAI only for the final index |
| Trail-following adds noise, not signal | Medium | Phase 6's exit criteria already permits cutting it |

---

## The one thing that decides whether this project works

Not the architecture. **The Phase 4 comparison table.**

A working RAG demo is a commodity in 2026 — a weekend and a tutorial gets you one. What isn't a commodity is someone who can say: flat RRF got 61% recall@6, source-quota RRF got 78%, and the entire gap came from "why" questions where code chunks were crowding out the issue threads that actually held the answer.

That sentence is the whole project. Every phase before it exists to make the number honest. Every phase after exists to make it visible.
