# Bug Archaeology Assistant — Part 2: How We Actually Build It

Which tools do what, and why each one earns its place.

---

## First, the uncomfortable bit about using everything

**Piling twelve tools into a project is visible from across the room, and it costs you credibility instead of buying it.**

You asked to use every tool available at full tilt. I want to take that seriously, so let me be straight about how it actually plays out. Picture the moment in an interview where someone looks at your architecture diagram and asks "what's Gmail doing in here?" If the honest answer is "I wanted to show I could wire it up," you've just spent the goodwill you were trying to earn. Reviewers have seen a lot of resume-driven architecture and they recognize it fast.

The version of "full tilt" that actually works is different: take five tools and use them to a depth almost nobody bothers with. Plan mode before every hard phase. Subagents whose entire job is to disagree with you. The API's real primitives instead of a loop around `messages.create`. That reads as someone who went deep. Twelve shallow integrations read as someone who went shopping.

So here's everything sorted into tiers. A and B are where the depth lives. C gets one honest use each, so if you want the line on the resume you have a real story behind it rather than a shrug.

### Tier A — these carry the project

| Tool | What it does here |
|---|---|
| **Claude Code** | The main build agent. Multi-file work, refactors, tests, eval runs. |
| **Anthropic API** | The product's own brain — plus caching, batch, and citations. |
| **GitHub + Actions** | Source of truth, the thing you're indexing, CI, and the reindex trigger. |
| **Cursor** | The tight loop. Inline edits and completions while you're reading code. |
| **Notion** *(connected)* | Phase tracker, decision log, eval results. |

### Tier B — genuinely useful, second string

| Tool | What it does here |
|---|---|
| **Claude in Chrome** | Checking how GitHub actually renders threads the API mangles; clicking through your own Streamlit UI. |
| **Cowork artifacts** | A live eval dashboard that re-pulls from Notion every time you open it. |
| **Cowork skills** | Freezing repeated workflows so they run the same way every time. |
| **Scheduled tasks** | Daily progress nudge, weekly eval regression run. |
| **MCP — as the author** | Shipping the assistant *as* an MCP server. See below; this is the best idea in the plan. |

### Tier C — thin. Use lightly or skip without guilt.

| Tool | Honest read | The one legitimate use |
|---|---|---|
| **Slack** | ⚠️ *Not authorized yet.* You have no team, so there's no collaboration value to capture. | Make a personal workspace. Pipe indexer runs and eval regressions into `#archaeology-ops`. Good demo footage, and there's something fitting about the project keeping its own institutional memory. |
| **Gmail** *(connected)* | Thin. Nothing about building this needs email. | A weekly digest to yourself of eval movement. Later, outreach when you're actually job hunting. |
| **Figma** | ⚠️ *Not authorized yet.* Mermaid renders natively in GitHub and takes five minutes. | Skip, unless you want one nice architecture diagram for the demo video. |

**Slack and Figma both need authorizing** in your claude.ai connector settings before I can touch them. Notion and Gmail are already live.

---

## The recursive move — do this one

**Wrap the finished assistant as an MCP server, connect it to Claude Code and Cursor, and point it at this project's own history.**

Why this is worth more than it costs:

You stop demoing the tool and start depending on it. By week six you'll be asking your own assistant why you wrote the diff chunker the way you did, and it will answer you out of your own commit messages from week two. That's a different kind of proof than a screenshot.

It also creates a loop that feeds itself. Knowing the tool will read your commit messages makes you write real ones. Real commit messages make a better corpus. A better corpus makes a better demo. Round and round.

And the story is just better. "I built a RAG system" is a sentence thousands of people will say this year. "I built it, exposed it over MCP, and it lives in my editor answering questions about its own history" is a sentence people repeat to someone else.

The build is small: a thin server exposing two tools — `ask_history(question, repo)` and `why_this_code(file_path, line_range)` — wrapped around the FastAPI endpoints you already built in Phase 7.

---

## Day zero, before any project code

**Four setup jobs that each prevent a specific kind of pain later.**

**Write `AGENTS.md` and have `CLAUDE.md` import it.** This is the highest-leverage file in the repo because it's read at the start of every single session. It's where the four non-negotiables live so the agent stops relitigating them. One file, both tools, no divergence — which matters, because two files drifting apart is worse than either file alone. Contradictory instructions mean the agent picks one arbitrarily and you can't tell which.

**Split the deep detail into `.claude/rules/` with path scoping.** A rule tagged `paths: ["src/chunking/**"]` only loads when the agent touches chunking code. This keeps the always-loaded file short, and short matters: past roughly 200 lines, adherence measurably drops. You get depth without paying for it in every unrelated session.

