# The Prompt Pack — Phases 0 to 5

Everything you paste into Claude Code to get from empty folder to a working CLI that answers
"why does this code do that" with verified citations.

**Target:** `psf/requests`. **Scope of first pass:** phases 0–5, terminal only, no web UI.
**Realistic time:** 5–7 evenings.

---

## How to use this document

Each phase gives you three things:

1. **The prompt** — paste it verbatim into a fresh Claude Code session. Don't paraphrase; the
   awkward specific clauses are the ones doing the work.
2. **Your check** — what *you* run and look at before moving on. Not "did it say it was done."
3. **What will probably go wrong** — the failures I actually expect, and what to do about each.

### Five rules for the whole run

**One phase per session, started fresh.** Type `/clear` between phases, or just quit and relaunch.
A session that's been running for four hours starts contradicting decisions it made in hour one,
and you won't notice because it says them with the same confidence either way.

**Plan mode for phases 2 and 4.** Shift+Tab before pasting the prompt, read what it proposes, then
approve. These are the two phases where a wrong shape costs you a day of rework.

**Commit and tag at every phase boundary.**

```bash
git add -A && git commit -m "phase 2: per-source chunking" && git tag phase-2
```

When phase 4 goes sideways — and one of them will — `git checkout phase-3` gets you back to known-good
in one command instead of an hour of unpicking.

**Never accept "done" without running your own check.** The agent's report that tests pass is not
the same as tests passing. This is the single habit that separates a working system from one that
looks like it works.

**When something breaks, paste the actual traceback.** Not "it failed." The full error. You'll get a
fix in one turn instead of four.

---

# Phase 0 — Foundation

**Building:** repo scaffold, dependencies, hooks, cloned corpus, green `pytest`.

You already have `PHASE_0_WALKTHROUGH.md` covering this in step-by-step detail. Follow that document
rather than this prompt if you want the full explanation of every line. Use the prompt below if you
just want it built.

### The prompt

```
Read CLAUDE.md, PLAN_PART_1_WHAT.md, and PHASE_0_WALKTHROUGH.md in this folder first.

Build Phase 0 exactly as PHASE_0_WALKTHROUGH.md describes: repo skeleton, pyproject.toml,
.gitignore, a trivial passing test, ruff + pre-commit hooks, bootstrap.sh, .cursorrules,
and the .claude/ directory with its commands and agents.

Three specifics:
- Use src/bug_archaeology/ as the package root, not flat src/. Update CLAUDE.md's repo
  layout section to match.
- Do NOT clone psf/requests into the repo. Clone it to ../corpus/requests, outside this
  git repo, so it never lands in my history.
- For tree-sitter, use the tree-sitter-python official binding, not tree-sitter-languages.
  tree-sitter-languages ships prebuilt wheels that break on newer Python versions. If you
  disagree, say so before writing pyproject.toml.

When you're done, run pytest and pre-commit run --all-files yourself and show me the real
output. Do not tell me it works without showing me.
```

### Your check

```bash
pytest                              # expect: 3 passed
pre-commit run --all-files          # expect: all hooks pass
ls ../corpus/requests               # expect: the requests source tree
git -C ../corpus/requests rev-list --count HEAD   # expect: ~6500
python -c "import tree_sitter_python; print('ok')"
```

That last line is the one that matters. If tree-sitter doesn't import now, phase 2 is dead on
arrival and you want to know tonight, not Thursday.

In Claude Code, run `/context` and confirm `CLAUDE.md` appears as loaded. A `CLAUDE.md` that silently
failed to load looks exactly like one that loaded, right up until the agent ignores your
non-negotiables and you can't work out why.

### What will probably go wrong

**tree-sitter won't install.** Most likely single failure in the whole project on Windows. If
`tree-sitter-python` also fails, you need a C compiler. On Windows that means Visual Studio Build
Tools, which is a 6GB download and an hour — which is exactly why the walkthrough puts you in WSL2.
If you're not in WSL2 and this fails, stop and move to WSL2 rather than fighting it.

**`uv` isn't on PATH after install.** Restart the terminal. Nothing exotic, but it wastes ten
minutes if you don't expect it.

