# Phase 0 — Foundation: the complete walkthrough

**Locked decisions (from our conversation):**

- Corpus: `psf/requests`
- Environment: Windows + WSL2 (Ubuntu)
- Mode: you type the commands, I explain them

**What "done" looks like.** You can delete your project folder, re-clone it from GitHub, run
*one* command, and be back to a working environment with `pytest` passing. Nothing else in Phase 0
matters as much as that sentence.

**Time:** ~2–3 hours if nothing fights you. Steps 1 and 2 are the only slow parts.

---

## How to read this

Every step has three parts:

- **What** — one line, the goal.
- **How** — the exact commands. Type them in order.
- **Why** — what breaks if you skip it. Read this part; it's the part you'll be asked about later.

A `$` at the start of a line means "type this in the terminal." Don't type the `$`.

---

# Step 1 — Install WSL2

### What

Get a real Ubuntu Linux running inside Windows.

### How

Open **PowerShell as Administrator** (Start menu → type "PowerShell" → right-click → Run as
administrator). Then:

```powershell
wsl --install -d Ubuntu-22.04
```

Reboot when it tells you to. On first launch it asks for a username and password — pick something
short and lowercase, like your first name. **The password won't show as you type it. That's normal,
not a broken keyboard.** Write it down; you need it for `sudo`.

Then verify:

```powershell
wsl -l -v
```

You want to see `Ubuntu-22.04` with `VERSION 2`. If it says `VERSION 1`, run
`wsl --set-version Ubuntu-22.04 2`.

From now on, **every command in this guide runs inside Ubuntu**, not PowerShell. Open it from the
Start menu ("Ubuntu") or by typing `wsl` in any terminal.

First thing inside Ubuntu:

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y git build-essential curl
```

### Why

Here's the failure mode. Around Phase 2 you'll `pip install tree-sitter`, and on native Windows pip
can't find a prebuilt wheel for your exact Python version, so it tries to compile C source. That
needs Microsoft C++ Build Tools — a 6 GB download — and even then the error you get is a wall of
`LNK2001: unresolved external symbol` that means nothing to you. Same story with LanceDB's Rust
bits. On Linux the wheel just downloads and installs in four seconds.

You'd spend a whole evening on build errors that have nothing to do with retrieval, which is
miserable and teaches you nothing. Twenty minutes now buys that back.

**One rule that will save you real pain:** keep your project inside the Linux filesystem
(`/home/you/...`), **not** in `/mnt/c/Users/...`. Reading files across the Windows↔Linux boundary is
roughly 10× slower. When you're walking 7,000 commits of git history, that's the difference between
40 seconds and 7 minutes, every single run.

---

# Step 2 — Install `uv` (your Python manager)

### What

Install one tool that handles Python versions, virtual environments, and package installs.

### How

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc
uv --version
```

If `uv --version` says "command not found", close and reopen the Ubuntu window and try again.

Then install Python 3.11:

```bash
uv python install 3.11
```

### Why

**Ubuntu 22.04 ships Python 3.10, your project needs 3.11, and the traditional ways of fixing that
are all traps.**

