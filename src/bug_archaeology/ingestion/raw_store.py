"""SQLite-backed raw store for Phase 1 ingestion.

Everything lands here in as-fetched form — no chunking, no interpretation.
Every insert uses natural keys with INSERT OR IGNORE, so re-running any
ingestion step twice fetches nothing new the second time. Rows are committed
as soon as they're written (not batched into a giant end-of-run transaction),
so a process killed mid-run leaves a store that's exactly as far along as it
looked a moment before it died — nothing to rewind, nothing half-written.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from bug_archaeology.ingestion.link_extractor import extract_links

SCHEMA = """
CREATE TABLE IF NOT EXISTS commits (
    sha TEXT PRIMARY KEY,
    repo TEXT NOT NULL,
    message TEXT NOT NULL,
    author_name TEXT,
    author_email TEXT,
    authored_date TEXT NOT NULL,
    parent_shas TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS diff_hunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    commit_sha TEXT NOT NULL,
    file_path TEXT NOT NULL,
    hunk_index INTEGER NOT NULL,
    hunk_header TEXT,
    hunk_text TEXT NOT NULL,
    insertions INTEGER NOT NULL DEFAULT 0,
    deletions INTEGER NOT NULL DEFAULT 0,
    UNIQUE (commit_sha, file_path, hunk_index)
);

CREATE TABLE IF NOT EXISTS pull_requests (
    number INTEGER PRIMARY KEY,
    repo TEXT NOT NULL,
    title TEXT,
    body TEXT,
    state TEXT,
    merged INTEGER,
    merged_at TEXT,
    created_at TEXT,
    updated_at TEXT,
    author TEXT,
    base_ref TEXT,
    head_ref TEXT,
    merge_commit_sha TEXT
);

CREATE TABLE IF NOT EXISTS pr_comments (
    id TEXT PRIMARY KEY,
    pr_number INTEGER NOT NULL,
    comment_type TEXT NOT NULL,
    author TEXT,
    body TEXT,
    created_at TEXT,
    path TEXT,
    position INTEGER
);

CREATE TABLE IF NOT EXISTS issues (
    number INTEGER PRIMARY KEY,
    repo TEXT NOT NULL,
    title TEXT,
    body TEXT,
    state TEXT,
    created_at TEXT,
    updated_at TEXT,
    closed_at TEXT,
    author TEXT,
    labels TEXT
);

