"""GitHub GraphQL client: fetches PR and issue threads into the raw store.

Rate-limit aware by reading `rateLimit { cost remaining resetAt }` off every
response (it's requested in both queries below) rather than waiting for a 403
and retrying blindly. When `remaining` drops below the floor, sleeps until
`resetAt` and logs that it's doing so.

Resumable: each page's end cursor is checkpointed in the raw store before the
next page is requested, and a `<resource>_done` flag is set once pagination
is exhausted so a completed fetch is a no-op on the next run.

Known limitation, not silently swallowed: nested comment/review threads are
fetched one page each (100 issue/PR comments, 50 reviews, 50 comments per
review). A thread longer than that gets a `failures` row saying so rather
than quietly truncating without a trace — multi-page nested pagination was
out of scope for Phase 1.
"""

from __future__ import annotations

import json
import os
import time
from datetime import UTC, datetime

import httpx
from tqdm import tqdm

from bug_archaeology.ingestion.raw_store import RawStore

GRAPHQL_URL = "https://api.github.com/graphql"
RATE_LIMIT_FLOOR = 200
MAX_RETRIES = 3
PAGE_SIZE = 25


class GitHubTokenMissing(RuntimeError):
    pass


def get_token() -> str:
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise GitHubTokenMissing(
            "GITHUB_TOKEN is not set (checked .env / environment). Refusing to fall "
            "back to unauthenticated requests at 60/hour — set GITHUB_TOKEN and retry."
        )
    return token


PR_QUERY = """
query($owner: String!, $name: String!, $first: Int!, $after: String) {
  rateLimit { cost remaining resetAt }
  repository(owner: $owner, name: $name) {
    pullRequests(first: $first, after: $after, orderBy: {field: CREATED_AT, direction: ASC}) {
      pageInfo { hasNextPage endCursor }
      nodes {
        number
        title
        body
        state
        merged
        mergedAt
        createdAt
        updatedAt
        author { login }
        baseRefName
        headRefName
        mergeCommit { oid }
        comments(first: 100) {
          pageInfo { hasNextPage }
          nodes { id author { login } body createdAt }
        }
        reviews(first: 50) {
          pageInfo { hasNextPage }
          nodes {
            id
            author { login }
            body
            createdAt
            comments(first: 50) {
              pageInfo { hasNextPage }
              nodes { id author { login } body createdAt path position }
            }
          }
        }
      }
    }
  }
}
"""

ISSUE_QUERY = """
query($owner: String!, $name: String!, $first: Int!, $after: String) {
  rateLimit { cost remaining resetAt }
  repository(owner: $owner, name: $name) {
    issues(first: $first, after: $after, orderBy: {field: CREATED_AT, direction: ASC}) {
      pageInfo { hasNextPage endCursor }
      nodes {
        number
        title
        body
        state
        createdAt
        updatedAt
        closedAt
        author { login }
        labels(first: 20) { nodes { name } }
        comments(first: 100) {
          pageInfo { hasNextPage }
          nodes { id author { login } body createdAt }
        }
      }
    }
  }
}
"""


class GitHubClient:
    def __init__(self, token: str | None = None):
        self.token = token or get_token()
        self._client = httpx.Client(
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github+json",
            },
            timeout=30.0,
        )

    def close(self) -> None:
        self._client.close()

    def query(self, query: str, variables: dict, store: RawStore, context: str) -> dict | None:
        """Runs a GraphQL query with retry-on-transient-failure. Returns the
        `data` dict, or None if it ultimately failed (always logged, never
        silent).
        """
        last_error = "unknown error"
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = self._client.post(
                    GRAPHQL_URL, json={"query": query, "variables": variables}
                )
            except httpx.HTTPError as exc:
                last_error = f"network error: {exc}"
                time.sleep(2**attempt)
                continue

            if response.status_code >= 500:
                last_error = f"HTTP {response.status_code}: {response.text[:300]}"
                time.sleep(2**attempt)
                continue

            if response.status_code != 200:
                store.log_failure(
                    "github_graphql", context, f"HTTP {response.status_code}: {response.text[:500]}"
                )
                return None

            payload = response.json()

            if payload.get("errors"):
                store.log_failure("github_graphql", context, json.dumps(payload["errors"])[:1000])
                if not payload.get("data"):
                    return None

            data = payload.get("data") or {}
            rate = data.get("rateLimit")
            if rate:
                self._respect_rate_limit(rate)
            return data

        store.log_failure(
            "github_graphql", context, f"gave up after {MAX_RETRIES} attempts: {last_error}"
        )
        return None

    def _respect_rate_limit(self, rate: dict) -> None:
        remaining = rate.get("remaining")
        reset_at = rate.get("resetAt")
        if remaining is None or reset_at is None or remaining >= RATE_LIMIT_FLOOR:
            return
        reset_dt = datetime.fromisoformat(reset_at.replace("Z", "+00:00"))
        sleep_for = (reset_dt - datetime.now(UTC)).total_seconds()
        if sleep_for > 0:
            print(
                f"[github_client] rate limit low (remaining={remaining}), "
                f"sleeping {sleep_for:.0f}s until {reset_at}"
            )
            time.sleep(sleep_for + 2)


def _store_pr_comment(store: RawStore, pr_number: int, comment_type: str, node: dict) -> None:
    author = (node.get("author") or {}).get("login")
    store.insert_pr_comment(
        id=node["id"],
        pr_number=pr_number,
        comment_type=comment_type,
        author=author,
        body=node.get("body") or "",
        created_at=node.get("createdAt"),
        path=node.get("path"),
        position=node.get("position"),
    )