**It clones `requests` inside your repo anyway.** Check `git status` before your first commit. A
6,500-commit repo accidentally staged into your own is genuinely annoying to remove afterward.

---

# Phase 1 — Ingestion

**Building:** a resumable fetcher that puts commits, diff hunks, PR threads, issue threads, and the
link graph into `raw.db`, and chops nothing up.

### The prompt

```
Phase 1: Ingestion. Read CLAUDE.md and the Phase 1 section of PLAN_PART_1_WHAT.md first.
Confirm Phase 0's exit criteria are met before you start.

Build src/bug_archaeology/ingestion/ with git_walker.py, github_client.py, raw_store.py,
and link_extractor.py, plus a CLI entry point.

What it fetches, into SQLite at data/raw.db:
1. Commits from the local clone at ../corpus/requests via GitPython — sha, message, author,
   author date, parent shas
2. Per-file diff hunks for each commit
3. PRs with full comment threads and review comments, via the GitHub GraphQL API
4. Issues with full comment threads and labels
5. A links table: scan every commit message, PR body, and comment for #\d+, "fixes",
   "closes", "refs", and bare 7-40 char hex commit hashes. Store as
   (from_chunk_id, to_ref_type, to_ref_value, relation).

Non-negotiable properties. Build these in from the start, do not add them later:
- RESUMABLE. Checkpoint to SQLite after every batch, not at the end. If it dies at 60%,
  re-running resumes at 60%.
- IDEMPOTENT. Running it twice fetches nothing new the second time. Use INSERT OR IGNORE
  on natural keys.
- RATE-LIMIT AWARE. Read the GraphQL rate limit cost and remaining fields from every
  response. When remaining drops below 200, sleep until the reset timestamp and log that
  you're doing it. Do not just catch 403 and retry blindly.
- It must NEVER silently swallow an API error. If a fetch fails, log it loudly to a
  failures table and keep going; print a summary of failures at the end.

Add --max-commits and --max-threads flags so I can do a small run first. Default them to
unlimited but I'll pass 300 and 60.

Read the token from GITHUB_TOKEN in .env. Never log the token. Add a check that errors out
with a clear message if the token is missing, rather than silently falling back to
unauthenticated requests at 60 requests/hour.

Write tests for the link extractor with real examples: "Fixes #1234", "closes #987 and
refs #412", "see a3f9c21", and a false positive like "issue #1 of the C standard" that
should still extract but I want to see how you handle it.
```

### Your check

Do the small run first. Always.

```bash
python -m bug_archaeology.ingestion --max-commits 300 --max-threads 60
```

Then run it a second time. It should finish in seconds and insert nothing. If it re-fetches, the
idempotency is fake and you must fix it now — every later phase re-runs this.

Then open the database yourself and look:

```bash
sqlite3 data/raw.db "select count(*) from commits;"
sqlite3 data/raw.db "select count(*) from links;"
sqlite3 data/raw.db "select relation, count(*) from links group by relation;"
sqlite3 data/raw.db "select message from commits limit 5;"
```

And the test that proves the point of the whole phase — pick a real issue number from your data and
follow an arrow in plain SQL:

```sql
select * from links where to_ref_value = '2011';
```

If that returns nothing for any issue number, your link extractor isn't working, and question 2 of
the project ("has this happened before?") is dead. Find out now.

**One manual spot-check worth ten minutes.** Open a real `psf/requests` issue thread in your browser,
one with quoted replies and code blocks. Compare it against what's in your database. The GitHub API's
representation of edits, quoted text, and code fences does not match what the rendered page looks
like, and finding that out in phase 4 — when retrieval is mysteriously bad and you have five layers
to suspect — is much worse than finding it now.

### What will probably go wrong

**Rate limiting.** GraphQL gives you 5,000 points an hour, and a query pulling a thread with 60
comments costs well more than one point. On the full corpus you will hit this. That's fine and
expected — that's what the sleep-until-reset behavior is for, and it's why you run the full ingest
overnight rather than watching it. On the 300-commit run you won't come close.

