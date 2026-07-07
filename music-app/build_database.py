"""
build_database.py
------------------
Run this ONCE (and again any time you add/change songs) to:
1. Read every audio file in the songs/ folder
2. Generate its fingerprint (a set of hashes)
3. Store everything in a local SQLite database: fingerprints.db

Usage:
    python build_database.py
"""

import os
import sqlite3
from fingerprint import fingerprint_file

SONGS_FOLDER = "songs"
DB_PATH = "fingerprints.db"


def create_tables(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS songs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL
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
    conn = sqlite3.connect(DB_PATH)
    create_tables(conn)

    # Clear old data so re-running this script is always clean
    conn.execute("DELETE FROM songs")
    conn.execute("DELETE FROM hashes")
    conn.commit()

    audio_files = [
        f for f in os.listdir(SONGS_FOLDER)
        if f.lower().endswith((".mp3", ".wav", ".m4a", ".flac"))
    ]

    if not audio_files:
        print(f"No audio files found in '{SONGS_FOLDER}/'. "
              f"Add your 10 songs there first.")
        return

    for filename in audio_files:
        path = os.path.join(SONGS_FOLDER, filename)
        song_name = os.path.splitext(filename)[0]
        print(f"Processing: {song_name} ...")

        cursor = conn.execute(
            "INSERT INTO songs (name) VALUES (?)", (song_name,)
        )
        song_id = cursor.lastrowid

        hashes = fingerprint_file(path)
        rows = [(h, song_id, offset) for (h, offset) in hashes]
        conn.executemany(
            "INSERT INTO hashes (hash, song_id, offset) VALUES (?, ?, ?)",
            rows,
        )
        conn.commit()
        print(f"  -> stored {len(rows)} fingerprint hashes")

    print(f"\nDatabase build complete. {len(audio_files)} songs indexed in {DB_PATH}")
    conn.close()


if __name__ == "__main__":
    build_database()
