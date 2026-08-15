"""CLI entry point: `python -m bug_archaeology.ingestion`.

Fetches commits + diff hunks (via GitPython, from a local clone) and
PRs + issues with full threads (via the GitHub GraphQL API) into a local
SQLite raw store. Resumable and idempotent — safe to kill and re-run.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

from bug_archaeology.ingestion.git_walker import ingest_commits
from bug_archaeology.ingestion.github_client import (
    GitHubClient,
    GitHubTokenMissing,
    fetch_issues,
    fetch_pull_requests,
)
from bug_archaeology.ingestion.raw_store import RawStore

# Assumption (per CLAUDE.md working agreements — stating and proceeding):
# target repo is psf/requests, cloned locally at ../corpus/requests, per
# PLAN_PART_1_WHAT.md assumption #1. Overridable via flags for the other
# repo indexed later (this project itself, assumption #5).
DEFAULT_DB_PATH = "data/raw.db"
DEFAULT_REPO_PATH = "../corpus/requests"
DEFAULT_OWNER = "psf"
DEFAULT_NAME = "requests"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ingest commits, PRs, and issues into raw.db",
    )
    parser.add_argument("--repo-path", default=DEFAULT_REPO_PATH, help="Local git clone to walk")
    parser.add_argument("--owner", default=DEFAULT_OWNER, help="GitHub repo owner")
    parser.add_argument("--name", default=DEFAULT_NAME, help="GitHub repo name")
    parser.add_argument("--db-path", default=DEFAULT_DB_PATH, help="SQLite raw store path")
    parser.add_argument(
        "--max-commits", type=int, default=None, help="Cap on commits walked (default: unlimited)"
    )
    parser.add_argument(
        "--max-threads",
        type=int,
        default=None,
        help="Cap on PR threads fetched, applied again independently to issue threads "
        "(default: unlimited)",
    )
    parser.add_argument("--skip-commits", action="store_true", help="Skip the git_walker step")
    parser.add_argument("--skip-github", action="store_true", help="Skip the GitHub GraphQL step")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    args = parse_args(argv)

    Path(args.db_path).parent.mkdir(parents=True, exist_ok=True)
    store = RawStore(args.db_path)
    repo_label = f"{args.owner}/{args.name}"

    try:
        if not args.skip_commits:
            print(f"== commits: {args.repo_path} -> {repo_label} ==")
            ingest_commits(args.repo_path, repo_label, store, max_commits=args.max_commits)

        if not args.skip_github:
            try:
                client = GitHubClient()
            except GitHubTokenMissing as exc:
                print(f"ERROR: {exc}", file=sys.stderr)
                return 1
            try:
                print(f"== pull requests: {repo_label} ==")
                fetch_pull_requests(
                    client, args.owner, args.name, store, max_threads=args.max_threads
                )
                print(f"== issues: {repo_label} ==")
                fetch_issues(client, args.owner, args.name, store, max_threads=args.max_threads)
            finally:
                client.close()
    finally:
        failures = store.get_failure_summary()
        if failures:
            print(f"\n== {len(failures)} failures logged ==")
            for phase, identifier, error_message, occurred_at in failures[:50]:
                print(f"  [{occurred_at}] [{phase}] {identifier}: {error_message[:200]}")
            if len(failures) > 50:
                print(
                    f"  ... and {len(failures) - 50} more (see `failures` table in {args.db_path})"
                )
        else:
            print("\n== no failures ==")
        store.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
