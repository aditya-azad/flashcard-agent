"""Anki MCP server.

Exposes solid Anki operations (via AnkiConnect) as MCP tools so agents can
create, update, find, and delete notes in the Default deck and manage tags.
"""

import re
from pathlib import Path

from mcp.server.mcpserver import MCPServer

from .anki import AnkiConnectError, anki_connect, require_anki
from .convert import to_anki

mcp = MCPServer(
    "anki",
    instructions=(
        "Tools for working with a local Anki instance over AnkiConnect. "
        "Cards are notes with Front/Back fields; notes go into the Default "
        "deck unless another deck is given. Tags are free-form labels such "
        "as 'dreamer'. Markdown flashcard files use a '## questions' section "
        "with '### question' headings followed by the answer."
    ),
)


def _note_fields(front: str, back: str) -> dict[str, str]:
    """Front/Back fields with markdown/LaTeX converted to Anki formatting."""
    return {"Front": to_anki(front), "Back": to_anki(back)}


async def _add_notes(
    cards: list[dict], deck: str, tags: list[str] | None
) -> dict:
    notes = [
        {
            "deckName": deck,
            "modelName": "Basic",
            "fields": _note_fields(card["front"], card["back"]),
            "tags": list({*(card.get("tags") or []), *(tags or [])}),
            "options": {"allowDuplicate": False},
        }
        for card in cards
    ]
    def _note_id(entry: object) -> int | None:
        # AnkiConnect versions return either a note id, null, or an
        # [id_or_null, error] pair per note.
        if isinstance(entry, (list, tuple)):
            return entry[0]
        return entry

    # Pre-check duplicates with canAddNotes: some AnkiConnect versions move
    # per-note duplicate errors into the top-level error field instead of
    # returning [id_or_null, error] pairs.
    addable = await anki_connect("canAddNotes", notes=notes)
    duplicate_indices = [i for i, ok in enumerate(addable) if not ok]
    addable_notes = [notes[i] for i, ok in enumerate(addable) if ok]
    added: list[int | None] = [None] * len(notes)
    if addable_notes:
        result = await anki_connect("addNotes", notes=addable_notes)
        new_ids = [_note_id(r) for r in result]
        it = iter(new_ids)
        for i, ok in enumerate(addable):
            if ok:
                added[i] = next(it)
    return {"added": added, "duplicates": duplicate_indices}


async def _note_info(note_id: int) -> dict:
    result = await anki_connect("notesInfo", notes=[note_id])
    info = result[0]
    return {
        "noteId": info["noteId"],
        "deck": (await anki_connect("cardsInfo", cards=[info["cards"][0]]))[0][
            "deckName"
        ],
        "fields": {k: v["value"] for k, v in info["fields"].items()},
        "tags": info["tags"],
    }


@mcp.tool()
async def list_decks() -> list[str]:
    """List all deck names in the local Anki collection."""
    await require_anki()
    return await anki_connect("deckNames")


@mcp.tool()
async def find_notes(query: str) -> list[int]:
    """Find note IDs with an Anki search query.

    Examples: 'tag:dreamer', 'deck:Default is:new', 'front:RSSM',
    'tag:dreamer deck:Default'.
    """
    await require_anki()
    return await anki_connect("findNotes", query=query)


@mcp.tool()
async def get_notes(note_ids: list[int]) -> list[dict]:
    """Get full info (deck, Front/Back fields, tags) for the given note IDs."""
    await require_anki()
    infos = await anki_connect("notesInfo", notes=note_ids)
    card_ids = [info["cards"][0] for info in infos]
    cards = await anki_connect("cardsInfo", cards=card_ids)
    return [
        {
            "noteId": info["noteId"],
            "deck": card["deckName"],
            "fields": {k: v["value"] for k, v in info["fields"].items()},
            "tags": info["tags"],
        }
        for info, card in zip(infos, cards, strict=True)
    ]


