Sample 20 chunks of source type $ARGUMENTS from the current index and print each one in full.

For each, answer: could someone who has never seen this repository understand what this chunk
is about from the chunk alone? A chunk fails if it needs surrounding context to make sense.

Check specifically:
- code: starts and ends at a real function/class boundary; never truncated mid-body
- diff: the commit message is present in the embedded text, not just the metadata
- pr_thread / issue_thread: author, date, and thread title are carried on the chunk
- all: the chunk carries enough to build its citation string per the CLAUDE.md table

End with a count of passes and failures and the single worst chunk, quoted.