The usual advice is to add the "deadsnakes" PPA, or install `pyenv` and compile Python from source
(ten minutes of scrolling compiler output, and it silently fails if you're missing `libssl-dev`,
which you find out three weeks later when `pip` can't do HTTPS). Or you `sudo pip install` into the
system Python and eventually break `apt`, because Ubuntu's own tools are written in Python.

`uv` downloads a prebuilt Python 3.11 into your home directory in about eight seconds and touches
nothing system-wide. It also replaces `pip`, `venv`, and `pip-tools`, so you learn one tool instead
of four. It's made by the same people as `ruff`, which you're installing later anyway.

> Small note: `uv` isn't in your CLAUDE.md stack list. It's a workflow tool, not an architecture
> choice — nothing about the retrieval system depends on it, and `pip` works identically if you
> prefer. Flagging it because we agreed to flag deviations.

---

# Step 3 — Create the repo skeleton

### What

Make every folder and empty file from the layout in `CLAUDE.md`, in one go.

### How

```bash
mkdir -p ~/projects && cd ~/projects
mkdir bug-archaeology && cd bug-archaeology
git init -b main
```

Now create the whole tree. Copy this entire block and paste it into the terminal at once:

```bash
mkdir -p src/{ingestion,chunking,indexing,retrieval,generation,api,mcp,db}
mkdir -p eval/scorecards tests frontend corpus
mkdir -p .claude/{commands,agents} .github/workflows

# make each src folder a real Python package
for d in ingestion chunking indexing retrieval generation api mcp db; do
  touch "src/$d/__init__.py"
done

# empty module files, so the shape of the project is visible from day one
touch src/ingestion/{git_walker,github_client,raw_store,link_extractor}.py
touch src/chunking/{base,code_chunker,diff_chunker,thread_chunker,models}.py
touch src/indexing/{embedder,vector_store,bm25_store,incremental}.py
touch src/retrieval/{hybrid_retriever,link_hop}.py
touch src/generation/{answer_generator,citation_verifier}.py
touch src/api/main.py src/mcp/server.py src/db/state.py
touch frontend/streamlit_app.py eval/run_eval.py
touch tests/__init__.py
```

Check it worked:

```bash
find src -type f | sort
```

You should see 20-ish `.py` files.

### Why

**Empty files are a to-do list you can't lose.** When you sit down on day 9 and run `find src -type
f -empty`, the answer *is* your remaining work. Compare that to trying to remember whether you ever
wrote the link extractor.

The `__init__.py` files are the non-obvious bit. Python only treats a folder as an importable
package if it's registered as one, and `__init__.py` — even completely empty — is what does that
registration. Without it, `from chunking.code_chunker import CodeChunker` fails with
`ModuleNotFoundError`, and the error points at the import line rather than at the missing file, so
you stare at a correct-looking import wondering what's wrong with it.

`corpus/` is where `psf/requests` will land in Step 8. Keeping it inside the repo but gitignored
means every path in your code can be relative — no absolute `/home/rishi/...` strings that break
the moment anyone else runs this.

---

# Step 4 — Write `pyproject.toml`

### What

One file that declares what your project is called, what Python it needs, what libraries it uses,
and how your tools are configured.

### How

Create the file:

```bash
nano pyproject.toml
```

(`nano` is a plain text editor in the terminal. Paste with **right-click** or `Ctrl+Shift+V`. Save
with `Ctrl+O` then `Enter`. Exit with `Ctrl+X`.)

Paste this:

```toml
[project]
name = "bug-archaeology"
version = "0.1.0"
description = "Retrieval over a repository's full history — answers why code is the way it is."
requires-python = ">=3.11"

dependencies = [
    # ingestion
    "GitPython>=3.1.43",
    "httpx>=0.27.0",
    # indexing + retrieval
    "rank-bm25>=0.2.2",
    "lancedb>=0.13.0",
    "pyarrow>=17.0.0",
    # generation
    "anthropic>=0.40.0",
    # plumbing
    "pydantic>=2.9.0",
    "python-dotenv>=1.0.1",
    "tqdm>=4.66.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.3.0",
    "pytest-cov>=5.0.0",
    "ruff>=0.7.0",
    "pre-commit>=4.0.0",
]
app = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.32.0",
    "streamlit>=1.39.0",
]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
addopts = "-v"

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B"]
```

### Why — read this section slowly, it's the one with real content

**`pyproject.toml` is the answer to "what does this project need to run," written down where a
machine can act on it instead of living in your head.**

Without it, the failure mode is this: it's November, you've moved to a new laptop, you clone your
own repo, run it, and get `ModuleNotFoundError: No module named 'lancedb'`. So you install lancedb.
Then it wants pyarrow. Then anthropic. Twenty minutes of whack-a-mole, and you *still* don't know if
you got the right versions, because the lancedb you just installed is six months newer than the one
you built against and quietly renamed a method you use. Recruiters clone repos. This is exactly
where a project stops looking finished.

Now the sections, one at a time:

**`requires-python = ">=3.11"`** — a hard gate. If someone tries to install this on Python 3.9 they
get a clear error immediately, instead of a baffling syntax error deep inside your code.

**`dependencies`** — the libraries needed for the system to actually *run*. `>=3.1.43` means "this
version or newer." A tighter pin (`==`) is safer for reproducibility but you'd be manually bumping
versions all project; `>=` is the right tradeoff for a project at this stage.

**`optional-dependencies`** — split into groups so you can install only what you need.
`dev` is testing and linting; `app` is the web layer you don't need until Phase 7. Someone who just
wants to *use* your library shouldn't have to download Streamlit.

**Where's tree-sitter?** Deliberately left out until Phase 2 — flagging that, since your plan lists
it in the stack. Two reasons. First, Phase 0's exit criterion is "pytest runs green," and adding a
package with C extensions is the single most likely thing to make Step 7 fail for reasons unrelated
to anything you did. Second, `tree-sitter-languages` (named in CLAUDE.md) is no longer maintained
against current `tree-sitter` versions and will fight you; the live path is `tree-sitter` plus the
official `tree-sitter-python` grammar package. That's a real decision, it deserves an ADR, and
Phase 2 is when to make it. Not now.

**`[build-system]`** — tells `pip`/`uv` *how* to turn your folder into an installable package. You
will never touch this again.

**`[tool.setuptools.packages.find] where = ["src"]`** — this makes the folders *inside* `src/` the
top-level packages, so you write `from chunking.code_chunker import ...`, not
`from src.chunking.code_chunker import ...`. It matches the layout in your CLAUDE.md exactly.

One honest caveat, and this is your call to make: names like `api`, `db`, and `indexing` are generic
top-level names, and if you ever `pip install` a real package called `api`, one will shadow the
other and you'll get a genuinely confusing bug. The standard fix is one more folder —
`src/bug_archaeology/chunking/...` — which makes every import unambiguous but means editing the
layout section of CLAUDE.md. **Settled:** we're following your CLAUDE.md as written. **Open, and
yours to decide:** whether to add that wrapper folder. If you want it, say so now — it's a 30-second
change today and an annoying find-and-replace in three weeks.

**`[tool.pytest.ini_options] pythonpath = ["src"]`** — this is the line that makes tests just work.
It tells pytest to look inside `src/` when resolving imports, so `from chunking.base import Chunk`
works in a test file without you doing anything clever.

**`[tool.ruff]`** — ruff is your linter and formatter (Step 9). Those `select` codes turn on:
`E`/`F` real errors like unused variables and undefined names, `I` automatic import sorting, `UP`
"you're writing this the old way, 3.11 has a nicer syntax," `B` common bug patterns like using a
mutable default argument.

---

# Step 5 — Create the environment and install

### What

Build an isolated Python environment for this project and install everything into it.

### How

```bash
uv venv --python 3.11
source .venv/bin/activate
uv pip install -e ".[dev]"
```

Your prompt should now start with `(bug-archaeology)`. Confirm:

```bash
python --version     # 3.11.x
which python         # .../bug-archaeology/.venv/bin/python
```

**Every time you open a new terminal to work on this, you must run `source .venv/bin/activate`
first.** Forgetting this is the #1 source of "but I installed it!" confusion. Optional shortcut:

```bash
echo "alias ba='cd ~/projects/bug-archaeology && source .venv/bin/activate'" >> ~/.bashrc
source ~/.bashrc
```

Now typing `ba` from anywhere takes you there, activated.

### Why

**A virtual environment is a private box of libraries that belongs to this project only.**

Picture what happens without one. You install `pydantic 2.9` globally for this project. Next month
you start something else that needs `pydantic 1.10`, so you install that — and now bug-archaeology
is broken, because pydantic 2 and 1 have incompatible APIs. You didn't touch bug-archaeology. It
broke anyway. Debugging that is genuinely awful because the code you're looking at is fine.

The venv is just a folder (`.venv/`) with its own Python and its own `site-packages`. "Activating"
it puts that Python first on your PATH. Delete the folder and it's like the install never happened.

**The `-e` flag means "editable install."** Without it, pip *copies* your `src/` into
`site-packages`, so when you edit `code_chunker.py` and rerun, nothing changes — you're running last
week's copy. You will lose an hour to this exactly once. With `-e`, pip drops in a pointer to your
actual folder, so every save is live.

**`".[dev]"`** means "install this project (`.` = here) plus the `dev` extras." The quotes matter;
some shells eat the square brackets.

---

# Step 6 — Add `.gitignore`

### What

Tell git which files to never track.

### How

```bash
nano .gitignore
```

```gitignore
# Python
__pycache__/
*.py[cod]
*.egg-info/
.venv/
venv/

