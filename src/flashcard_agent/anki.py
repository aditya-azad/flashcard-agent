"""Thin async client for the AnkiConnect HTTP API (http://localhost:8765)."""

import asyncio
import logging
import os
import shutil
import subprocess
import sys
import time

import httpx

logger = logging.getLogger(__name__)

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


def _connect_error(exc: Exception) -> AnkiConnectError:
    """Build a descriptive error for an unreachable AnkiConnect."""
    return AnkiConnectError(
        "Cannot reach AnkiConnect. Is Anki running with the AnkiConnect "
        f"add-on listening at {ANKI_CONNECT_URL}? ({exc})"
    )


async def require_anki() -> None:
    """Raise a descriptive error if Anki/AnkiConnect is not reachable."""
    try:
        await anki_connect("version")
    except Exception as exc:  # noqa: BLE001 - surfaced verbatim to the caller
        raise _connect_error(exc) from exc


async def _ping_anki() -> bool:
    """Return True if AnkiConnect answers a version request."""
    try:
        await anki_connect("version")
        return True
    except Exception:  # noqa: BLE001 - any failure means not ready
        return False


async def ensure_anki_running(
    timeout: float = float(os.environ.get("ANKI_START_TIMEOUT", "30")),
) -> None:
    """Ping AnkiConnect, starting Anki in the background if it is not up.

    Raises AnkiConnectError if Anki could not be started or did not answer
    within ``timeout`` seconds.
    """
    if await _ping_anki():
        return

    logger.info("AnkiConnect not reachable; attempting to start Anki")
    try:
        # Detach from this process so Anki outlives the MCP server, and
        # redirect stdio so a GUI app logging to stdout cannot corrupt the
        # MCP stdio transport.
        subprocess.Popen(
            ["anki"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
    except Exception as exc:
        raise AnkiConnectError(f"Failed to launch Anki: {exc}") from exc

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        await asyncio.sleep(0.5)
        if await _ping_anki():
            logger.info("AnkiConnect is up after starting Anki")
            return
    raise AnkiConnectError(
        f"Started Anki but AnkiConnect did not answer within {timeout}s "
        f"at {ANKI_CONNECT_URL}"
    )
