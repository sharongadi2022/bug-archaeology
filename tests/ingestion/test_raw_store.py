from bug_archaeology.ingestion.raw_store import RawStore


def make_store(tmp_path):
    return RawStore(str(tmp_path / "raw.db"))


def test_insert_commit_is_idempotent(tmp_path):
    store = make_store(tmp_path)
    kwargs = dict(
        sha="abc1234",
        repo="psf/requests",
        message="Fixes #1 — trivial change",
        author_name="A",
        author_email="a@example.com",
        authored_date="2021-01-01T00:00:00+00:00",
        parent_shas="",
    )
    store.insert_commit(**kwargs)
    store.insert_commit(**kwargs)

    count = store._conn.execute("SELECT COUNT(*) FROM commits").fetchone()[0]
    assert count == 1
    store.close()


def test_insert_commit_extracts_links_automatically(tmp_path):
    store = make_store(tmp_path)
    store.insert_commit(
        sha="abc1234",
        repo="psf/requests",
        message="Fixes #987 — see a3f9c21 for context",
        author_name="A",
        author_email="a@example.com",
        authored_date="2021-01-01T00:00:00+00:00",
        parent_shas="",
    )
    rows = store._conn.execute(
        "SELECT to_ref_type, to_ref_value, relation FROM links WHERE from_chunk_id = ?",
        ("commit:abc1234",),
    ).fetchall()
    assert ("issue_or_pr", "987", "closes") in rows
    assert ("commit", "a3f9c21", "mentions") in rows
    store.close()


def test_diff_hunk_unique_constraint_is_idempotent(tmp_path):
    store = make_store(tmp_path)
    store.insert_commit(
        sha="abc1234",
        repo="psf/requests",
        message="msg",
        author_name="A",
        author_email="a@example.com",
        authored_date="2021-01-01T00:00:00+00:00",
        parent_shas="",
    )
    hunk_kwargs = dict(
        commit_sha="abc1234",
        file_path="src/models.py",
        hunk_index=0,
        hunk_header="@@ -1,3 +1,3 @@",
        hunk_text="@@ -1,3 +1,3 @@\n-old\n+new",
        insertions=1,
        deletions=1,
    )
    store.insert_diff_hunk(**hunk_kwargs)
    store.insert_diff_hunk(**hunk_kwargs)

    count = store._conn.execute("SELECT COUNT(*) FROM diff_hunks").fetchone()[0]
    assert count == 1
    store.close()


def test_failures_are_logged_not_swallowed(tmp_path):
    store = make_store(tmp_path)
    store.log_failure("git_walker", "deadbeef1", "boom")
    summary = store.get_failure_summary()
    assert len(summary) == 1
    assert summary[0][0] == "git_walker"
    assert summary[0][1] == "deadbeef1"
    assert summary[0][2] == "boom"
    store.close()


def test_checkpoints_roundtrip_and_upsert(tmp_path):
    store = make_store(tmp_path)
    assert store.get_checkpoint("pr_cursor") is None

    store.set_checkpoint("pr_cursor", "cursor-1")
    assert store.get_checkpoint("pr_cursor") == "cursor-1"

    store.set_checkpoint("pr_cursor", "cursor-2")
    assert store.get_checkpoint("pr_cursor") == "cursor-2"
    store.close()