# Environment secrets — NEVER commit this
.env

# Project data (large, regenerable)
corpus/
data/
*.db
*.sqlite3
.lancedb/
lancedb/

# Tooling caches
.pytest_cache/
.ruff_cache/
.coverage
htmlcov/

# Editors / OS
.vscode/
.idea/
.DS_Store
```

### Why

**Three different disasters, one file.**

The one that actually hurts: your Anthropic API key lives in `.env`. Commit that once to a public
repo and bots scrape it within minutes — GitHub's secret scanner is fast but not instant, and
you'll get a bill. There's no undo; git keeps history, so "deleting it in the next commit" doesn't
help. The key has to be revoked.

The one that's merely embarrassing: `corpus/` will hold the full clone of `psf/requests`, and
`.lancedb/` will hold your embeddings. That's hundreds of megabytes of *regenerable* data. GitHub
starts warning past 50 MB per file and hard-refuses at 100 MB, and by the time you hit that the
files are already in your history, so you have to rewrite history to get rid of them.

The quiet one: `__pycache__/` is compiled bytecode that changes constantly. Left untracked-but-
visible, every `git status` is 40 lines of noise and you stop reading it — which is how you miss
the actual change you didn't mean to make.

Verify it's working:

```bash
git status --short
```

You should see your source files and *not* see `.venv`.

---

# Step 7 — A trivial test, and `pytest` green ✅

### What

Hit the Phase 0 exit criterion.

### How

```bash
nano tests/test_smoke.py
```

```python
"""Smoke test: proves the environment and package layout actually work.

If this passes, Phase 0's exit criterion is met.
"""


