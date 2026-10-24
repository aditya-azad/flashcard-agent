# anki-mcp

A local MCP server that exposes Anki operations (via [AnkiConnect](https://foosoft.net/projects/anki-connect/)) as tools for coding agents. Cards are `Basic` notes with Front/Back fields and go into the **Default** deck unless another deck is given.

Runs on Python 3.14 (managed by [mise](https://mise.jdx.dev/)) with [uv](https://docs.astral.sh/uv/). Requires Anki running with AnkiConnect (default `http://localhost:8765`; override with `ANKI_CONNECT_URL`).

## Automatic formatting

Every Front/Back the server writes to Anki is converted first (`anki_mcp.convert.to_anki`, idempotent):

- `$$...$$` display math → `\[...\]` (Anki MathJax display)
- `$...$` inline math → `\(...\)` (Anki MathJax inline)
- `**text**` markdown bold → `<b>text</b>`

This applies to `add_note`, `add_notes`, `update_note`, and `add_flashcards_from_markdown`. Cards already using `\(...\)`/`\[...\]`/`<b>` pass through unchanged.

## Setup

```bash
mise use python@3.14   # or: mise install (reads mise.toml)
uv sync
uv run anki-mcp        # starts the stdio MCP server
```

## Tools

| Tool | Purpose |
| --- | --- |
| `list_decks()` | List deck names. |
| `find_notes(query)` | Anki search, e.g. `tag:dreamer`, `deck:Default is:new`. Returns note IDs. |
| `get_notes(note_ids)` | Deck, Front/Back fields, and tags for notes. |
| `add_note(front, back, tags?, deck="Default")` | Add one card (rejects duplicates). |
| `add_notes(cards, deck="Default", tags?)` | Add many cards; per-card and shared tags; reports duplicates without failing. |
| `update_note(note_id, front?, back?, tags?)` | Update fields and/or replace tags. |
| `add_tags(note_ids, tags)` / `remove_tags(note_ids, tags)` | Incremental tag changes. |
| `delete_notes(note_ids)` | Delete notes (irreversible). |
| `add_flashcards_from_markdown(path, tags?, deck="Default")` | Parse a markdown file's `## questions` section (`### question` headings followed by the answer) and create cards with the given tags. LaTeX `$...$`/`$$...$$` is rendered by Anki's MathJax. |

## Registering with agents

Pi (user-level, so every session can use it):

```bash
pi mcp add anki -- uv run --directory ~/code/anki-mcp anki-mcp
pi mcp list
```

Any other MCP client (JSON format):

```json
{
  "mcpServers": {
    "anki": {
      "command": "uv",
      "args": ["run", "--directory", "/home/<user>/code/anki-mcp", "anki-mcp"]
    }
  }
}
```

## Testing

End-to-end smoke test (spawns the server over stdio, exercises add/find/get/update/tags/delete against the live Anki, and cleans up after itself):

```bash
uv run python tests/smoke.py
```