def _store_pull_request(store: RawStore, repo_label: str, node: dict) -> None:
    number = node["number"]
    author = (node.get("author") or {}).get("login")
    merge_commit = node.get("mergeCommit") or {}

    store.insert_pull_request(
        number=number,
        repo=repo_label,
        title=node.get("title"),
        body=node.get("body") or "",
        state=node.get("state"),
        merged=bool(node.get("merged")),
        merged_at=node.get("mergedAt"),
        created_at=node.get("createdAt"),
        updated_at=node.get("updatedAt"),
        author=author,
        base_ref=node.get("baseRefName"),
        head_ref=node.get("headRefName"),
        merge_commit_sha=merge_commit.get("oid"),
    )

    comments_block = node.get("comments") or {}
    if comments_block.get("pageInfo", {}).get("hasNextPage"):
        store.log_failure(
            "github_graphql", f"pr:{number}", "comment thread truncated at 100 comments"
        )
    for c in comments_block.get("nodes", []):
        _store_pr_comment(store, number, "issue_comment", c)

    for review in (node.get("reviews") or {}).get("nodes", []):
        review_id = review["id"]
        review_author = (review.get("author") or {}).get("login")
        review_body = review.get("body") or ""
        if review_body:
            store.insert_pr_comment(
                id=review_id,
                pr_number=number,
                comment_type="review",
                author=review_author,
                body=review_body,
                created_at=review.get("createdAt"),
                path=None,
                position=None,
            )
        rc_block = review.get("comments") or {}
        if rc_block.get("pageInfo", {}).get("hasNextPage"):
            store.log_failure(
                "github_graphql",
                f"pr:{number} review:{review_id}",
                "review comments truncated at 50",
            )
        for rc in rc_block.get("nodes", []):
            _store_pr_comment(store, number, "review_comment", rc)


def _store_issue(store: RawStore, repo_label: str, node: dict) -> None:
    number = node["number"]
    author = (node.get("author") or {}).get("login")
    labels = [label["name"] for label in (node.get("labels") or {}).get("nodes", [])]

    store.insert_issue(
        number=number,
        repo=repo_label,
        title=node.get("title"),
        body=node.get("body") or "",
        state=node.get("state"),
        created_at=node.get("createdAt"),
        updated_at=node.get("updatedAt"),
        closed_at=node.get("closedAt"),
        author=author,
        labels=json.dumps(labels),
    )

    comments_block = node.get("comments") or {}
    if comments_block.get("pageInfo", {}).get("hasNextPage"):
        store.log_failure(
            "github_graphql", f"issue:{number}", "comment thread truncated at 100 comments"
        )
    for c in comments_block.get("nodes", []):
        author_login = (c.get("author") or {}).get("login")
        store.insert_issue_comment(
            id=c["id"],
            issue_number=number,
            author=author_login,
            body=c.get("body") or "",
            created_at=c.get("createdAt"),
        )


def _paginate(
    client: GitHubClient,
    query: str,
    owner: str,
    name: str,
    store: RawStore,
    resource_key: str,
    cursor_checkpoint_key: str,
    done_checkpoint_key: str,
    already_fetched: int,
    max_threads: int | None,
    store_node_fn,
    desc: str,
) -> None:
    if store.get_checkpoint(done_checkpoint_key) == "true":
        print(f"[github_client] {desc} already fully fetched, skipping")
        return

    cursor = store.get_checkpoint(cursor_checkpoint_key)
    fetched = already_fetched

    with tqdm(total=max_threads, initial=fetched, desc=desc) as pbar:
        while max_threads is None or fetched < max_threads:
            page_size = PAGE_SIZE if max_threads is None else min(PAGE_SIZE, max_threads - fetched)
            data = client.query(
                query,
                {"owner": owner, "name": name, "first": page_size, "after": cursor},
                store,
                context=f"{resource_key}_page cursor={cursor}",
            )
            if data is None:
                # Failure already logged by client.query; stop here, resumable next run.
                break

            repo_data = data.get("repository")
            if repo_data is None:
                store.log_failure(
                    "github_graphql",
                    f"{resource_key}_page",
                    "repository field missing from response",
                )
                break

            block = repo_data[resource_key]
            for node in block["nodes"]:
                store_node_fn(node)
                fetched += 1
                pbar.update(1)

            cursor = block["pageInfo"]["endCursor"]
            store.set_checkpoint(cursor_checkpoint_key, cursor or "")

            if not block["pageInfo"]["hasNextPage"]:
                store.set_checkpoint(done_checkpoint_key, "true")
                break


def fetch_pull_requests(
    client: GitHubClient, owner: str, name: str, store: RawStore, max_threads: int | None = None
) -> None:
    repo_label = f"{owner}/{name}"
    _paginate(
        client,
        PR_QUERY,
        owner,
        name,
        store,
        resource_key="pullRequests",
        cursor_checkpoint_key="pr_cursor",
        done_checkpoint_key="pr_done",
        already_fetched=store.count_pull_requests(),
        max_threads=max_threads,
        store_node_fn=lambda node: _store_pull_request(store, repo_label, node),
        desc="pull requests",
    )


def fetch_issues(
    client: GitHubClient, owner: str, name: str, store: RawStore, max_threads: int | None = None
) -> None:
    repo_label = f"{owner}/{name}"
    _paginate(
        client,
        ISSUE_QUERY,
        owner,
        name,
        store,
        resource_key="issues",
        cursor_checkpoint_key="issue_cursor",
        done_checkpoint_key="issue_done",
        already_fetched=store.count_issues(),
        max_threads=max_threads,
        store_node_fn=lambda node: _store_issue(store, repo_label, node),
        desc="issues",
    )
