from app.sample_data import SAMPLE_RECORDS

def test_demo_records_have_metadata():
 assert len(SAMPLE_RECORDS)>=5
 for record in SAMPLE_RECORDS:
  assert record["id"] and record["title"] and record["text"]
  assert record["type"] in {"commit","pull_request","issue","code"}
  assert record["url"].startswith("https://")

def test_retry_story_links_commit_pr_issue():
 history=" ".join(r["text"] for r in SAMPLE_RECORDS)
 assert "retry_limit from 10 to 3" in history
 assert "PR #142" in history and "Issue #98" in history