**Set up Notion.** One database for phases (status, exit criteria, blockers), one for decisions — the decision, what you rejected, why, and the date. That second database is the one that pays off. Write the entry the day you make the call, while you still remember the alternative you dismissed, because six weeks later in an interview you'll remember the conclusion and not the reasoning.

**Write four slash commands and three subagents.**

| Command | What it does |
|---|---|
| `/chunk-review` | Pulls 20 chunks of a given type, prints them, argues about whether they stand alone |
| `/run-eval` | Runs the harness, diffs against the last scorecard, flags anything that got worse |
| `/adr` | Turns the current conversation into a decision record and pushes it to Notion |
| `/spec-check` | Diffs the code against the four principles and reports drift |

The subagents, and the point of each:

- **`chunk-critic`** — read-only, and adversarial on purpose. You hand it chunks, it argues they're badly cut. An agent that only agrees with you is expensive autocomplete. You want something that makes you defend your boundaries.
- **`eval-writer`** — reads the corpus and drafts candidate questions with their known sources. Gets you to twenty labelled pairs in an afternoon instead of a day.
- **`retrieval-debugger`** — given a question that failed, traces *why* the right chunk didn't surface. Embedding? BM25 tokenization? RRF rank? Guessing at this wastes hours.

Plus hooks in `.claude/settings.json` to run ruff and pytest on every write. Cheap, and it catches drift the same minute it happens rather than three days later.

---

## Phase by phase

### Phase 0 — Foundation

**Use plan mode before you let anything write files.**

Shift+Tab into plan mode, have it propose the scaffold, read the proposal, *then* let it build. This sounds like a formality and isn't. The difference between a generated project and a designed one is almost entirely whether you looked at the plan before the files existed — because once files exist, you review them one at a time and never see the shape of the whole thing.

Cursor for the small stuff: `pyproject.toml` edits, gitignore. Notion gets all nine phases seeded as rows with their exit criteria. And set up a scheduled task for 9am daily that reads the board and asks what's blocked — accountability you don't have to remember to apply.

### Phase 1 — Ingestion

**Ask explicitly for the failure handling, because you won't get it otherwise.**

Agents write happy-path code by default. If you say "write me a GitHub ingester" you'll get one that works beautifully until request 4,999 and then loses everything. So say the words: resumable, idempotent, checkpointed after every batch. Then check that it actually is.

Kick the full ingest off overnight. Rate limits resolve themselves while you sleep, which is the only pleasant thing about rate limits.

Then spot-check with Claude in Chrome: open a real issue thread in the browser and compare it against what you stored. This catches a specific and annoying class of bug — the API's representation of quoted replies, edits, and code blocks doesn't match what you'd guess from looking at the rendered page, and you'd rather find that out now than in Phase 4 when your retrieval is mysteriously bad.

### Phase 2 — Chunking ⭐

**This is the phase to use the most Claude and accept the least of its first answer.**

Plan mode for each chunker separately — four sessions, not one. Don't try to hold all four strategies in a single context window; quality degrades and the fourth chunker ends up as a copy of the first.

After each one, run `chunk-critic` on twenty samples and make it argue the chunks are bad. Fix whatever lands. This adversarial pass is worth more than any amount of reading your own output and thinking it looks fine, because you wrote it and it will always look fine to you.

Turn on extended thinking for the thread chunker specifically. Deciding where one argument ends and the next begins is a genuine judgement call with no clean rule, and it's the one place in this project where giving the model room to reason visibly pays off.

Cursor's Composer for the fiddly tree-sitter node-traversal code — you're iterating in seconds there and a full agent turn is too slow.

And write an ADR after each chunker via `/adr`. Four decision records here. **These are your interview answers, captured while the reasoning is still fresh.** Reconstructing them in six weeks produces something vaguer and less convincing.

### Phase 3 — The test set

**The subagent proposes; you label. Never the other way round.**

`eval-writer` reads the corpus and drafts candidate questions with their sources. That's a huge time save on the tedious part. But you personally verify every single gold answer, because a test set the model wrote and the model grades is a mirror, not a measurement. It will tell you your system is excellent, and it will be wrong, and you won't find out until someone asks.

Keep the set in a Notion database — easier to edit than raw JSON, and it exports cleanly to `eval/eval_set.json` in CI.

Use the Batch API for eval runs. Twenty questions across five retrieval configurations, run repeatedly as you tune, adds up faster than you'd think. Batch is half price and you don't need the answers in the next four seconds.

### Phase 4 — Indexing and retrieval

**Script the sweep so you're not babysitting it, and never guess at a failure.**

