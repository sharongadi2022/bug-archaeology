import os
import requests
from typing import Iterable


API = "https://api.github.com"


def chunk_record(item: dict) -> dict:
    """Keep each commit as one chunk; split longer discussions into comment-sized blocks."""
    text = (item.get("text") or item.get("body") or "").strip()
    if len(text) <= 1100:
        return {**item, "text": text}
    parts = [text[i:i + 900] for i in range(0, len(text), 780)]
    return [{**item, "id": f"{item.get('id', 'source')}-{i+1}", "text": part}
            for i, part in enumerate(parts)]


def _headers() -> dict:
    headers = {"Accept": "application/vnd.github+json"}
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def fetch_repository_history(repo: str) -> list[dict]:
    """Fetch recent commits, issues and PRs from a public or authorized GitHub repo."""
    headers = _headers()
    records: list[dict] = []

    commits = requests.get(f"{API}/repos/{repo}/commits", headers=headers,
                           params={"per_page": 30}, timeout=20)
    commits.raise_for_status()
    for c in commits.json():
        message = c.get("commit", {}).get("message", "")
        records.append({
            "id": f"commit-{c['sha'][:8]}", "kind": "commit",
            "title": message.splitlines()[0][:140], "text": message,
            "url": c.get("html_url", ""), "date": c.get("commit", {}).get("author", {}).get("date", ""),
            "author": c.get("commit", {}).get("author", {}).get("name", "Unknown")
        })

    issues = requests.get(f"{API}/repos/{repo}/issues", headers=headers,
                          params={"state": "all", "per_page": 30}, timeout=20)
    issues.raise_for_status()
    for issue in issues.json():
        if issue.get("pull_request"):
            kind = "pull request"
        else:
            kind = "issue"
        body = issue.get("body") or ""
        comments = ""
        if issue.get("comments", 0):
            detail = requests.get(issue["comments_url"], headers=headers, timeout=20)
            if detail.ok:
                comments = "\n".join(x.get("body") or "" for x in detail.json()[:8])
        records.append({
            "id": f"{'pr' if issue.get('pull_request') else 'issue'}-{issue['number']}",
            "kind": kind, "title": issue.get("title", ""),
            "text": f"{body}\n{comments}".strip(),
            "url": issue.get("html_url", ""), "date": issue.get("updated_at", ""),
            "author": issue.get("user", {}).get("login", "Unknown")
        })
    chunks = []
    for record in records:
        value = chunk_record(record)
        chunks.extend(value if isinstance(value, list) else [value])
    return [r for r in chunks if r.get("text")]


def load_sample(path: str) -> list[dict]:
    import json
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    chunks = []
    for record in data:
        value = chunk_record(record)
        chunks.extend(value if isinstance(value, list) else [value])
    return chunks
