"""
metadata.py
-----------
Extracts song metadata (title, artist, album, genre) and embedded album
art from audio files using the Mutagen library, with safe fallbacks when
tags are missing (common with informally-ripped or renamed files).
"""

import os
from mutagen import File as MutagenFile


def extract_metadata(file_path):
    """
    Read ID3/Vorbis/MP4 tags from an audio file.
    Returns a dict with title, artist, album, genre - falling back to
    the filename for the title, and "Unknown" for anything else missing.
    """
    filename_title = os.path.splitext(os.path.basename(file_path))[0]

    metadata = {
        "title": filename_title,
        "artist": "Unknown Artist",
        "album": "Unknown Album",
        "genre": "Unknown",
    }

    try:
        audio = MutagenFile(file_path, easy=True)
        if audio is not None and audio.tags:
            tags = audio.tags
            metadata["title"] = _first_tag(tags, "title") or filename_title
            metadata["artist"] = _first_tag(tags, "artist") or metadata["artist"]
            metadata["album"] = _first_tag(tags, "album") or metadata["album"]
            metadata["genre"] = _first_tag(tags, "genre") or metadata["genre"]
    except Exception:
        # A file with corrupt/unsupported tags should never crash the
        # whole database build - just fall back to defaults.
        pass

    return metadata


def _first_tag(tags, key):
    """Safely grab the first value of a tag key, if present."""
    value = tags.get(key)
    if value:
        return str(value[0])
    return None


def extract_cover_art(file_path, output_path):
    """
    Extract embedded album art (if any) and save it as a JPEG at
    output_path. Returns True if artwork was found and saved, else False.
    Supports the common embedded-art formats: ID3 APIC (mp3), MP4 covr
    (m4a), and FLAC pictures.
    """
    try:
        audio = MutagenFile(file_path)
        if audio is None:
            return False

        image_data = None

        # MP3 (ID3 APIC frames)
        if hasattr(audio, "tags") and audio.tags:
            for tag in audio.tags.values():
                if tag.__class__.__name__ == "APIC":
                    image_data = tag.data
                    break

        # FLAC embedded pictures
        if image_data is None and hasattr(audio, "pictures") and audio.pictures:
            image_data = audio.pictures[0].data

        # MP4 / M4A covr atom
        if image_data is None and "covr" in getattr(audio, "tags", {}) if audio.tags else False:
            covers = audio.tags["covr"]
            if covers:
                image_data = bytes(covers[0])

        if image_data:
            with open(output_path, "wb") as f:
                f.write(image_data)
            return True

    except Exception:
        pass

    return False
