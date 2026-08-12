Write an architecture decision record from this conversation.

Format:
  # ADR-NNN: <title>
  Date | Status (accepted/superseded)
  ## Context      — what forced a decision
  ## Decision     — what we chose, one sentence
  ## Alternatives — each option actually considered, and the specific reason it lost
  ## Consequences — what this makes easy, and what it makes hard or expensive to change later

Be concrete about the rejected options. "We chose X because it's better" is a useless ADR;
"we rejected tree-sitter-languages because it pins an old tree-sitter and breaks on 0.22+" is
the kind of thing that saves you in three months.

Save to docs/adr/ and number it sequentially.