Claude Code's headless mode (`claude -p`) can run all five retrieval configurations, collect the scorecards, and hand you a table. Do that rather than running them by hand and copying numbers.

Every failed question goes to `retrieval-debugger`. Not "hm, probably the embeddings" — trace it. The answer is often something small and fixable, like BM25 tokenizing `ChunkedEncodingError` into three useless fragments, and you will not find that by staring at the scorecard.

Build the Cowork artifact here: a live dashboard reading results from Notion, showing the comparison table and a breakdown by question shape, refreshing every time it's opened. That becomes a link you can send someone, which beats a screenshot in a README by a wide margin.

Turn on prompt caching while you iterate. You'll re-send the same retrieved chunks over and over while tuning the generation prompt, and paying full price for identical context every time is just waste.

### Phase 5 — Answers and citations

**Look hard at the Citations API here, because it changes the claim you get to make.**

Pass retrieved chunks in as documents and you get back answers with structural attribution to spans in those documents. The distinction that matters: your Phase 5 verifier *detects* fabricated citations after the fact. This *prevents* them for quoted material. "I check for hallucinated citations" and "hallucinated citations are structurally impossible in my system" are different sentences and the second one is much stronger. Keep the verifier as a second layer anyway — belt and braces on the one thing the project can't afford to get wrong. Check the current API docs for the exact shape.

Cache the system prompt and the citation-format instructions. They're long and they never change, so this is real money saved on every query and a legitimate engineering line for the README.

Temperature 0 to 0.2. And run `/security-review` before anything touches the network — you're holding a GitHub token and it would be a stupid way to have a bad week.

### Phase 6 — Following the trail

**Plan mode, and be genuinely willing to throw it away.**

This phase has the highest chance of any in the project of adding noise rather than signal, so design it before you build it. Then run the eval harness before and after.

If the numbers don't move, cut it and document the negative result. That's not a failure to report — a candidate who removed a clever feature because their own measurements said it didn't help is demonstrating something most candidates can't.

### Phase 7 — Making it usable

Claude Code can move fast on the FastAPI layer; it's well-trodden ground.

Then use Claude in Chrome to actually test the Streamlit UI — click through it, read the console for errors, and verify that citation deep-links land on the right lines rather than roughly the right file. Faster than doing it by hand, and it catches the off-by-a-few-lines problems that make a demo look sloppy.

Architecture diagram in Mermaid, in the README, where GitHub renders it for free.

### Phase 8 — Incremental reindex

GitHub Actions runs the reindex workflow. Add the Claude Code GitHub Action for automated review on your own PRs — useful in itself, and it's evidence you know the tooling.

Pipe every reindex into Slack with its timing and cost. **That log is where your "incremental costs 4% of a full rebuild" number comes from** — measured over dozens of real runs rather than estimated once, which is the difference between a claim and a finding.

Schedule the eval harness weekly, so a change that quietly breaks recall gets caught in days rather than discovered in an interview.

### Phase 9 — Polish

Let Claude Code draft the README, then rewrite the narrative sections yourself. **Don't let it write the pitch.** The kitchen-note analogy is yours, it's better than what a model will generate, and it's the part that makes non-technical people understand the project in one breath. A model will produce something competent and forgettable in its place.

Ship the Cowork artifact as the public results dashboard. Build the MCP wrapper. Package a `bug-archaeology-demo` skill so your live demo runs the same way every time and never wanders off script.

Then Gmail, for the one thing it's actually good for: writing to engineers whose repos you indexed. People genuinely like hearing their project was used well, and it's a warmer opening than a cold application.

---

## What "using Claude fully" actually comes down to

Not the number of logos on the diagram. Four habits:

**Plan mode before every hard phase.** Most people prompt and hope. Designing first, in a mode built for exactly that, is the single largest quality difference available to you and it costs about ten minutes.

**Subagents that argue with you.** `chunk-critic` and `retrieval-debugger` exist to disagree. An agent that only ever agrees is autocomplete you're overpaying for.

**The API's real primitives.** Caching, batch, citations — not a loop around `messages.create`. This is the exact area interviewers probe when they want to know whether you've actually shipped something, and most candidates have nothing to say.

**Dogfooding through MCP.** The project becomes part of how you work rather than a thing you built once and screenshotted.

---

## Where to start

Say go and I'll do the whole day-zero setup now: `AGENTS.md`, the trimmed `CLAUDE.md`, four path-scoped rule files, four slash commands, three subagent definitions, the hooks, and the repo scaffold. Then the two Notion databases.

Two things need you first: **confirm the target repo** (`psf/requests` unless you'd rather something else) and **authorize Slack and Figma** if you want them in the mix. Neither is load-bearing.
