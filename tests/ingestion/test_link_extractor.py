from bug_archaeology.ingestion.link_extractor import Link, extract_links


def test_fixes_keyword():
    assert extract_links("Fixes #1234") == [Link("issue_or_pr", "1234", "closes")]


def test_multiple_keywords_in_one_string():
    assert extract_links("closes #987 and refs #412") == [
        Link("issue_or_pr", "987", "closes"),
        Link("issue_or_pr", "412", "refs"),
    ]


def test_bare_commit_hash():
    assert extract_links("see a3f9c21") == [Link("commit", "a3f9c21", "mentions")]


def test_bare_issue_number_false_positive_is_still_extracted():
    """ "issue #1 of the C standard" isn't a real cross-reference, but the
    extractor is syntactic, not semantic: it has no way to know that without
    reading the surrounding prose. It extracts #1 anyway, tagged as a
    low-confidence 'mentions' relation (no closing keyword precedes it), and
    leaves any filtering to whatever consumes the links table downstream.
    """
    assert extract_links("issue #1 of the C standard") == [Link("issue_or_pr", "1", "mentions")]


def test_case_insensitive_keyword():
    assert extract_links("FIXES #42") == [Link("issue_or_pr", "42", "closes")]


def test_resolved_and_close_variants():
    assert extract_links("Resolved #1") == [Link("issue_or_pr", "1", "closes")]
    assert extract_links("Close #2") == [Link("issue_or_pr", "2", "closes")]


def test_reference_variants():
    assert extract_links("References #3") == [Link("issue_or_pr", "3", "refs")]
    assert extract_links("See #4") == [Link("issue_or_pr", "4", "refs")]


def test_commit_hash_requires_a_digit_to_avoid_english_word_false_positives():
    # "effaced" is a real word made entirely of hex letters (e,f,f,a,c,e,d) —
    # without the digit requirement this would wrongly look like a SHA.
    assert extract_links("the bug was effaced by a later patch") == []


def test_no_links_in_plain_text():
    assert extract_links("just a normal commit message, nothing to see here") == []


def test_empty_and_none_text():
    assert extract_links("") == []
    assert extract_links(None) == []


def test_multiple_commit_hashes():
    assert extract_links("bisected between a3f9c21 and 9c8b7a6") == [
        Link("commit", "a3f9c21", "mentions"),
        Link("commit", "9c8b7a6", "mentions"),
    ]
