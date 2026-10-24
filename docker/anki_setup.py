"""Headless Anki bootstrap + AnkiWeb sign-in for the flashcard-agent container.

Run by the container entrypoint before Anki starts. Two jobs:

1. Seed the Anki base dir's prefs21.db with a default profile and
   firstRun=False, so Anki skips its interactive first-run language dialog
   (which would otherwise block a headless container). Same pickle-in-SQLite
   storage the desktop GUI uses.

2. If ANKIWEB_EMAIL/ANKIWEB_PASSWORD are set (e.g. via a .env file), sign in
   to AnkiWeb, download the account's collection into the base dir, and
   persist the sync credentials in the profile exactly the way the desktop
   sign-in does, so Anki starts up already signed in.

   ANKIWEB_SYNC_URL optionally points at a self-hosted Anki sync server
   instead of AnkiWeb; it is used for sign-in and stored as the profile's
   customSyncUrl so Anki's own auto-syncs hit the same server.

Runs under the interpreter bundled inside the official Anki tarball (which
provides the matching `anki` library via PYTHONPATH), but only imports it
when credentials are present.
"""

import os
import pickle
import random
import sqlite3
import time
from pathlib import Path

BASE = Path(os.environ.get("ANKI_BASE", "/data/anki"))
PREFS = BASE / "prefs21.db"

# Mirrors aqt.profiles.metaConf / profileConf. Anki treats every key as
# optional (lookup with .get and defaults), so this stays forward-compatible.
META_CONF = {
    "ver": 0,
    "updates": False,
    "created": int(time.time()),
    "id": random.randrange(0, 2**63),
    "lastMsg": 0,
    "suppressUpdate": False,
    "firstRun": False,
    "defaultLang": "en",
}
PROFILE_CONF = {
    "mainWindowGeom": None,
    "mainWindowState": None,
    "numBackups": 50,
    "lastOptimize": int(time.time()),
    "searchHistory": [],
    "syncKey": None,
    "syncMedia": True,
    "autoSync": True,
    "allowHTML": False,
    "importMode": 1,
    "lastColour": "#00f",
    "stripHTML": True,
    "deleteMedia": False,
}


def seed_prefs() -> str:
    """Ensure prefs21.db has meta and one profile; return the profile name."""
    db = sqlite3.connect(PREFS)
    try:
        db.execute(
            "create table if not exists profiles "
            "(name text primary key collate nocase, data blob not null)"
        )
        if (
            db.execute("select 1 from profiles where name = '_global'").fetchone()
            is None
        ):
            db.execute(
                "insert or replace into profiles values ('_global', ?)",
                (pickle.dumps(META_CONF, protocol=4),),
            )
        existing = [
            row[0]
            for row in db.execute("select name from profiles where name != '_global'")
        ]
        if existing:
            profile = existing[0]
            print(f"Using existing Anki profile {profile!r}")
        else:
            profile = "User 1"
            db.execute(
                "insert or replace into profiles values (?, ?)",
                (profile, pickle.dumps(PROFILE_CONF, protocol=4)),
            )
            print(f"Seeded default Anki profile {profile!r}")
        db.commit()
        return profile
    finally:
        db.close()


def ankiweb_login(email: str, password: str, profile: str) -> None:
    from anki.collection import Collection  # bundled anki lib, matching version

    endpoint = os.environ.get("ANKIWEB_SYNC_URL") or None
    profile_dir = BASE / profile
    profile_dir.mkdir(parents=True, exist_ok=True)
    collection_path = profile_dir / "collection.anki2"
    print(f"Opening collection at {collection_path}")
    col = Collection(str(collection_path))
    try:
        print(f"Signing in as {email} (endpoint: {endpoint or 'AnkiWeb'})...")
        auth = col.sync_login(email, password, endpoint)
        print("Signed in; syncing collection (first sync may take a while)...")
        out = col.sync_collection(auth, True)
        print(f"Sync finished: {out}")
        hkey = auth.hkey
    finally:
        col.close()

    # Persist credentials the same way the desktop GUI sign-in does: the
    # pickled profile dict carries "syncKey"/"syncUser", which the GUI reads
    # to consider itself signed in.
    db = sqlite3.connect(PREFS)
    try:
        row = db.execute(
            "select data from profiles where name = ?", (profile,)
        ).fetchone()
        prof = pickle.loads(row[0])
        prof["syncKey"] = hkey
        prof["syncUser"] = email
        if endpoint:
            prof["customSyncUrl"] = endpoint
        db.execute(
            "update profiles set data = ? where name = ?",
            (pickle.dumps(prof, protocol=4), profile),
        )
        db.commit()
        print(f"Stored sync credentials in profile {profile!r}")
    finally:
        db.close()


def main() -> None:
    email = os.environ.get("ANKIWEB_EMAIL")
    password = os.environ.get("ANKIWEB_PASSWORD")
    profile = seed_prefs()
    if email and password:
        ankiweb_login(email, password, profile)
    else:
        print("No ANKIWEB credentials set; skipping AnkiWeb sign-in")


if __name__ == "__main__":
    main()
