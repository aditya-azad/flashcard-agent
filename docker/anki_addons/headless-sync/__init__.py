"""Auto-answer Anki's full-sync confirmation dialogs in headless containers.

aqt asks for confirmation whenever a full sync is required ("AnkiWeb
collection has no cards. Replace it with local collection?", the
upload/download conflict prompt, etc.). With no display to click, those modals
block syncing forever, so this add-on replaces aqt.sync.full_sync with
non-destructive automatic answers:

- AnkiWeb is empty and local has data  -> full upload (data moves to the server)
- Local is empty and AnkiWeb has data  -> full download (data moves locally)
- Both sides changed since last sync   -> per ANKI_SYNC_CONFLICT env:
    "cancel"   (default) skip the sync, never destroy data
    "upload"                resolve by uploading local state
    "download"              resolve by downloading server state

The empty-side cases never overwrite existing data, so they are always safe;
only a genuine conflict is configurable.
"""

import os

from aqt import sync as aqt_sync

POLICY = os.environ.get("ANKI_SYNC_CONFLICT", "cancel").lower().strip()


def _server_usn(mw, out):
    return out.server_media_usn if mw.pm.media_syncing_enabled() else None


def _full_sync(mw, out, on_done) -> None:
    server_usn = _server_usn(mw, out)
    if out.required == out.FULL_UPLOAD:
        # AnkiWeb has no cards / is behind; push local state.
        print("[headless-sync] server collection empty -> auto full upload")
        aqt_sync.full_upload(mw, server_usn, on_done)
    elif out.required == out.FULL_DOWNLOAD:
        # Local collection is empty; pull server state.
        print("[headless-sync] local collection empty -> auto full download")
        aqt_sync.full_download(mw, server_usn, on_done)
    elif POLICY == "upload":
        print("[headless-sync] sync conflict -> resolving with full upload")
        aqt_sync.full_upload(mw, server_usn, on_done)
    elif POLICY == "download":
        print("[headless-sync] sync conflict -> resolving with full download")
        aqt_sync.full_download(mw, server_usn, on_done)
    else:
        print(
            "[headless-sync] WARNING: sync conflict (both sides changed) and "
            "ANKI_SYNC_CONFLICT=cancel; skipping this sync. Set "
            "ANKI_SYNC_CONFLICT=upload or =download to resolve automatically."
        )
        on_done()


aqt_sync.full_sync = _full_sync