def test_python_version():
    import sys

    assert sys.version_info >= (3, 11), "Bug Archaeology requires Python 3.11+"


def test_core_dependencies_import():
    import anthropic  # noqa: F401
    import git  # noqa: F401  (GitPython imports as `git`)
    import lancedb  # noqa: F401
    import pydantic  # noqa: F401
    from rank_bm25 import BM25Okapi  # noqa: F401


def test_src_packages_are_importable():
    """The src/ layout resolves — this is what pythonpath=['src'] buys us."""
    import chunking  # noqa: F401
    import generation  # noqa: F401
    import indexing  # noqa: F401
    import ingestion  # noqa: F401
    import retrieval  # noqa: F401
```

Run it:

```bash
pytest
```

You want:

```
tests/test_smoke.py::test_python_version PASSED
tests/test_smoke.py::test_core_dependencies_import PASSED
tests/test_smoke.py::test_src_packages_are_importable PASSED

=========== 3 passed in 0.4s ===========
```

**If something fails:**

| Error | Cause | Fix |
|---|---|---|
| `ModuleNotFoundError: chunking` | missing `__init__.py`, or `pythonpath` not set | rerun the `for d in ...` loop from Step 3; check Step 4's pytest block |
| `ModuleNotFoundError: lancedb` | venv not activated | `source .venv/bin/activate` |
| `pytest: command not found` | same | same |

### Why

**A trivial test isn't about testing anything — it's a tripwire that tells you the plumbing is
connected.**

`test_src_packages_are_importable` is the one doing real work. It's asserting that a file in
`tests/` can see the code in `src/`, which is the single most common way a Python project is quietly
broken. Without it you'd discover the problem on day 4, mid-way through writing the chunker, and
you'd assume the bug was in your chunker — because that's what you just wrote. You'd debug the wrong
file for an hour.

`test_core_dependencies_import` catches the other classic: a package that installs cleanly but
fails at import time because a system library is missing. Finding that out in 0.4 seconds is better
than finding out during your first indexing run.

The `# noqa: F401` comments tell ruff "yes, I know this import is unused — that's the point."

