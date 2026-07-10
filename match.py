import sqlite3
from collections import Counter, defaultdict

import config

DB_PATH = "fingerprints.db"


def _best_alignment_per_song(clip_hashes, conn):
    
    offset_votes = Counter()
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


        relative_percent = min(100.0, round((top_votes / total_clip_hashes) * 100, 1))

        if total_clip_hashes < config.SHORT_CLIP_HASH_COUNT:
            minimum_votes = max(
                config.MIN_ABSOLUTE_MATCHES_SHORT,
                int(total_clip_hashes * config.MIN_SHORT_VOTE_RATE),
            )
        else:
            minimum_votes = config.MIN_ABSOLUTE_MATCHES

        passes_absolute = top_votes >= minimum_votes
        passes_relative = relative_percent >= config.MIN_CONFIDENCE_PERCENT
        passes_lead = (
            runner_up_votes == 0
            or (top_votes / max(runner_up_votes, 1)) >= config.MIN_LEAD_RATIO
        )

        if not (passes_absolute and passes_relative and passes_lead):
            return _no_match(
                reason="No confident match found.",
                debug_top_votes=top_votes,
                debug_confidence=relative_percent,
            )

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
