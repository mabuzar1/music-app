"""
match.py
--------
Takes a recorded audio clip, fingerprints it, and compares it against
the stored database to find the best matching song.

Key idea: matching hashes alone isn't enough (noise can cause a few
random matches by chance). What makes a match reliable is that many
matching hashes share the SAME time offset difference between the
clip and the original song. This is called "offset alignment".
"""

import sqlite3
from collections import Counter
from fingerprint import fingerprint_file

DB_PATH = "fingerprints.db"


def identify_song(clip_path, min_confidence=5):
    """
    Returns a dict with the identified song name and confidence score,
    or None if no confident match was found.
    """
    conn = sqlite3.connect(DB_PATH)
    clip_hashes = fingerprint_file(clip_path)

    if not clip_hashes:
        conn.close()
        return None

    # For each hash in the clip, look up which songs have that same hash
    # and at what offset. We track (song_id, offset_difference) pairs.
    offset_votes = Counter()
    song_names = {}

    for h, clip_offset in clip_hashes:
        rows = conn.execute(
            "SELECT song_id, offset FROM hashes WHERE hash = ?", (h,)
        ).fetchall()

        for song_id, db_offset in rows:
            # If this is a real match, db_offset - clip_offset should be
            # roughly the same value across many hashes for the correct song.
            delta = db_offset - clip_offset
            offset_votes[(song_id, delta)] += 1

    if not offset_votes:
        conn.close()
        return None

    # The (song_id, delta) combination with the most votes is our best guess
    (best_song_id, _best_delta), best_score = offset_votes.most_common(1)[0]

    if best_score < min_confidence:
        conn.close()
        return None

    row = conn.execute(
        "SELECT name FROM songs WHERE id = ?", (best_song_id,)
    ).fetchone()
    conn.close()

    if row is None:
        return None

    return {
        "song": row[0],
        "confidence_score": best_score,
    }