**It writes a fetcher that's resumable in the README and not in the code.** Very common. The test is
brutal and simple: start the ingest, hit Ctrl-C at around 40%, restart it, and watch whether it
starts from zero. Do this once. It takes two minutes and it's the difference between a fetcher you
can use and one you can't.

**Diff hunks explode.** A few commits in `requests` history are vendoring updates that touch hundreds
of files. Those alone can be a large fraction of your total hunks. You'll filter them in phase 2, but
if `select count(*) from diff_hunks` looks absurd relative to your commit count, that's why, and it's
not a bug.

**`.env` gets committed.** Check `git status` before committing. Your `.gitignore` from phase 0 should
cover it, but verify — a leaked GitHub token is a bad evening.

---

# Phase 2 — Per-source chunking ⭐

**Building:** four chunkers, one interface. This is the phase the project lives or dies on.

Do this one as **four separate sessions**, not one. Four strategies in a single context window means
the fourth chunker comes out as a slightly worse copy of the first. And use plan mode for each.

## 2a — Code chunker

```
Phase 2a: the code chunker. Read CLAUDE.md and the Phase 2 section of
PLAN_PART_1_WHAT.md. Confirm Phase 1 is complete — data/raw.db should have commits,
hunks, and threads in it.

Enter plan mode first. Propose the design, let me read it, then build.

Build src/bug_archaeology/chunking/base.py (the shared Chunk model and chunker interface)
and code_chunker.py.

The Chunk spine, exactly as PLAN_PART_1_WHAT.md specifies:
chunk_id, repo, source_type, text, display_text, authored_at, author, links, extras.
text and display_text are different on purpose — text is what gets embedded and
BM25-indexed, display_text is what the model sees and carries a provenance header.

The code chunker:
- tree-sitter, Python grammar. Cut at function_definition, class_definition, and methods.
- NEVER split mid-function. If a function exceeds 1500 tokens, emit it whole and set a
  flag in extras. Do not truncate. Do not split. A chunk that confidently describes the
  first half of a function while having no idea the second half exists is worse than no
  chunk.
- Each chunk carries: file_path, node_type, name, parent_class, start_line, end_line,
  docstring, commit_sha.
- Also emit one summary chunk per class: the class docstring plus its method names, for
  high-level questions.
- Attach the docstring or the comment block immediately above the definition.
- display_text opens with a provenance line so a fragment is never orphaned.

Citation format, exactly: src/models.py:Request.prepare:120-145 @a3f9c21

Then write a stats command that prints, per source type, the chunk count and the token
length distribution (min, p50, p90, max).

Do not write the other three chunkers in this session.
```

**Your check.** Look at actual chunks with your own eyes — this is not optional and it's where you
learn the most in the whole project:

```bash
python -m bug_archaeology.chunking.inspect --type code --sample 20
```

Every chunk must start at a `def` or `class` line. None may end mid-body. Pick the biggest function
in `requests/src/requests/models.py` and confirm it came out as one chunk, not three.

If you set up the `chunk-critic` subagent in phase 0, run it now: `> use chunk-critic on 20 code
chunks and argue they're badly cut`. Reading your own output and thinking it looks fine is not a
review — you wrote it, it will always look fine.

## 2b — Diff chunker

```
Phase 2b: the diff chunker. Code chunker is done. Read CLAUDE.md's principle 1 again.

Build src/bug_archaeology/chunking/diff_chunker.py.

One chunk per (commit, file, hunk). The critical part, and the reason this project works:

THE COMMIT MESSAGE GETS FOLDED INTO THE EMBEDDED TEXT, not stored as metadata beside it.

Concretely, a hunk that reads "+ time.sleep(2)" is unfindable and useless alone. The same
hunk with "workaround for upstream connection reset, see #987" sitting above it in the
embedded text IS the product. Build the text field as: commit message, then the file path,
then the hunk body.

extras: commit_sha, file_path, hunk_index, commit_message, insertions, deletions.

Filter out noise commits before chunking, and log how many you dropped and why:
- commits touching more than 50 files (mass reformats, vendoring)
- paths matching vendored dependencies, generated files, lockfiles, or anything under
  a vendor/ or _vendor/ directory
These produce hundreds of chunks that say nothing and dilute every neighbour they have.

Citation format, exactly: commit a3f9c21 — src/models.py hunk 2 (2022-03-14)
```

