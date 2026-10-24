"""Anki MCP server.

Exposes solid Anki operations (via AnkiConnect) as MCP tools so agents can
create, update, find, and delete notes and manage tags.

Deck policy: agents may ONLY operate on the Default deck. There is no way to
pass another deck, searches are always scoped to Default, and every
note-level operation verifies that the notes belong to Default before acting.
"""

import argparse
import difflib
import html
import os
import re

from mcp.server.mcpserver import MCPServer

from .anki import AnkiConnectError, anki_connect, ensure_anki_running

DEFAULT_DECK = "Default"

mcp = MCPServer(
    "flashcard-agent",
    instructions=(
        "Tools for working with a local Anki instance over AnkiConnect. "
        "All operations are restricted to the Default deck: cards are "
        "created there, searches are scoped there, and notes from any other "
        "deck cannot be read, updated, or deleted through this server. "
        "Agents should never work or access non-default decks. "
        "You are not allowed to use AnkiConnect directly. For guidance, use "
        "the flashcard skills"
    ),
)


def _note_fields(front: str, back: str) -> dict[str, str]:
    """Front/Back fields stored verbatim."""
    return {"Front": front, "Back": back}


async def _assert_notes_in_default(note_ids: list[int]) -> None:
    """Raise unless every note belongs to the Default deck."""
    infos = await anki_connect("notesInfo", notes=note_ids)
    card_ids = [info["cards"][0] for info in infos]
    cards = await anki_connect("cardsInfo", cards=card_ids)
    offenders = {}
    for note_id, card in zip(note_ids, cards, strict=True):
        if card["deckName"] != DEFAULT_DECK:
            offenders[note_id] = card["deckName"]
    if offenders:
        raise ValueError(
            f"Only notes in the {DEFAULT_DECK} deck are accessible. "
            f"These notes belong to other decks: {offenders}"
        )


async def _note_in_default(note_id: int) -> dict:
    """Return deck info for one note after verifying it is in Default."""
    await _assert_notes_in_default([note_id])
    info = (await anki_connect("notesInfo", notes=[note_id]))[0]
    return {
        "noteId": info["noteId"],
        "deck": DEFAULT_DECK,
        "fields": {k: v["value"] for k, v in info["fields"].items()},
        "tags": info["tags"],
    }