---

# Step 8 — Clone the corpus

### What

Get the full history of `psf/requests` onto disk.

### How

```bash
git clone https://github.com/psf/requests.git corpus/requests
```

Sanity-check what you got:

```bash
cd corpus/requests
git log --oneline | wc -l              # ~6,489 commits
git log -1 --format=%cd                # most recent commit date
git log --oneline --grep="#" | wc -l   # ~1,842 commits reference an issue or PR
grep -rn "Retry" src/requests/adapters.py | head   # your demo material
cd ../..
```

That third number is the one that matters: **1,842 commits explicitly name an issue or PR number.**
That's your link graph for Phase 6 — 1,842 ready-made edges from "this code changed" to "here's the
conversation about why."

### Why — this is the choice the whole project rests on

**A "why is this code here" system is only impressive if the answers are surprising, and `requests`
has fifteen years of surprising answers.**

Concretely, here's the demo. Someone reads `requests/adapters.py`, sees retry and backoff logic, and
thinks "why is this so convoluted, urllib3 already retries." Your system should come back with: it's
convoluted because of a specific 2015 issue where connection pooling interacted badly with
`Retry-After` headers, here's the thread, here's the maintainer's comment explaining the tradeoff,
here's the commit. That's an answer no amount of reading the current source gets you — the reason
lives in a 2015 conversation, not in the file.

The alternative — using a repo you wrote yourself — fails in a specific way. You can't tell whether
the system found a real answer or made one up, because you're the only person who knows the truth
and you already believe it. With `requests`, you can go read the actual issue thread and check. That
verification ability is what makes your eval set in Phase 3 possible at all.

**Do not use `--depth 1`.** That's the "shallow clone" flag, and it downloads only the most recent
commit. Your entire project is the history. A shallow clone of `requests` gives you a system that
can only tell you what the code looks like today — which is what `grep` is for.

The full clone is around 60 MB. That's fine, and it's gitignored.

---

# Step 9 — Ruff + pre-commit hooks

### What

Auto-format and lint your code every time you commit.

### How

```bash
nano .pre-commit-config.yaml
```

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.7.4
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v5.0.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-toml
      - id: check-added-large-files
        args: [--maxkb=5000]
      - id: check-merge-conflict
      - id: detect-private-key
```

Install and test:

```bash
pre-commit install
pre-commit run --all-files
```

The first run is slow (it downloads the hooks) and will probably *fail* while fixing whitespace in
your files. That's the expected outcome — it fixed them. Run it again and it passes.

### Why

**Hooks are for the mistakes you can't catch by being careful, because being careful is exactly what
fails at 1am.**

`check-added-large-files` is the one that will actually save you. Phase 4 produces a LanceDB
directory of embeddings. One misconfigured path, one `git add .`, and you've committed 400 MB. Git
will let you. GitHub won't, and by then the file is baked into your history and you're reading Stack
Overflow posts about `git filter-repo` at midnight. The hook just refuses the commit and tells you
which file. Two seconds instead of two hours.

`detect-private-key` is the same insurance for the API key that `.gitignore` already covers. Two
layers, because that one is unrecoverable.

`ruff --fix` and `ruff-format` are the boring ones: consistent import order, no unused imports,
consistent style. The value isn't beauty — it's that your `git diff` only ever shows changes you
*meant*, instead of a mix of real edits and formatting churn. When every diff is signal, reviewing
your own work gets much faster.

`pre-commit install` writes a script into `.git/hooks/`, which is why it has to be re-run on a fresh
clone — hence Step 10.

---

# Step 10 — The one-command bootstrap

### What

A single script that takes a fresh clone to a working environment. This is a Phase 0 exit criterion.

### How

```bash
nano bootstrap.sh
```

```bash
#!/usr/bin/env bash
# Bootstrap Bug Archaeology from a fresh clone.
#   ./bootstrap.sh
set -euo pipefail