**Your check.** Search your chunks for one that has a substantive commit message attached, and read
it end to end. Then check the filter actually fired: `--stats` should tell you how many commits it
dropped. If it dropped zero, the filter isn't running.

## 2c — Thread chunker

```
Phase 2c: the thread chunker, for PR and issue threads. Think hard about this one — where
one argument ends and the next begins is a real judgement call with no clean rule, and
it's the one place in this project where reasoning it through visibly pays off.

Build src/bug_archaeology/chunking/thread_chunker.py.

Two obvious approaches both fail, and I want you to avoid both:
- One chunk per comment fragments discussion into pieces too small to mean anything.
  Half of them are "+1" and "same here."
- One chunk per thread goes too far the other way. A 60-comment thread averaged into one
  embedding is a smear that matches everything vaguely and nothing well.

So: cut at argument boundaries. Consecutive comments from the same author merge. A topic
shift or a rebuttal starts a new chunk. Short reaction-only comments merge into their
neighbour rather than becoming their own chunk.

EVERY chunk carries a header with the thread title, the participants, and the date — so a
fragment pulled out of context is never orphaned.

Each thread ALSO gets exactly one resolution chunk: the title, the final state, the closing
comment, and the commit that closed it. That chunk answers "what did they actually decide,"
which is usually the real question being asked.

Citation formats, exactly:
  PR #1234 — @author, 2022-03-14
  issue #987 — @author, 2021-08-02
```

**Your check.** Read 20 thread chunks. The test is: does each one stand alone? If you can read a
chunk and not know what's being argued about or by whom, the header is wrong. Find a long
contentious thread and check the boundaries landed where the argument actually turned, not every N
comments.

## 2d — Wire up and stats

```
Phase 2d: wire the four chunkers behind one interface and produce the stats report.

A single CLI: python -m bug_archaeology.chunking --all, reading from data/raw.db,
writing chunks to data/chunks.db.

Then a stats report showing, per source type: chunk count, token distribution
(min/p50/p90/max), and the count of chunks flagged as oversized.

Also write an inspect command that prints N random chunks of a given type with their
display_text, so I can read them by hand.
```

**Your check — this is the phase exit criterion.** Read 20 random chunks *of each type* by hand.
Every single one must make sense standing alone. No chunk splits a function mid-body or an argument
mid-sentence. That's four sets of twenty, and it will take you an hour, and it is the highest-value
hour in the project.

### What will probably go wrong in phase 2

**tree-sitter's node types don't match what it expected.** The Python grammar calls things
`function_definition` and `class_definition`, and decorated functions wrap in `decorated_definition`,
which is easy to miss — you'll get functions whose chunk starts *below* the `@property` line. Check
for this specifically.

**Async functions get missed.** They're a distinct node type. Grep your chunks for `async def` and
confirm they're there.

**Token counts are guesses.** If it estimates tokens as `len(text) / 4`, your 1,500-token guardrail is
approximate. That's fine for now, but know that it's approximate — use `tiktoken` if you want it
exact.

**The thread chunker produces either 1 chunk or 40 chunks per thread.** This is the hardest of the
four and the first attempt usually collapses to one of the two failure modes it was told to avoid.
Check the distribution: threads should average somewhere in the 2–6 chunk range. If your p50 is 1,
it's not splitting; if it's 20, it's splitting per comment.

**Everything is slow.** Chunking the full corpus takes a while. Add `--limit` while you're iterating.
You will rewrite this logic thirty times, and that's phase 2 working correctly, not failing.

---

# Phase 3 — The eval set

**Building:** 20 hand-labelled questions and a harness that scores against them.

**Do this before phase 4. Resist every urge to postpone it.** Between "start building retrieval" and
"finish building retrieval" you'll make forty small decisions — is k 60 or 30, do docstrings go in
BM25, do code chunks win ties. Without a scorecard you'll pick whichever one made the last answer you
happened to look at feel slightly better. That's not tuning, that's superstition with extra steps.

