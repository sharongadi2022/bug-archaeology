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
    """The src/bug_archaeology layout resolves — this is what pythonpath=['src'] buys us."""
    import bug_archaeology  # noqa: F401
    import bug_archaeology.chunking  # noqa: F401
    import bug_archaeology.generation  # noqa: F401
    import bug_archaeology.indexing  # noqa: F401
    import bug_archaeology.ingestion  # noqa: F401
    import bug_archaeology.retrieval  # noqa: F401