CORPUS_REPO="https://github.com/psf/requests.git"
CORPUS_DIR="corpus/requests"

echo "==> [1/5] Checking for uv"
if ! command -v uv &> /dev/null; then
    echo "    uv not found. Installing..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi

echo "==> [2/5] Creating virtual environment (Python 3.11)"
uv venv --python 3.11

echo "==> [3/5] Installing dependencies"
uv pip install -e ".[dev]"

echo "==> [4/5] Installing git hooks"
.venv/bin/pre-commit install

echo "==> [5/5] Cloning corpus: $CORPUS_REPO"
if [ -d "$CORPUS_DIR/.git" ]; then
    echo "    Already present, pulling latest."
    git -C "$CORPUS_DIR" pull --ff-only
else
    git clone "$CORPUS_REPO" "$CORPUS_DIR"
fi

echo ""
echo "==> Verifying"
.venv/bin/pytest -q

echo ""
echo "Done. Activate with:  source .venv/bin/activate"
```

Make it runnable:

```bash
chmod +x bootstrap.sh
```

### Why

**"How do I set this up?" should have a one-line answer, and the only way to guarantee that is to
write the answer down as a script that you actually run.**

The failure mode here is subtle and very common. You write beautiful setup instructions in your
README. Two months later you re-clone and follow them — and step 4 doesn't work, because back in
week 3 you ran some command to fix something and never wrote it down. Your README describes a
project that no longer exists. A script can't drift like that, because it's the thing you run.

Note it ends with `pytest`. A bootstrap that finishes without verifying anything is a bootstrap
that can lie to you.

`set -euo pipefail` is four safety switches: stop on the first error (`-e`), stop on undefined
variables (`-u`), and don't let a failure in the middle of a pipeline get swallowed (`pipefail`).
Without `-e`, if the dependency install fails, the script cheerfully carries on and prints "Done."

The `.venv/bin/pytest` path (rather than plain `pytest`) is deliberate: a script can't reliably
"activate" an environment for its parent shell, so we call the venv's executables directly.

---

# Step 11 — Verify the exit criteria properly

### What

Prove it, don't assume it.

### How

```bash
cd ~/projects
git clone ~/projects/bug-archaeology /tmp/ba-test
cd /tmp/ba-test
./bootstrap.sh
```

If that ends in `3 passed`, Phase 0 is genuinely done. Clean up:

```bash
cd ~ && rm -rf /tmp/ba-test
```

### Why

**This is the only step that actually tests the exit criterion, because it's the only one that
starts from nothing.**

Everything up to now worked in a folder where you'd already installed things by hand. Cloning to
`/tmp` strips all of that away. If you forgot to commit `pyproject.toml`, or `.gitignore` is
accidentally excluding a file you need, this is where you find out — in 90 seconds, on your own
machine, rather than when someone else tries your repo and it doesn't work.

(You'll need to `git add . && git commit` first if you haven't — the clone only sees committed
files, which is part of the point.)

---

# Step 12 — First commit

```bash
cd ~/projects/bug-archaeology
git add .
git status          # LOOK at this. No .venv, no corpus/, no .env.
git commit -m "Phase 0: foundation — scaffold, deps, hooks, bootstrap, smoke tests"
```

Then create an empty repo on GitHub (no README, no .gitignore — you have both) and:

```bash
git remote add origin https://github.com/YOUR_USERNAME/bug-archaeology.git
git push -u origin main
```

---

# Step 13 — `.cursorrules` and the `.claude/` directory

### What

Give your AI tools the same rulebook so they stop arguing with each other.

### How

```bash
cp CLAUDE.md .cursorrules
```

Then the four slash commands. Each is a markdown file whose contents become a prompt:

```bash
cat > .claude/commands/spec-check.md <<'EOF'
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
EOF