### The prompt

```
Phase 3: the eval set. Read the Phase 3 section of PLAN_PART_1_WHAT.md.

Two parts, and the split matters: you DRAFT, I LABEL. A test set the model wrote and the
model grades is a mirror, not a measurement.

Part 1 — draft candidates. Read data/chunks.db and propose 30 candidate questions with
the chunk_ids you believe contain the answer. Spread them deliberately across these six
shapes, roughly 5 each:

| Shape | Example | Tests |
|---|---|---|
| Why is this here | "Why does send() retry three times?" | diffs and threads |
| Has this happened before | "Have we had connection-reset bugs before?" | trail-following |
| Exact identifier | "What raises ChunkedEncodingError?" | BM25's strength |
| Vague paraphrase | "Why is this slow?" | embeddings' strength |
| What was decided | "Why was urllib3 vendored?" | resolution chunks |
| Should refuse | something genuinely NOT in the corpus | abstention |

For each: the question, the gold chunk_ids, the source types needed, and a one-line
correct answer. Write them to eval/candidates.json for me to review — do NOT write
eval_set.json directly, I'm going to edit these by hand.

Part 2 — the harness. eval/run_eval.py that takes any retriever conforming to a simple
interface and scores it on:
- recall@6: fraction of gold chunks appearing in the top 6
- MRR: mean reciprocal rank of the first gold chunk
- citation precision: fraction of cited sources that exist in the retrieved set
- abstention accuracy: on the should-refuse questions, did it refuse

It must run against a STUB retriever that returns random chunks, and print a scorecard.
That proves the harness works before any real retriever exists. Write scorecards to
eval/scorecards/ with a timestamp so I can diff runs.
```

### Your check

**Read all 30 candidates and verify every gold answer yourself.** Open the actual chunk, confirm it
really answers the question. This is tedious and it is the point of the phase — you cannot skip it and
have the numbers mean anything.

Cut down to 20. Then, the rule that saves the whole phase from lying to you: **make sure at least
five are questions you expect to fail.** If your first real run in phase 4 scores 95% across the
board, the test set is too easy and it's telling you a comfortable lie.

```bash
python eval/run_eval.py --retriever stub
```

Random retrieval should score near zero. If the stub scores 40%, your metric is broken — probably
counting a hit when any chunk from the right source type appears.

### What will probably go wrong

**The drafted questions are all the same shape.** Models gravitate to "what does X do" — which your
system doesn't need to be good at. Check the spread yourself against the six-row table.

**The should-refuse questions are secretly answerable.** It'll propose "what is the release date of
Python 4" — trivially refusable and tests nothing. You want questions that *sound* like the corpus
should answer them but don't: "why was the retry backoff changed to exponential in 2019" when no such
change exists. Those are the ones that catch confabulation.

**Gold chunk IDs are wrong.** It'll guess plausibly rather than verify. Spot-check ten of them
against the actual chunk text. If more than one or two are wrong, ask it to re-derive them by
actually searching, and re-check.

---

# Phase 4 — Indexing and hybrid retrieval

**Building:** embeddings, BM25, RRF fusion, and the comparison table that is the whole project.

Plan mode for this one.

### The prompt

