---
name: flashcard-creation
description: >-
  Create high-quality Anki flashcards from source text (notes, articles,
  textbooks, transcripts) or from a topic description. Use whenever the user
  asks to make flashcards, memorization cards, or spaced-repetition cards.
  Covers card-writing principles, Anki formatting conventions, and storing
  cards in Anki via the flashcard-agent MCP server.
---

# Flashcard creation

Turn source text or a topic instruction into Anki flashcards, then store them with the `flashcard-agent` MCP server.

## Format

- **Basic notes, Front/Back only.** Front is the prompt, Back is the answer. No cloze model.
- **Write all card text in proper Anki formatting**: HTML lists (`<ul>`, `<ol>`, `<li>`), text decoration (`<b>`, `<i>`, `<u>`), and MathJax (`\(...\)` for inline math, `\[...\]` for display math) for all mathematical notation and everything else. Never leave the structure as plain text/markdown.
- Use the server's tools only — never call AnkiConnect directly.
- The server automatically starts Anki on the first tool call if it isn't running; the first call may take a few seconds while Anki launches.

## Tags

- **Never invent tags yourself.** Only apply tags the user provides. If the user explicitly asks for a tag recommendation, suggest one; otherwise store cards without tags.

## Writing good cards

1. **One fact per card.** Split compound facts into separate cards.
2. **Pose a question or cue, not a topic.** Front must demand retrieval: "What does the enzyme catalyze?" — not "Enzyme X".
3. **Be specific about context.** Every card must be specific enough that the user immediately knows what topic/context the question is about when it comes up in review. Name the subject, system, or source explicitly rather than relying on a bare pronoun or generic phrasing.
4. **Answers self-contained and short.** The Back must be understandable without the source text; prefer one sentence or a short list.
5. **Drop yes/no and trivia-free cards.** If the answer is guessable from the Front alone, or the fact isn't worth memorizing, skip it.
6. **Use examples and counterexamples** ("e.g. X is Y because ...") for concepts.
7. **Preserve math and notation exactly** — render formulas with MathJax as they appear in the source, don't paraphrase into words.
8. **Keep the user's language** unless asked otherwise.
9. **Scale to the material.** A dense page yields ~5–15 cards, a short paragraph 1–3. Ask if the user wants a specific count or depth.

## Workflow

1. Read the source. If scope (sections, depth) is ambiguous, confirm first.
2. Draft cards following the principles above.
3. **Check for existing similar cards before adding.** Before storing, run the MCP tool `find_similar_notes` with the drafted Front (and Back as `back`) for each card — or batch your checks efficiently by iterating over the drafted cards. It returns existing Default-deck cards with a similarity `score` above the threshold. Skip any card whose match has a high score (roughly ≥ 0.6) — it's a duplicate or trivially rephrased version of an existing card — and tell the user which were skipped and why. Only genuinely new cards go to step 4.
4. Store with MCP tool `add_notes`, passing `[{"front": ..., "back": ..., "tags": [...]}]` (plus a shared `tags` list if the user provided one). Use `add_note` only for a single card.
5. Report: number of cards added, any entries in the returned `duplicates` list, any cards skipped in step 3, and the tags used. Duplicates are skipped (`allowDuplicate: false`); offer `update_note` instead of force-adding.
6. For edits: `find_notes` (e.g. `tag:biology`) + `get_notes` to locate, then `update_note`, `add_tags`, `remove_tags`, or `delete_notes`.
