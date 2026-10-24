"""Thin async client for the AnkiConnect HTTP API (http://localhost:8765)."""

import os

import httpx

ANKI_CONNECT_URL = os.environ.get(
    "ANKI_CONNECT_URL", "http://localhost:8765"
)
TIMEOUT = float(os.environ.get("ANKI_CONNECT_TIMEOUT", "30"))


class AnkiConnectError(RuntimeError):
    """AnkiConnect returned an error for a request."""


async def anki_connect(action: str, **params) -> object:
    """Call an AnkiConnect action and unwrap the {result, error} envelope."""
    payload = {"action": action, "version": 6, "params": params}
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        response = await client.post(ANKI_CONNECT_URL, json=payload)
        response.raise_for_status()
        body = response.json()
    if body.get("error") is not None:
        raise AnkiConnectError(f"AnkiConnect {action} failed: {body['error']}")
    return body.get("result")


async def require_anki() -> None:
    """Raise a descriptive error if Anki/AnkiConnect is not reachable."""
    try:
        await anki_connect("version")
    except Exception as exc:  # noqa: BLE001 - surfaced verbatim to the caller
        raise AnkiConnectError(
            "Cannot reach AnkiConnect. Is Anki running with the AnkiConnect "
            f"add-on listening at {ANKI_CONNECT_URL}? ({exc})"
        ) from exc