```
Phase 4: indexing and hybrid retrieval. Read CLAUDE.md principle 2 and the Phase 4
section of PLAN_PART_1_WHAT.md. Phase 3's harness must run green against the stub first.

Enter plan mode. Propose, let me read, then build.

Build src/bug_archaeology/indexing/ (embedder.py, vector_store.py, bm25_store.py) and
src/bug_archaeology/retrieval/hybrid_retriever.py.

- Embeddings: bge-small-en-v1.5 locally via sentence-transformers, on the `text` field.
  Batch it. Cache by chunk_id so re-running doesn't re-embed unchanged chunks.
- Vector store: LanceDB. Store chunk_id, vector, source_type, authored_at as columns so
  I can filter without a second lookup.
- Keyword: rank_bm25 over the same `text` field. rank_bm25 has no persistence, so pickle
  the fitted index to disk and load it — do not rebuild on every process start.
- Retrieval: top 20 from each, merged with Reciprocal Rank Fusion at k=60, return top 6-10.

Then the part that actually matters. Implement FIVE retrieval configurations behind the
same interface so I can race them on the eval harness:
1. vector-only
2. BM25-only
3. flat RRF
4. quota RRF — run RRF separately within each source type, then take a fixed budget from
   each: 3 code, 3 diff, 4 thread
5. query-adaptive RRF — a cheap classifier that notices "why"/"when"/"who" questions want
   prose and diffs, while "where"/"what" questions want code, and shifts the weights

Why 4 and 5 exist: a code chunk is forty lines of dense identifiers; an issue comment is
"yeah this broke for me too, on 3.9." Different lengths by an order of magnitude, different
vocabulary, similarity scores that aren't comparable. Run flat RRF over that mixture and one
source type sweeps the board — you ask "why does send() retry three times" and get back six
code chunks all showing the retry logic and none saying why it exists. That is the exact
failure this whole project exists to fix.

Finally: a script that runs all five configs against eval/eval_set.json and prints one
markdown table — configs as rows, recall@6 / MRR / citation precision / abstention as
columns.
```

### Your check

```bash
python eval/compare_configs.py
```

Look hard at the table. **Sanity conditions:** BM25-only should beat vector-only on the exact-
identifier questions. Vector-only should beat BM25-only on the vague-paraphrase questions. If
neither is true, something is wired wrong — most likely both configs are secretly returning the same
thing, which happens more often than you'd think.

Then, for every question that failed, trace *why* rather than guessing. If you built the
`retrieval-debugger` subagent, this is what it's for. The answer is often small and fixable — BM25
tokenizing `ChunkedEncodingError` into three useless fragments is a real example, and you will never
find it by staring at the scorecard.

**This table is the deliverable of the entire project.** "Flat RRF got 61% recall@6, source-quota RRF
got 78%, and the whole gap came from 'why' questions where code chunks crowded out the issue threads
that actually held the answer" — that sentence is what you're building. Everything before phase 4
exists to make it honest.

### What will probably go wrong

**The first embedding run downloads ~130MB and looks frozen.** It isn't. Let it finish.

**LanceDB schema is locked by the first write.** Switch embedding models later — bge-small is 384
dimensions, `text-embedding-3-small` is 1536 — and inserts fail with a confusing dimension error. You
have to drop and recreate the table. Expect this when you swap to OpenAI for the final index; it's
not a bug you need to fix, just one you need to recognise.

**rank_bm25 gets rebuilt every run.** It has no save/load of its own. If your retrieval takes 40
seconds to start every time, this is why, and the pickle instruction in the prompt is what prevents
it. Verify it actually happened.

**Quota RRF looks worse than flat RRF at first.** Often because the quotas are wrong for your
question mix, not because the idea is wrong. Try 2/2/2 and 4/2/4 before concluding anything. And if
it genuinely loses, that's a real finding worth writing down, not a failure.

**Everything scores 95%.** Your test set is too easy. Go back to phase 3. This is the outcome that
feels best and means least.

---

# Phase 5 — Answers with citations that hold up

**Building:** the generation layer, plus the verifier that stops it lying.

### The prompt