async def _add_notes(
    cards: list[dict], tags: list[str] | None
) -> dict:
    notes = [
        {
            "deckName": DEFAULT_DECK,
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


def _normalized_text(raw: str) -> str:
    """Strip HTML/MathJax markup, lowercase, collapse whitespace."""
    text = html.unescape(raw)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\\\[.*?\\\]|\\\((.*?)\\\)", " ", text, flags=re.DOTALL)
    return " ".join(text.lower().split())


@mcp.tool()
async def find_similar_notes(
    front: str,
    back: str | None = None,
    threshold: float = 0.6,
) -> list[dict]:
    """Find existing cards in the Default deck similar to a candidate card.

    Uses a fuzzy text comparison. Threshold (0.0–1.0, default 0.6) is the
    minimum combined similarity score. Returns matches sorted by score
    (highest first), each with noteId, front, back, tags, and score.
    Returns [] when nothing matches.
    """
    await ensure_anki_running()
    note_ids = await anki_connect(
        "findNotes", query=f'deck:"{DEFAULT_DECK}"'
    )
    infos = await anki_connect("notesInfo", notes=note_ids)

    norm_front = _normalized_text(front)
    norm_back = _normalized_text(back) if back else None

    matches: list[dict] = []
    for info in infos:
        fields = {k: v["value"] for k, v in info["fields"].items()}
        existing_front = _normalized_text(fields["Front"])
        existing_back = _normalized_text(fields["Back"])
        front_score = difflib.SequenceMatcher(
            None, norm_front, existing_front
        ).ratio()
        scores = [front_score]
        if norm_back:
            scores.append(
                difflib.SequenceMatcher(
                    None, norm_back, existing_back
                ).ratio()
            )
        score = sum(scores) / len(scores)
        if score >= threshold:
            matches.append(
                {
                    "noteId": info["noteId"],
                    "front": fields["Front"],
                    "back": fields["Back"],
                    "tags": info["tags"],
                    "score": round(score, 3),
                }
            )
    matches.sort(key=lambda m: m["score"], reverse=True)
    return matches


@mcp.tool()
async def find_notes(query: str) -> list[int]:
    """Find note IDs in the Default deck with an Anki search query.

    The search is always scoped to the Default deck: matches from any other
    deck are filtered out, and the query cannot bypass that (even with OR,
    parentheses, or negations). Example queries: 'tag:dreamer', 'is:new',
    'front:RSSM'.
    """
    await ensure_anki_running()
    note_ids = await anki_connect(
        "findNotes", query=f'deck:"{DEFAULT_DECK}" and ({query})'
    )
    return sorted(set(note_ids))


@mcp.tool()
async def get_notes(note_ids: list[int]) -> list[dict]:
    """Get full info (Front/Back fields, tags) for notes in the Default deck.

    Fails if any note belongs to a deck other than Default.
    """
    await ensure_anki_running()
    await _assert_notes_in_default(note_ids)
    infos = await anki_connect("notesInfo", notes=note_ids)
    return [
        {
            "noteId": info["noteId"],
            "deck": DEFAULT_DECK,
            "fields": {k: v["value"] for k, v in info["fields"].items()},
            "tags": info["tags"],
        }
        for info in infos
    ]


@mcp.tool()
async def get_all_tags() -> list[str]:
    """Get all tags used by notes in the Default deck, sorted.

    Returns an empty list when the deck has no notes or no tags.
    """
    await ensure_anki_running()
    note_ids = await anki_connect(
        "findNotes", query=f'deck:"{DEFAULT_DECK}"'
    )
    if not note_ids:
        return []
    infos = await anki_connect("notesInfo", notes=note_ids)
    tags: set[str] = set()
    for info in infos:
        tags.update(info["tags"])
    return sorted(tags)


@mcp.tool()
async def add_note(front: str, back: str, tags: list[str] | None = None) -> dict:
    """Add one card with Front/Back fields to the Default deck.

    Tags is a list such as ['dreamer']. Front/Back are stored verbatim.
    Returns the new noteId.
    """
    await ensure_anki_running()
    result = await _add_notes(
        [{"front": front, "back": back, "tags": tags}], tags=None
    )
    note_id = result["added"][0]
    if note_id is None:
        raise AnkiConnectError("Card not added (duplicate?).")
    return {"noteId": note_id, "deck": DEFAULT_DECK, "tags": tags or []}


@mcp.tool()
async def add_notes(
    cards: list[dict],
    tags: list[str] | None = None,
) -> dict:
    """Add many cards in one call to the Default deck.

    cards: list of {"front": str, "back": str, "tags"?: list[str]}.
    tags: extra tags applied to every card (e.g. ['dreamer']).
    Returns {'added': [noteId|null, ...], 'duplicates': [indices]}.
    """
    await ensure_anki_running()
    return await _add_notes(cards, tags)


@mcp.tool()
async def update_note(
    note_id: int,
    front: str | None = None,
    back: str | None = None,
    tags: list[str] | None = None,
) -> dict:
    """Update the Front and/or Back fields and/or replace the tags of a
    note in the Default deck.

    Only provided arguments are changed. When tags is given it replaces the
    whole tag set (use add_tags/remove_tags for incremental changes).
    """
    await ensure_anki_running()
    await _assert_notes_in_default([note_id])
    if front is None and back is None and tags is None:
        raise ValueError("Nothing to update: pass front, back, and/or tags.")
    if front is not None or back is not None:
        existing = (await anki_connect("notesInfo", notes=[note_id]))[0]
        fields = {
            "Front": (
                front
                if front is not None
                else existing["fields"]["Front"]["value"]
            ),
            "Back": (
                back
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
    return await _note_in_default(note_id)


@mcp.tool()
async def add_tags(note_ids: list[int], tags: list[str]) -> dict:
    """Add tags (e.g. ['dreamer']) to notes in the Default deck."""
    await ensure_anki_running()
    await _assert_notes_in_default(note_ids)
    await anki_connect("addTags", notes=note_ids, tags=" ".join(tags))
    return {"noteIds": note_ids, "tags": tags}


@mcp.tool()
async def remove_tags(note_ids: list[int], tags: list[str]) -> dict:
    """Remove tags from notes in the Default deck."""
    await ensure_anki_running()
    await _assert_notes_in_default(note_ids)
    await anki_connect("removeTags", notes=note_ids, tags=" ".join(tags))
    return {"noteIds": note_ids, "tags": tags}


@mcp.tool()
async def delete_notes(note_ids: list[int]) -> dict:
    """Delete notes (and their cards) from the Default deck. Irreversible.

    Fails if any note belongs to a deck other than Default.
    """
    await ensure_anki_running()
    await _assert_notes_in_default(note_ids)
    await anki_connect("deleteNotes", notes=note_ids)
    return {"deleted": note_ids}


def main() -> None:
    parser = argparse.ArgumentParser(description="Anki MCP server")
    parser.add_argument(
        "--http",
        action="store_true",
        help="serve over Streamable HTTP instead of stdio",
    )
    parser.add_argument(
        "--host",
        default=os.environ.get("FLASHCARD_AGENT_HOST", "127.0.0.1"),
        help="HTTP bind host (HTTP mode only; default 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("FLASHCARD_AGENT_PORT", "8000")),
        help="HTTP bind port (HTTP mode only; default 8000)",
    )
    args = parser.parse_args()
    if args.http:
        mcp.run(transport="streamable-http", host=args.host, port=args.port)
    else:
        mcp.run()


if __name__ == "__main__":
    main()
