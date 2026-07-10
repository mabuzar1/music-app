"""
build_database.py
------------------
Run this once (and again whenever you add/change songs) to:
1. Read every audio file in songs/
2. Extract metadata (title, artist, album, genre) and embedded cover art
3. Generate each song's audio fingerprint
4. Store everything in fingerprints.db (SQLite)

Usage:
    python build_database.py
"""

import os
import sqlite3

from fingerprint import fingerprint_file, get_duration_seconds
from metadata import extract_metadata, extract_cover_art

SONGS_FOLDER = "songs"
COVERS_FOLDER = "static/covers"
DB_PATH = "fingerprints.db"


def create_tables(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS songs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            artist TEXT,
            album TEXT,
            genre TEXT,
            duration REAL,
            cover_path TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS hashes (
            hash INTEGER NOT NULL,
            song_id INTEGER NOT NULL,
            offset INTEGER NOT NULL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_hash ON hashes (hash)")
    conn.commit()


def build_database():
    os.makedirs(COVERS_FOLDER, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    create_tables(conn)

    # Clean rebuild every time this script runs
    conn.execute("DELETE FROM songs")
    conn.execute("DELETE FROM hashes")
    conn.commit()

    audio_files = sorted(
        f for f in os.listdir(SONGS_FOLDER)
        if f.lower().endswith((".mp3", ".wav", ".m4a", ".flac", ".ogg"))
    )

    if not audio_files:
        print(f"No audio files found in '{SONGS_FOLDER}/'. Add your songs there first.")
        return

    for filename in audio_files:
        path = os.path.join(SONGS_FOLDER, filename)
        print(f"Processing: {filename} ...")

        meta = extract_metadata(path)
        duration = get_duration_seconds(path)

        cover_filename = f"{os.path.splitext(filename)[0]}.jpg"
        cover_full_path = os.path.join(COVERS_FOLDER, cover_filename)
        has_cover = extract_cover_art(path, cover_full_path)
        cover_path = f"/static/covers/{cover_filename}" if has_cover else None

        cursor = conn.execute(
            "INSERT INTO songs (name, artist, album, genre, duration, cover_path) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (meta["title"], meta["artist"], meta["album"], meta["genre"], duration, cover_path),
        )
        song_id = cursor.lastrowid

        hashes = fingerprint_file(path)
        rows = [(h, song_id, offset) for (h, offset) in hashes]
        conn.executemany(
            "INSERT INTO hashes (hash, song_id, offset) VALUES (?, ?, ?)",
            rows,
        )
        conn.commit()

        cover_note = "cover art found" if has_cover else "no cover art"
        print(f"  -> {meta['title']} by {meta['artist']} | "
              f"{len(rows)} hashes | {duration:.1f}s | {cover_note}")

    print(f"\nDatabase build complete. {len(audio_files)} songs indexed in {DB_PATH}")
    conn.close()


if __name__ == "__main__":
    build_database()
