"""End-to-end smoke test: MCP client -> anki-mcp server -> AnkiConnect."""

import asyncio
import json

from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

TAG = "anki-mcp-smoke-test"


def data(result):
    """Unwrap a CallToolResult: structured content, else parse the text."""
    sc = result.structured_content
    if sc is not None:
        if isinstance(sc, dict) and set(sc) == {"result"}:
            return sc["result"]
        return sc
    return json.loads(result.content[0].text)


async def main() -> None:
    params = StdioServerParameters(
        command="uv",
        args=["run", "anki-mcp"],
        cwd="/home/azada/code/anki-mcp",
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            # Idempotency: remove leftovers from earlier failed runs.
            stale = await session.call_tool(
                "find_notes", {"query": f"tag:{TAG}"}
            )
            stale_ids = data(stale)
            if stale_ids:
                await session.call_tool("delete_notes", {"note_ids": stale_ids})

            tools = await session.list_tools()
            print("tools:", [t.name for t in tools.tools])

            decks = await session.call_tool("list_decks", {})
            print("decks:", data(decks))

            added = await session.call_tool(
                "add_note",
                {
                    "front": "anki-mcp smoke test front with $x^2$",
                    "back": "$$y=mx+b$$ and **bold** part",
                    "tags": [TAG],
                },
            )
            print("add_note:", data(added))
            note_id = data(added)["noteId"]

            found = await session.call_tool(
                "find_notes", {"query": f"tag:{TAG}"}
            )
            assert note_id in data(found)
            print("find_notes ok:", data(found))

            stored = data(
                await session.call_tool(
                    "get_notes", {"note_ids": [note_id]}
                )
            )[0]["fields"]
            assert stored["Front"] == (
                "anki-mcp smoke test front with \\(x^2\\)"
            ), stored["Front"]
            assert stored["Back"] == (
                "\\[y=mx+b\\] and <b>bold</b> part"
            ), stored["Back"]
            print("conversion ok:", stored)

            info = await session.call_tool(
                "get_notes", {"note_ids": [note_id]}
            )
            print("get_notes:", data(info))

            updated = await session.call_tool(
                "update_note",
                {
                    "note_id": note_id,
                    "back": "updated back",
                    "tags": [TAG, "extra"],
                },
            )
            print("update_note:", data(updated))

            removed = await session.call_tool(
                "remove_tags", {"note_ids": [note_id], "tags": ["extra"]}
            )
            print("remove_tags:", data(removed))

            deleted = await session.call_tool(
                "delete_notes", {"note_ids": [note_id]}
            )
            print("delete_notes:", data(deleted))

            gone = await session.call_tool("find_notes", {"query": f"tag:{TAG}"})
            assert data(gone) == [], data(gone)
            print("cleanup verified: smoke card deleted")


asyncio.run(main())
