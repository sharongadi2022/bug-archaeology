"""Scans free text — commit messages, PR/issue bodies, comments — for
references to other issues, PRs, and commits.

This is deliberately syntactic, not semantic. "issue #1 of the C standard"
extracts a link to #1 exactly the same as a real cross-reference would —
the extractor has no way to tell the difference without reading the
surrounding prose, and that's not this phase's job. It records everything
it sees, tags low-confidence bare mentions as `mentions` rather than
`closes`/`refs`, and leaves any filtering to whatever consumes the links
table later (Phase 6's trail-following, most likely).

At this stage we can't tell whether a bare `#1234` names an issue or a PR
(GitHub numbers them from the same sequence but resolving which requires a
lookup against data we may not have fetched yet), so it's stored as the
ambiguous `issue_or_pr` ref type. Whatever reads the links table resolves
that later by checking the issues/pull_requests tables.
"""

from __future__ import annotations

import re
from typing import NamedTuple

_CLOSE_WORDS = {
    "fix",
    "fixes",
    "fixed",
    "close",
    "closes",
    "closed",
    "resolve",
    "resolves",
    "resolved",
}
_REF_WORDS = {"ref", "refs", "reference", "references", "see"}

_KEYWORDS_BY_LENGTH_DESC = sorted(_CLOSE_WORDS | _REF_WORDS, key=len, reverse=True)

_ISSUE_REF_RE = re.compile(
    r"\b(?P<keyword>" + "|".join(_KEYWORDS_BY_LENGTH_DESC) + r")\s+#(?P<num_kw>\d+)"
    r"|#(?P<num_bare>\d+)",
    re.IGNORECASE,
)

# 7-40 char hex runs, required to contain at least one digit. Pure-letter hex
# runs are valid English words often enough ("effaced", "cafeteria") that
# without this they'd be a steady source of false positives; real short SHAs
# almost always mix in a digit.
_COMMIT_HASH_RE = re.compile(r"\b(?=[0-9a-f]*\d)[0-9a-f]{7,40}\b", re.IGNORECASE)


class Link(NamedTuple):
    to_ref_type: str
    to_ref_value: str
    relation: str


def extract_links(text: str | None) -> list[Link]:
    if not text:
        return []

    links: list[Link] = []

    for match in _ISSUE_REF_RE.finditer(text):
        keyword = match.group("keyword")
        if keyword is not None:
            num = match.group("num_kw")
            relation = "closes" if keyword.lower() in _CLOSE_WORDS else "refs"
        else:
            num = match.group("num_bare")
            relation = "mentions"
        links.append(Link("issue_or_pr", num, relation))

    for match in _COMMIT_HASH_RE.finditer(text):
        links.append(Link("commit", match.group(0).lower(), "mentions"))

    return links
