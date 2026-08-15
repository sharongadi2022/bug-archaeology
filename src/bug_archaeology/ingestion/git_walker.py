"""Walks commit history from a local clone via GitPython and writes commits
plus per-file diff hunks into the raw store.

Resumable by construction: `RawStore.insert_commit` uses INSERT OR IGNORE on
`sha`, so we fetch the set of shas already stored once up front and skip
anything already there — a killed-and-restarted run just picks up where it
left off, and a completed run re-invoked does nothing.

Merge commits are diffed against their first parent only. `requests` doesn't
merge with rebase-and-squash-adjacent history that would make this
misleading, and diffing against every parent would multiply hunk count for
little benefit here — flagged per CLAUDE.md's "flag deviations" agreement.
"""

from __future__ import annotations

import re

import git
from tqdm import tqdm

from bug_archaeology.ingestion.raw_store import RawStore

_HUNK_START_RE = re.compile(r"^@@ .*? @@", re.MULTILINE)


def _split_hunks(patch_text: str) -> list[tuple[str, str]]:
    """Split a unified diff patch into (header, full hunk text) pairs."""
    if "@@" not in patch_text:
        return []
    pieces = re.split(r"(?=^@@ )", patch_text, flags=re.MULTILINE)
    hunks = []
    for piece in pieces:
        if not piece.startswith("@@"):
            continue
        header_match = _HUNK_START_RE.match(piece)
        header = header_match.group(0) if header_match else ""
        hunks.append((header, piece))
    return hunks


def _count_changes(hunk_text: str) -> tuple[int, int]:
    insertions = sum(
        1 for line in hunk_text.splitlines() if line.startswith("+") and not line.startswith("+++")
    )
    deletions = sum(
        1 for line in hunk_text.splitlines() if line.startswith("-") and not line.startswith("---")
    )
    return insertions, deletions


def _ingest_one_commit(commit: git.Commit, repo_label: str, store: RawStore) -> None:
    parent_shas = ",".join(p.hexsha for p in commit.parents)
    store.insert_commit(
        sha=commit.hexsha,
        repo=repo_label,
        message=commit.message.strip(),
        author_name=commit.author.name,
        author_email=commit.author.email,
        authored_date=commit.authored_datetime.isoformat(),
        parent_shas=parent_shas,
    )

    if commit.parents:
        diff_index = commit.parents[0].diff(commit, create_patch=True)
    else:
        # Root commit: diff against the empty tree, reversed, so the patch
        # reads as additions rather than "everything was deleted".
        diff_index = commit.diff(git.NULL_TREE, create_patch=True, R=True)

    for diff_item in diff_index:
        if diff_item.diff is None:
            continue
        file_path = diff_item.b_path or diff_item.a_path
        patch_text = diff_item.diff.decode("utf-8", errors="replace")
        for idx, (header, hunk_text) in enumerate(_split_hunks(patch_text)):
            insertions, deletions = _count_changes(hunk_text)
            store.insert_diff_hunk(
                commit_sha=commit.hexsha,
                file_path=file_path,
                hunk_index=idx,
                hunk_header=header,
                hunk_text=hunk_text,
                insertions=insertions,
                deletions=deletions,
            )


def ingest_commits(
    repo_path: str,
    repo_label: str,
    store: RawStore,
    max_commits: int | None = None,
) -> None:
    repo = git.Repo(repo_path)
    already_stored = store.get_existing_commit_shas()

    processed = 0
    skipped = 0
    with tqdm(total=max_commits, desc="commits") as pbar:
        for commit in repo.iter_commits("HEAD"):
            if max_commits is not None and processed >= max_commits:
                break
            processed += 1
            pbar.update(1)

            if commit.hexsha in already_stored:
                skipped += 1
                continue

            try:
                _ingest_one_commit(commit, repo_label, store)
            except Exception as exc:  # noqa: BLE001 — must log and keep going, never die silently
                store.log_failure("git_walker", commit.hexsha, str(exc))

    print(f"[git_walker] {processed} commits considered, {skipped} already stored and skipped")