CREATE TABLE IF NOT EXISTS issue_comments (
    id TEXT PRIMARY KEY,
    issue_number INTEGER NOT NULL,
    author TEXT,
    body TEXT,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS links (
    from_chunk_id TEXT NOT NULL,
    to_ref_type TEXT NOT NULL,
    to_ref_value TEXT NOT NULL,
    relation TEXT NOT NULL,
    UNIQUE (from_chunk_id, to_ref_type, to_ref_value, relation)
);

CREATE TABLE IF NOT EXISTS failures (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    phase TEXT NOT NULL,
    identifier TEXT,
    error_message TEXT,
    occurred_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS checkpoints (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""


class RawStore:
    def __init__(self, db_path: str):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    # -- commits ------------------------------------------------------

    def get_existing_commit_shas(self) -> set[str]:
        rows = self._conn.execute("SELECT sha FROM commits").fetchall()
        return {row[0] for row in rows}

    def insert_commit(
        self,
        sha: str,
        repo: str,
        message: str,
        author_name: str | None,
        author_email: str | None,
        authored_date: str,
        parent_shas: str,
    ) -> None:
        with self._conn:
            self._conn.execute(
                """INSERT OR IGNORE INTO commits
                   (sha, repo, message, author_name, author_email, authored_date, parent_shas)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (sha, repo, message, author_name, author_email, authored_date, parent_shas),
            )
        self.insert_links_from_text(f"commit:{sha}", message)

    # -- diff hunks -----------------------------------------------------

    def insert_diff_hunk(
        self,
        commit_sha: str,
        file_path: str,
        hunk_index: int,
        hunk_header: str,
        hunk_text: str,
        insertions: int,
        deletions: int,
    ) -> None:
        with self._conn:
            self._conn.execute(
                """INSERT OR IGNORE INTO diff_hunks
                   (commit_sha, file_path, hunk_index, hunk_header, hunk_text,
                    insertions, deletions)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (commit_sha, file_path, hunk_index, hunk_header, hunk_text, insertions, deletions),
            )

    # -- pull requests ----------------------------------------------------

    def count_pull_requests(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM pull_requests").fetchone()[0]

    def insert_pull_request(
        self,
        number: int,
        repo: str,
        title: str | None,
        body: str,
        state: str | None,
        merged: bool,
        merged_at: str | None,
        created_at: str | None,
        updated_at: str | None,
        author: str | None,
        base_ref: str | None,
        head_ref: str | None,
        merge_commit_sha: str | None,
    ) -> None:
        with self._conn:
            self._conn.execute(
                """INSERT OR IGNORE INTO pull_requests
                   (number, repo, title, body, state, merged, merged_at, created_at,
                    updated_at, author, base_ref, head_ref, merge_commit_sha)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    number,
                    repo,
                    title,
                    body,
                    state,
                    int(merged),
                    merged_at,
                    created_at,
                    updated_at,
                    author,
                    base_ref,
                    head_ref,
                    merge_commit_sha,
                ),
            )
        self.insert_links_from_text(f"pr:{number}", body)

    def insert_pr_comment(
        self,
        id: str,
        pr_number: int,
        comment_type: str,
        author: str | None,
        body: str,
        created_at: str | None,
        path: str | None,
        position: int | None,
    ) -> None:
        with self._conn:
            self._conn.execute(
                """INSERT OR IGNORE INTO pr_comments
                   (id, pr_number, comment_type, author, body, created_at, path, position)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (id, pr_number, comment_type, author, body, created_at, path, position),
            )
        self.insert_links_from_text(f"pr_comment:{id}", body)

    # -- issues -----------------------------------------------------------

    def count_issues(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM issues").fetchone()[0]

    def insert_issue(
        self,
        number: int,
        repo: str,
        title: str | None,
        body: str,
        state: str | None,
        created_at: str | None,
        updated_at: str | None,
        closed_at: str | None,
        author: str | None,
        labels: str,
    ) -> None:
        with self._conn:
            self._conn.execute(
                """INSERT OR IGNORE INTO issues
                   (number, repo, title, body, state, created_at, updated_at,
                    closed_at, author, labels)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    number,
                    repo,
                    title,
                    body,
                    state,
                    created_at,
                    updated_at,
                    closed_at,
                    author,
                    labels,
                ),
            )
        self.insert_links_from_text(f"issue:{number}", body)

    def insert_issue_comment(
        self,
        id: str,
        issue_number: int,
        author: str | None,
        body: str,
        created_at: str | None,
    ) -> None:
        with self._conn:
            self._conn.execute(
                """INSERT OR IGNORE INTO issue_comments
                   (id, issue_number, author, body, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (id, issue_number, author, body, created_at),
            )
        self.insert_links_from_text(f"issue_comment:{id}", body)

    # -- links --------------------------------------------------------------

    def insert_links_from_text(self, from_chunk_id: str, text: str | None) -> None:
        for link in extract_links(text):
            with self._conn:
                self._conn.execute(
                    """INSERT OR IGNORE INTO links
                       (from_chunk_id, to_ref_type, to_ref_value, relation)
                       VALUES (?, ?, ?, ?)""",
                    (from_chunk_id, link.to_ref_type, link.to_ref_value, link.relation),
                )

    # -- failures -------------------------------------------------------

    def log_failure(self, phase: str, identifier: str, error_message: str) -> None:
        with self._conn:
            self._conn.execute(
                """INSERT INTO failures (phase, identifier, error_message, occurred_at)
                   VALUES (?, ?, ?, ?)""",
                (phase, identifier, error_message, datetime.now(UTC).isoformat()),
            )

    def get_failure_summary(self) -> list[tuple[str, str, str, str]]:
        rows = self._conn.execute(
            "SELECT phase, identifier, error_message, occurred_at FROM failures ORDER BY id"
        ).fetchall()
        return [tuple(row) for row in rows]

    # -- checkpoints ------------------------------------------------------

    def get_checkpoint(self, key: str) -> str | None:
        row = self._conn.execute("SELECT value FROM checkpoints WHERE key = ?", (key,)).fetchone()
        return row[0] if row else None

    def set_checkpoint(self, key: str, value: str) -> None:
        with self._conn:
            self._conn.execute(
                "INSERT INTO checkpoints (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )
