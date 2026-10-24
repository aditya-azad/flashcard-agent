# Flashcard Agent

An MCP server that exposes solid Anki operations (via AnkiConnect) as tools, so agents can create, update, find, and delete notes. All operations are restricted to the **Default** deck.

Card-writing guidance (how to turn text into good flashcards, formatting conventions for LaTeX/bold, and which tools to call) lives in companion skills for the [pi](https://github.com/badlogic/pi-mono) agent, shipped in this repository under `skills/`. The skills are intentionally not placed in the auto-discovered project skills directory (`.agents/skills/`): they are meant to be installed into your pi agent, not tied to this checkout.

## Setup

1. **Anki** must be running with the [AnkiConnect](https://foosoft.net/projects/anki-connect/) add-on listening on `http://localhost:8765` (configurable via `ANKI_CONNECT_URL` / `ANKI_CONNECT_TIMEOUT`).

2. **Run the MCP server** from this repository:

```sh
uv run flashcard-agent
```

Then register it with pi's MCP gateway (see pi docs on MCP servers) or add it to your agent's MCP configuration as a stdio server running the command above.

## Install the skills into your pi agent

Point pi at the checkout's `skills/` directory via your agent settings (`~/.pi/agent/settings.json`):

```json
{
  "skills": ["/path/to/flashcard-agent/skills"]
}
```