cat > .claude/commands/chunk-review.md <<'EOF'
Sample 20 chunks of source type $ARGUMENTS from the current index and print each one in full.

For each, answer: could someone who has never seen this repository understand what this chunk
is about from the chunk alone? A chunk fails if it needs surrounding context to make sense.

Check specifically:
- code: starts and ends at a real function/class boundary; never truncated mid-body
- diff: the commit message is present in the embedded text, not just the metadata
- pr_thread / issue_thread: author, date, and thread title are carried on the chunk
- all: the chunk carries enough to build its citation string per the CLAUDE.md table

End with a count of passes and failures and the single worst chunk, quoted.
EOF

cat > .claude/commands/run-eval.md <<'EOF'
Run `python eval/run_eval.py` and compare the result to the most recent scorecard in
eval/scorecards/.

Report: per-question pass/fail, aggregate retrieval recall, citation-verification pass rate,
and abstention accuracy on the questions whose expected answer is "insufficient information".

Then diff against the previous scorecard and list every question that changed state. Call out
regressions first and loudly. Write the new scorecard to eval/scorecards/ with today's date.
EOF

cat > .claude/commands/adr.md <<'EOF'
Write an architecture decision record from this conversation.

Format:
  # ADR-NNN: <title>
  Date | Status (accepted/superseded)
  ## Context      — what forced a decision
  ## Decision     — what we chose, one sentence
  ## Alternatives — each option actually considered, and the specific reason it lost
  ## Consequences — what this makes easy, and what it makes hard or expensive to change later

Be concrete about the rejected options. "We chose X because it's better" is a useless ADR;
"we rejected tree-sitter-languages because it pins an old tree-sitter and breaks on 0.22+" is
the kind of thing that saves you in three months.

Save to docs/adr/ and number it sequentially.
EOF
```

Now the three subagents:

```bash
cat > .claude/agents/chunk-critic.md <<'EOF'
---
name: chunk-critic
description: Adversarially critiques chunk boundaries. Use after any change to a chunker.
tools: Read, Grep, Glob
---

You are a hostile reviewer of chunk boundaries. Your job is to argue that the chunks you are
shown are cut badly. Assume they are wrong and look for the evidence.

Attack these:
- a chunk that is meaningless without the chunk before or after it
- a diff hunk whose commit message is missing, so the change has no stated reason
- a thread chunk missing author or date, making its citation unbuildable
- code split anywhere other than a function/class/method boundary
- a chunk so large that a specific question would retrieve it for the wrong reason
- a chunk so small it carries no retrievable signal

Quote the offending text. Never propose a fix — that is not your job. If a chunk is genuinely
good, say so in one line and move on; do not manufacture criticism.
EOF

cat > .claude/agents/eval-writer.md <<'EOF'
---
name: eval-writer
description: Proposes new eval questions with known-correct sources from the corpus.
tools: Read, Grep, Glob, Bash
---

You write eval questions for a bug-archaeology retrieval system over the psf/requests repo.

Method: dig through git history, commit messages, and linked issue/PR numbers to find code
whose reason is non-obvious from the current source. Then write the question a confused
developer would ask about it.

