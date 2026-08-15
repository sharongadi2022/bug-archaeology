"""git_walker tests run entirely against the local corpus clone — no network,
no GitHub token needed. This is not "running an ingest"; it's a handful of
commits parsed into a throwaway tmp_path database, same as any other test.
"""

from pathlib import Path

import pytest

from bug_archaeology.ingestion.git_walker import ingest_commits
from bug_archaeology.ingestion.raw_store import RawStore

CORPUS_PATH = Path(__file__).resolve().parents[2].parent / "corpus" / "requests"

pytestmark = pytest.mark.skipif(
    not CORPUS_PATH.exists(), reason=f"target repo clone not found at {CORPUS_PATH}"
)


def test_ingest_commits_walks_requested_number_of_commits(tmp_path):
    store = RawStore(str(tmp_path / "raw.db"))
    ingest_commits(str(CORPUS_PATH), "psf/requests", store, max_commits=3)

    count = store._conn.execute("SELECT COUNT(*) FROM commits").fetchone()[0]
    assert count == 3

    hunk_count = store._conn.execute("SELECT COUNT(*) FROM diff_hunks").fetchone()[0]
    assert hunk_count > 0

    header = store._conn.execute("SELECT hunk_header FROM diff_hunks LIMIT 1").fetchone()[0]
    assert header.startswith("@@")

    store.close()


def test_ingest_commits_is_idempotent_on_rerun(tmp_path):
    db_path = str(tmp_path / "raw.db")

    store = RawStore(db_path)
    ingest_commits(str(CORPUS_PATH), "psf/requests", store, max_commits=3)
    store.close()

    store = RawStore(db_path)
    ingest_commits(str(CORPUS_PATH), "psf/requests", store, max_commits=3)
    count = store._conn.execute("SELECT COUNT(*) FROM commits").fetchone()[0]
    hunk_count = store._conn.execute("SELECT COUNT(*) FROM diff_hunks").fetchone()[0]
    store.close()

    assert count == 3

    # Re-run once more and confirm hunk count doesn't grow either.
    store = RawStore(db_path)
    ingest_commits(str(CORPUS_PATH), "psf/requests", store, max_commits=3)
    hunk_count_again = store._conn.execute("SELECT COUNT(*) FROM diff_hunks").fetchone()[0]
    store.close()

    assert hunk_count_again == hunk_count


def test_ingest_commits_resumes_after_partial_progress(tmp_path):
    """Simulates a crash mid-run: pre-seed one commit's sha as already stored,
    then ingest and confirm it's skipped rather than reprocessed.
    """
    import git

    db_path = str(tmp_path / "raw.db")
    repo = git.Repo(str(CORPUS_PATH))
    first_commit = next(repo.iter_commits("HEAD", max_count=1))

    store = RawStore(db_path)
    store.insert_commit(
        sha=first_commit.hexsha,
        repo="psf/requests",
        message="placeholder — pretend this was already ingested",
        author_name="nobody",
        author_email="nobody@example.com",
        authored_date="2000-01-01T00:00:00+00:00",
        parent_shas="",
    )

    ingest_commits(str(CORPUS_PATH), "psf/requests", store, max_commits=3)

    count = store._conn.execute("SELECT COUNT(*) FROM commits").fetchone()[0]
    stored_message = store._conn.execute(
        "SELECT message FROM commits WHERE sha = ?", (first_commit.hexsha,)
    ).fetchone()[0]
    store.close()

    # Still 3 total commits (the pre-seeded one plus 2 newly walked), and the
    # pre-seeded row was left untouched — INSERT OR IGNORE skipped it rather
    # than overwriting, proving the resumed run didn't reprocess it.
    assert count == 3
    assert stored_message == "placeholder — pretend this was already ingested"
