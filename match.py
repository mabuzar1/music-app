"""
match.py
--------
Matching engine: takes a recorded clip and decides whether it corresponds
to any song in the database.

=== THE BUG THIS FILE FIXES ===
The original version accepted a match whenever it found >= 5 hash votes
for some song, with no relation to how many hashes the clip actually
produced, and no comparison against other candidates. That meant:
  - A short or noisy clip that matched NO real song could still rack up
    a handful of coincidental hash collisions and get reported as a
    confident match.
  - There was no "No Match Found" outcome at all - the app always
    guessed *something*.

=== THE FIX ===
A match is now only accepted if it passes THREE independent checks
(see config.py for the tunable numbers):
  1. Absolute votes   >= MIN_ABSOLUTE_MATCHES
  2. Relative votes   >= MIN_CONFIDENCE_PERCENT of the clip's own hash count
  3. Lead over runner-up >= MIN_LEAD_RATIO (the winner must clearly stand
     out from the second-best candidate, not just barely win a crowded field)

If any check fails, the function returns a "No Match Found" result instead
of guessing.
"""

import sqlite3
from collections import Counter, defaultdict

import config

DB_PATH = "fingerprints.db"


def _best_alignment_per_song(clip_hashes, conn):
    """
    For every hash in the clip, look up which (song_id, stored_offset)
    pairs share that hash, and tally votes by (song_id, time_delta).

    Grouping by time_delta (not just song_id) is what separates a real
    match from noise: real matches have MANY hashes agreeing on the SAME
    delta (the clip's position within the song), whereas coincidental
    hash collisions scatter across many different deltas.

    Returns: dict {song_id: best_vote_count_for_that_song}
    """
    offset_votes = Counter()

    # Batch the lookup: gather all hashes first, then query in chunks,
    # instead of one query per hash (much faster for longer clips).
    hash_to_offsets = defaultdict(list)
    clip_hash_list = [h for h, _ in clip_hashes]

    cursor = conn.cursor()
    CHUNK = 500
    for i in range(0, len(clip_hash_list), CHUNK):
        chunk = clip_hash_list[i:i + CHUNK]
        placeholders = ",".join("?" * len(chunk))
        rows = cursor.execute(
            f"SELECT hash, song_id, offset FROM hashes WHERE hash IN ({placeholders})",
            chunk,
        ).fetchall()
        for h, song_id, db_offset in rows:
            hash_to_offsets[h].append((song_id, db_offset))

    for h, clip_offset in clip_hashes:
        for song_id, db_offset in hash_to_offsets.get(h, []):
            delta = db_offset - clip_offset
            offset_votes[(song_id, delta)] += 1

    # Collapse to the single best-aligned delta per song
    best_per_song = {}
    for (song_id, delta), count in offset_votes.items():
        if song_id not in best_per_song or count > best_per_song[song_id]:
            best_per_song[song_id] = count

    return best_per_song


def identify_song(clip_path):
    """
    Identify the song a recorded clip most likely came from.

    Returns a dict describing the outcome. When no confident match is
    found, match=False and the caller should display "No Match Found"
    rather than any guessed song.
    """
    from fingerprint import fingerprint_file  # local import avoids unused cost when unused

    conn = sqlite3.connect(DB_PATH)
    try:
        clip_hashes = fingerprint_file(clip_path)
        total_clip_hashes = len(clip_hashes)

        if total_clip_hashes == 0:
            return _no_match(reason="Could not extract any audio features from the clip.")

        best_per_song = _best_alignment_per_song(clip_hashes, conn)

        if not best_per_song:
            return _no_match(reason="No fingerprint overlap with any stored song.")

        # Rank candidates by vote count, best first
        ranked = sorted(best_per_song.items(), key=lambda kv: kv[1], reverse=True)
        top_song_id, top_votes = ranked[0]
        runner_up_votes = ranked[1][1] if len(ranked) > 1 else 0

        # --- Internal gating metric (used only for the accept/reject decision) ---
        # Raw votes as a % of the clip's own hash count. This scales correctly
        # with clip length but gets diluted by heavy background noise (noise
        # inflates the clip's total hash count without adding real votes),
        # so it is NOT what we show to the user - see confidence_score below.
        relative_percent = min(100.0, round((top_votes / total_clip_hashes) * 100, 1))

        # --- The three-part rejection check (the bug fix) ---
        passes_absolute = top_votes >= config.MIN_ABSOLUTE_MATCHES
        passes_relative = relative_percent >= config.MIN_CONFIDENCE_PERCENT
        passes_lead = (
            runner_up_votes == 0
            or (top_votes / max(runner_up_votes, 1)) >= config.MIN_LEAD_RATIO
        )

        if not (passes_absolute and passes_relative and passes_lead):
            return _no_match(
                reason="Best candidate did not clear the confidence threshold.",
                debug_top_votes=top_votes,
                debug_confidence=relative_percent,
            )

        # --- User-facing confidence score (0-100%) ---
        # This is a SEPARATE calculation from the gate above. It answers a
        # different question: "of the songs in the database, how clearly
        # did this one stand out?" rather than "what fraction of the clip
        # matched?" (the latter is naturally low for noisy clips even on a
        # correct match, and would look alarming to a user despite being
        # a confidently correct result).
        #
        # It combines two things:
        #   dominance - how much the winner beat the runner-up by
        #               (1.0 = total dominance, 0.5 = barely ahead)
        #   strength  - how large the winning vote count is in absolute
        #               terms, saturating once it is comfortably past the
        #               minimum floor (so a huge vote count doesn't need
        #               to keep pushing the score higher forever)
        dominance = top_votes / (top_votes + runner_up_votes) if runner_up_votes else 1.0
        strength = min(1.0, top_votes / (config.MIN_ABSOLUTE_MATCHES * 3))
        confidence_score = round(100 * dominance * (0.5 + 0.5 * strength), 1)
        confidence_score = max(0.0, min(100.0, confidence_score))

        song_row = conn.execute(
            "SELECT name, artist, album, genre, duration, cover_path FROM songs WHERE id = ?",
            (top_song_id,),
        ).fetchone()

        if song_row is None:
            return _no_match(reason="Matched song id missing from metadata table.")

        name, artist, album, genre, duration, cover_path = song_row

        return {
            "match": True,
            "song": name,
            "artist": artist,
            "album": album,
            "genre": genre,
            "duration_seconds": duration,
            "cover_path": cover_path,
            "confidence_score": confidence_score,
            "raw_votes": top_votes,
        }
    finally:
        conn.close()


def _no_match(reason="", debug_top_votes=0, debug_confidence=0.0):
    return {
        "match": False,
        "song": None,
        "reason": reason,
        "confidence_score": debug_confidence,
        "raw_votes": debug_top_votes,
    }