```
Phase 5: answer generation with verified citations. Read CLAUDE.md principles 4 and 5,
and the Phase 5 section of PLAN_PART_1_WHAT.md.

Build src/bug_archaeology/generation/answer_generator.py and citation_verifier.py, plus
a CLI: python -m bug_archaeology ask "why does X do Y"

The failure this is built to prevent is specific and it WILL happen. The model writes
"this was fixed in PR #1450." It's fluent, correctly formatted, indistinguishable from
every real citation in the answer. And there is no PR #1450. It invented one because a
number was needed and one appeared.

Generation:
- Claude via the Anthropic SDK, temperature 0.
- The prompt restricts the model to the retrieved excerpts and nothing else — no outside
  knowledge about requests, urllib3, or Python.
- Per-source citation formats, exactly as in CLAUDE.md's table.
- An explicit, easy path to say "I don't have enough information to answer this."
- Use prompt caching on the system prompt and citation-format instructions. They're long
  and they never change.

Verification, two layers, both required:
1. Every citation in the answer must resolve to something actually in the retrieved chunk
   set. If any doesn't, reject and regenerate ONCE. If it fails again, downgrade the whole
   answer to "insufficient information." Do not ship a partially-verified answer.
2. Every factual sentence must carry at least one citation. Uncited factual claims do not
   ship.

Log every rejection to eval/scorecards/citation_failures.jsonl with the fabricated
citation and the question, so I can see how often this fires and on what.

Then extend eval/run_eval.py to score end-to-end: citation precision must be 1.0 across
the full eval set, and the should-refuse questions must actually get refused.

Also look at whether the Anthropic Citations API applies here — passing retrieved chunks
as documents gives structural attribution to spans. My verifier DETECTS fabrication after
the fact; that would PREVENT it for quoted material. Check the current API docs rather
than working from memory, tell me what you find, and keep my verifier as a second layer
either way.
```

### Your check

Ask it your two headline questions and read the answers properly:

```bash
python -m bug_archaeology ask "why does this wait two seconds?"
python -m bug_archaeology ask "have connection reset bugs happened before?"
```

**Then verify one citation manually.** Take a cited PR number, open it on GitHub, confirm it says what
the answer claims. Do this at least three times across different source types. This is the moment you
find out whether you built a research tool or a confident liar.

```bash
python eval/run_eval.py --config quota-rrf --end-to-end
```

**Exit criteria: zero fabricated citations across the entire eval set, and the unanswerable questions
actually get refused.** Not "mostly refused." Refused.

### What will probably go wrong

**The verifier is too strict and rejects everything.** It'll do exact string matching on citation
format and reject `PR #1234 — @user, 2022-03-14` because the em-dash is a hyphen. Parse citations
into structured fields and compare those, not raw strings.

**The verifier is too loose and catches nothing.** Test it deliberately: hand it an answer citing
`PR #99999999` and confirm it rejects. If your citation failure log is empty after twenty questions,
assume the verifier is broken, not that the model is honest.

**It refuses everything.** Over-correction in the other direction — the "insufficient information"
path becomes the easy default and it takes it constantly. Check that your answerable questions still
get answered. Abstention accuracy and recall move against each other, and you want both measured.

**The answers are correct but read like a police report.** Fine at this stage. Tone is phase 9.

---

# When phases 0–5 are done

You have a terminal command that answers "why is this code like this" out of thirteen years of
history, with citations that have been checked against what was actually retrieved. That is the
entire intellectual core of the project.

What's deliberately deferred, and the trigger for each:

**Phase 6, link-hop retrieval.** Build it when your "has this happened before" questions score
noticeably worse than the rest. Check the per-shape breakdown in your phase 4 table — if they're
already fine, the diff chunks are carrying enough issue references on their own, and phase 6 might
not earn its place. Decide from the numbers.

**Phase 7, FastAPI and Streamlit.** Build it when you need to show someone who isn't you. The debug
panel showing retrieved chunks is the actual demo, not the chat box.

**Phase 8, incremental reindexing.** ⚠️ **This is CLAUDE.md's non-negotiable principle 3, and
deferring it is a real deviation, not a shortcut I'm hiding.** It's acceptable only while your corpus
stays small enough that a full rebuild is cheap. The trigger is not "when I get around to it" — it's
**the moment you widen past the 300-commit slice to the full history.** At that point a full
re-index on every push becomes genuinely unbearable and the deferral stops being free.

**Full-corpus ingest.** Once phases 0–5 work on the small slice, run the ingest without limits,
overnight. Re-chunk, re-embed, re-run the eval. Expect the numbers to move — more corpus means more
distractors as well as more answers, and recall usually drops a little before you re-tune. That drop
is information, not a regression.

---

# One-line summary

Paste the prompt, run your own check, fix what the check caught, commit, `/clear`, next phase — and
never let a phase pass on the agent's word that it worked.
