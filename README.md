# Flashcard Agent

A local MCP server that exposes Anki operations (via [AnkiConnect](https://foosoft.net/projects/anki-connect/)) as tools for coding agents.

## Automatic formatting

Every Front/Back the server writes to Anki is converted first (`flashcard_agent.convert.to_anki`, idempotent):

- `$$...$$` display math → `\[...\]` (Anki MathJax display)
- `$...$` inline math → `\(...\)` (Anki MathJax inline)
- `**text**` markdown bold → `<b>text</b>`

This applies to `add_note`, `add_notes`, and `update_note`. Cards already using `\(...\)`/`\[...\]`/`<b>` pass through unchanged.

## Setup

```bash
mise use python@3.14   # or: mise install (reads mise.toml)
uv sync
uv run flashcard-agent  # starts the stdio MCP server
```

## Tools


| Tool | Purpose |
| --- | --- |
| `find_notes(query)` | Anki search scoped to Default, e.g. `tag:dreamer`, `is:new`. Returns note IDs. |
| `get_notes(note_ids)` | Front/Back fields and tags for Default notes (rejects foreign notes). |
| `add_note(front, back, tags?)` | Add one card to Default (rejects duplicates). |
| `add_notes(cards, tags?)` | Add many cards to Default; per-card and shared tags; reports duplicates without failing. |
| `update_note(note_id, front?, back?, tags?)` | Update fields and/or replace tags on a Default note. |
| `add_tags(note_ids, tags)` / `remove_tags(note_ids, tags)` | Incremental tag changes on Default notes. |
| `delete_notes(note_ids)` | Delete notes from Default (irreversible). |


## Registering with agents

Pi (user-level, so every session can use it):

```bash
pi mcp add flashcard-agent -- uv run --directory ~/code/flashcard-agent flashcard-agent
pi mcp list
```

Any other MCP client (JSON format):

```json
{
  "mcpServers": {
    "flashcard-agent": {
      "command": "uv",
      "args": ["run", "--directory", "/home/<user>/code/flashcard-agent", "flashcard-agent"]
    }
  }
}
```