Every question must include:
  - question           — phrased naturally, as a developer would type it
  - expected_sources   — specific refs (commit sha, PR #, issue #, file:symbol) that MUST be
                         retrieved for the answer to be correct
  - answer_must_mention — the facts a correct answer states
  - difficulty         — easy / medium / hard

Roughly 20% of questions must be unanswerable from the corpus, with expected answer
"insufficient information". Abstention is a tested behaviour, not a fallback.

Never invent a source. If you cannot verify a ref exists by reading the repo, drop the question.
EOF

cat > .claude/agents/retrieval-debugger.md <<'EOF'
---
name: retrieval-debugger
description: Traces why a correct chunk failed to surface for a failing eval question.
tools: Read, Grep, Glob, Bash
---

Given a failing eval question and its expected sources, find where in the pipeline the correct
chunk was lost. Work in this order and stop at the first stage that explains it:

1. Indexing — does the expected chunk exist in the index at all? If not, ingestion or chunking
   dropped it. Stop here.
2. BM25 — what rank did it get? If poor, inspect tokenisation: identifiers, snake_case splitting,
   stopwords eating a short query.
3. Vector — what rank and what cosine score? If poor, is the chunk's embedded text missing the
   context it needs (e.g. a diff hunk with no commit message)?
4. RRF fusion — it ranked fine in one method but lost after merge. Check whether one source type
   flooded the result set and starved the others.
5. Source-aware weighting — did quotas or query-adaptive weights push the right type out?

Report the stage, the evidence with numbers, and the smallest change that would fix it.
Do not implement the fix.
EOF
```

Finally the hooks file:

```bash
cat > .claude/settings.json <<'EOF'
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "if echo \"$CLAUDE_FILE_PATHS\" | grep -q '\\.py$'; then .venv/bin/ruff check --fix $CLAUDE_FILE_PATHS 2>&1 | tail -20; .venv/bin/ruff format $CLAUDE_FILE_PATHS 2>&1 | tail -5; fi"
          }
        ]
      }
    ]
  }
}
EOF
```

### Why

**Rules that live in your head get re-litigated every session; rules that live in `CLAUDE.md` get
followed.**

Here's what happens without it. Day 6, you ask Claude for a chunker. It writes a perfectly
reasonable one using 512-token windows with 50-token overlap, because that is the overwhelmingly
common answer and it has no reason to think otherwise. You catch it. Day 11, different session, you
ask for something adjacent — and it does the same thing again, because the earlier conversation is
gone. Every session starts from zero. Writing the four principles into a file that's read
automatically is how you stop having that argument.

`.cursorrules` being a copy of the same file matters for a dumber reason: if Cursor and Claude Code
disagree about your architecture, you end up with two half-implemented designs in one repo.

**On `chunk-critic` specifically** — it's read-only *by design*. Give a critic the ability to fix
things and it stops criticising and starts patching, and you lose the thing you actually wanted,
which is an independent second opinion. Your chunker is the highest-risk component in this project
(Phase 2 is starred in your own plan), and you are the worst possible reviewer of it, because you'll
evaluate it against what you intended rather than what it does.

The hook runs ruff on every Python file that gets written or edited. It's small, but it means bad
formatting never accumulates — you're never facing a 40-file cleanup commit.

Commit all of it:

```bash
git add . && git commit -m "Phase 0: CLAUDE.md mirror, slash commands, subagents, hooks"
```

---

# Phase 0 checklist

| Deliverable | Done when |
|---|---|
| Repo structure | `find src -type f` shows the full tree |
| `pyproject.toml` | `uv pip install -e ".[dev]"` succeeds |
| `CLAUDE.md` populated | already done — it's in your folder |
| `.cursorrules` | mirrors CLAUDE.md |
| Pre-commit hooks | `pre-commit run --all-files` passes |
| Target repo cloned | `corpus/requests` has ~6,500 commits |
| **Exit: pytest green** | `pytest` → 3 passed |
| **Exit: one-command bootstrap** | fresh clone to `/tmp` + `./bootstrap.sh` → 3 passed |

---

# One-line summary

Phase 0 is not about writing code — it's about making sure that on day 30, when something breaks,
you can prove the break is in your retrieval logic and not in your environment.

---

# What's open, and what I need from you

Two things are genuinely your call, not mine:

1. **The package-name question in Step 4** — flat `src/chunking/` (matches your CLAUDE.md, tiny
   collision risk) versus `src/bug_archaeology/chunking/` (bulletproof, requires a one-line edit to
   CLAUDE.md). Cheap now, annoying later. I'd take the wrapper, but it's your spec.
2. **Notion** — your Part 2 plan calls for a Project database and a Decisions database. Your Notion
   is connected here. Say the word and I'll create both and seed all nine phases as rows with their
   exit criteria, plus the 9am daily check-in as a scheduled task. I didn't do it unprompted because
   it writes to your workspace.

Everything else in Phase 0 is settled and in this document.