@mcp.tool()
async def add_note(
    front: str,
    back: str,
    tags: list[str] | None = None,
    deck: str = "Default",
) -> dict:
    """Add one card with Front/Back fields to a deck (default: Default).

    Tags is a list such as ['dreamer']. LaTeX ($...$, $$...$$) is rendered
    by Anki with MathJax. Returns the new noteId.
    """
    await require_anki()
    note = {
        "deckName": deck,
        "modelName": "Basic",
        "fields": _note_fields(front, back),
        "tags": tags or [],
        "options": {"allowDuplicate": False},
    }
    result = await anki_connect("addNotes", notes=[note])
    if result[0] is None:
        raise AnkiConnectError(
            f"Card not added (duplicate?): {result[1] or 'unknown reason'}"
        )
    return {"noteId": result[0], "deck": deck, "tags": tags or []}


@mcp.tool()
async def add_notes(
    cards: list[dict],
    deck: str = "Default",
    tags: list[str] | None = None,
) -> dict:
    """Add many cards in one call to a deck (default: Default).

    cards: list of {"front": str, "back": str, "tags"?: list[str]}.
    tags: extra tags applied to every card (e.g. ['dreamer']).
    Returns {'added': [noteId|null, ...], 'duplicates': [indices]}.
    """
    await require_anki()
    return await _add_notes(cards, deck, tags)


@mcp.tool()
async def update_note(
    note_id: int,
    front: str | None = None,
    back: str | None = None,
    tags: list[str] | None = None,
) -> dict:
    """Update the Front and/or Back fields and/or replace the tags of a note.

    Only provided arguments are changed. When tags is given it replaces the
    whole tag set (use add_tags/remove_tags for incremental changes).
    """
    await require_anki()
    if front is None and back is None and tags is None:
        raise ValueError("Nothing to update: pass front, back, and/or tags.")
    if front is not None or back is not None:
        existing = (await anki_connect("notesInfo", notes=[note_id]))[0]
        fields = {
            "Front": (
                to_anki(front)
                if front is not None
                else existing["fields"]["Front"]["value"]
            ),
            "Back": (
                to_anki(back)
                if back is not None
                else existing["fields"]["Back"]["value"]
            ),
        }
        await anki_connect(
            "updateNoteFields", note={"id": note_id, "fields": fields}
        )
    if tags is not None:
        await anki_connect(
            "updateNoteTags", note=note_id, tags=" ".join(tags)
        )
    return await _note_info(note_id)


@mcp.tool()
async def add_tags(note_ids: list[int], tags: list[str]) -> dict:
    """Add tags (e.g. ['dreamer']) to the given notes."""
    await require_anki()
    await anki_connect(
        "addTags", notes=note_ids, tags=" ".join(tags)
    )
    return {"noteIds": note_ids, "tags": tags}


@mcp.tool()
async def remove_tags(note_ids: list[int], tags: list[str]) -> dict:
    """Remove tags from the given notes."""
    await require_anki()
    await anki_connect("removeTags", notes=note_ids, tags=" ".join(tags))
    return {"noteIds": note_ids, "tags": tags}


@mcp.tool()
async def delete_notes(note_ids: list[int]) -> dict:
    """Delete the given notes (and their cards) from Anki. Irreversible."""
    await require_anki()
    await anki_connect("deleteNotes", notes=note_ids)
    return {"deleted": note_ids}


@mcp.tool()
async def add_flashcards_from_markdown(
    path: str,
    tags: list[str] | None = None,
    deck: str = "Default",
) -> dict:
    """Create cards from a markdown flashcard file and add them to a deck.

    Expects a '## questions' section with '### question' headings, each
    followed by the answer (LaTeX $...$/$$...$$ supported). Tags are applied
    to every created card, e.g. ['dreamer'].
    Returns {'added': [...], 'duplicates': [...]}.
    """
    file = Path(path).expanduser()
    text = file.read_text(encoding="utf-8")
    if "## questions" not in text:
        raise ValueError(f"No '## questions' section found in {file}")
    section = text.split("## questions", 1)[1]
    cards: list[dict] = []
    for part in re.split(r"^### ", section, flags=re.MULTILINE):
        part = part.strip()
        if not part:
            continue
        if "\n\n" not in part:
            raise ValueError(f"Question without answer in {file}: {part[:80]}")
        question, answer = part.split("\n\n", 1)
        cards.append(
            {"front": question.strip(), "back": answer.strip(), "tags": tags}
        )
    if not cards:
        raise ValueError(f"No '### question' entries found in {file}")
    await require_anki()
    return await _add_notes(cards, deck, tags)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
