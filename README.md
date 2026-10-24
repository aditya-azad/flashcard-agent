# Flashcard Agent

An MCP server that exposes solid Anki operations (via AnkiConnect) as tools, so agents can create, update, find, and delete notes. All operations are restricted to the **Default** deck.

Card-writing guidance (how to turn text into good flashcards, formatting conventions for LaTeX/bold, and which tools to call) lives in companion skills for the [pi](https://github.com/badlogic/pi-mono) agent, shipped in this repository under `skills/`. The skills are intentionally not placed in the auto-discovered project skills directory (`.agents/skills/`): they are meant to be installed into your pi agent, not tied to this checkout.

## Setup

1. Clone this repository and run

```sh
mise install
uv sync
```

2. **Anki** with the [AnkiConnect](https://foosoft.net/projects/anki-connect/) add-on listening on `http://localhost:8765` (configurable via `ANKI_CONNECT_URL` / `ANKI_CONNECT_TIMEOUT`). The server lazy-starts Anki automatically on the first tool call if it isn't running, so it doesn't need to be open beforehand; the startup wait is adjustable via `ANKI_START_TIMEOUT` (seconds, default 30).

3. **Install the MCP server** into your pi agent:

```sh
pi mcp add -l flashcards -- uv run --directory "$(pwd)" flashcard-agent
```

This adds a project-level (`-l`) stdio server entry that runs the server via uv, so no separate manual launch is needed. Verify the connection with:

```sh
pi mcp list
```

Alternatively, add it manually to `.pi/mcp.json` (project) or `~/.pi/agent/mcp.json` (user):

```json
{
  "mcpServers": {
    "flashcards": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/flashcard-agent", "flashcard-agent"]
    }
  }
}
```

You can also run the server directly from this repository to test it:

```sh
uv run flashcard-agent
```

## Available tools

All tools operate exclusively on the **Default** deck and fail if a note belongs to any other deck.

| Tool | Description |
|---|---|
| `find_similar_notes` | Find existing cards in the Default deck similar to a candidate card.|
| `find_notes` | Find note IDs in the Default deck using an Anki search query (e.g. `tag:dreamer`, `is:new`). |
| `get_notes` | Get full info (Front/Back fields, tags) for a list of note IDs. |
| `get_all_tags` | Get all tags used by notes in the Default deck, sorted. |
| `add_note` | Add one card with Front/Back fields and optional tags. Returns the new note ID. |
| `add_notes` | Add many cards in one call; supports shared tags and reports duplicates. |
| `update_note` | Update the Front and/or Back fields and/or replace the tags of a note. |
| `add_tags` | Add tags to one or more notes. |
| `remove_tags` | Remove tags from one or more notes. |
| `delete_notes` | Delete notes (and their cards). Irreversible. |


## Docker

The image bundles the MCP server, a headless Anki desktop (under Xvfb) with AnkiConnect, and AnkiWeb sign-in from environment variables. The server is served over Streamable HTTP:

```sh
cp .env.example .env          # fill in your AnkiWeb credentials
docker compose up -d --build
```

The MCP endpoint is then available at `http://localhost:8000/mcp`. Install it into your pi agent with:

```sh
pi mcp add -l flashcards --url http://localhost:8000/mcp
pi mcp list
```

(or point any MCP client at that URL; add `--bearer-token-env-var` if you put the server behind authenticated access).

Credentials are read from the environment, not hard-coded anywhere. Without `ANKIWEB_EMAIL`/`ANKIWEB_PASSWORD` the container starts with a fresh empty collection; with them set, the container signs in at startup, downloads your collection (first sync may take a while), and stores the sync credentials so Anki comes up signed in. Wrong credentials abort startup with a clear error.

While signed in, a background loop pushes/pulls the collection every `ANKIWEB_SYNC_INTERVAL` seconds (default 300), so cards added by the agent reach AnkiWeb without a restart. Confirmation dialogs aqt would normally show for full syncs are answered automatically by a bundled add-on (`docker/anki_addons/headless-sync`): an empty side is filled from the other, and a genuine sync conflict (both sides changed) defaults to skipping the sync without destroying data — set `ANKI_SYNC_CONFLICT=upload` or `=download` to resolve such conflicts automatically. A self-hosted Anki sync server can be used via `ANKIWEB_SYNC_URL`.

Your collection lives in a named Docker volume (`anki-data`), so it persists across restarts and only incremental syncs happen on reboot. Run without compose via:

```sh
docker build -t flashcard-agent .
docker run -d --rm --env-file .env -p 127.0.0.1:8000:8000 flashcard-agent
```

For a plain `docker run`, note that AnkiWeb sign-in happens when `ANKIWEB_EMAIL`/`ANKIWEB_PASSWORD` are present in the environment; the `.env` file is only loaded by the flags shown above (`--env-file` or compose's `env_file`).

## Install the skills into your pi agent

Point pi at the checkout's `skills/` directory via your agent settings (`~/.pi/agent/settings.json`):

```json
{
  "skills": ["/path/to/flashcard-agent/skills"]
}
```
