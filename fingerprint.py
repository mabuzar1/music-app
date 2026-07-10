"""
fingerprint.py
--------------
Audio fingerprinting engine (Shazam-style "constellation map" approach).

Pipeline:
    audio file
      -> load + clean (trim silence, normalize volume)
      -> spectrogram (STFT / FFT)
      -> log-scaled magnitude (compresses loud/quiet gap, helps with
         low-quality recordings)
      -> banded peak picking (constellation map, noise-resistant)
      -> peak pairing -> fingerprint hashes

This module is used both when building the database (full songs) and when
matching a freshly recorded clip, so any accuracy improvement here benefits
both sides equally.
"""

import numpy as np
import librosa

import config


def load_audio(file_path):
    """
    Load an audio file, convert to mono, resample to a consistent rate,
    trim leading/trailing silence, and normalize volume.

    Trimming silence matters because a recorded clip often has a second
    of silence at the start (time to hold the phone up) that shifts every
    peak's timestamp and can throw off matching. Volume normalization
    helps recognize quiet or poorly recorded clips.
    """
    y, sr = librosa.load(file_path, sr=config.SAMPLE_RATE, mono=True)

    # Trim silence from both ends (top_db=30 means: anything 30dB quieter
    # than the peak volume counts as silence).
    y_trimmed, _ = librosa.effects.trim(y, top_db=30)
    if len(y_trimmed) > 0:
        y = y_trimmed

    # Normalize peak amplitude to 1.0 so quiet recordings get analyzed
    # with the same effective "loudness" as clean studio audio.
    peak = np.max(np.abs(y))
    if peak > 1e-8:
        y = y / peak

    return y, sr


def compute_spectrogram(y):
    """
    Convert the waveform into a spectrogram using the Short-Time Fourier
    Transform (STFT), then apply log-scaling to the magnitude.

    Log-scaling compresses the difference between very loud and very quiet
    frequency content, which mirrors how humans perceive loudness and makes
    faint-but-real musical tones easier to detect against background noise.
    """
    stft_result = librosa.stft(y, n_fft=config.N_FFT, hop_length=config.HOP_LENGTH)
    magnitude = np.abs(stft_result)
    log_magnitude = np.log1p(magnitude)  # log1p avoids log(0) issues
    return log_magnitude


def find_peaks(spectrogram):
    """
    Find the strongest points in the spectrogram using banded peak picking.

    The frequency axis is split into config.NUM_BANDS bands. For every time
    frame, we keep the single loudest point in each band (if it clears a
    minimum energy floor). This keeps the number of peaks stable and
    concentrated on real musical content, rather than letting broadband
    background noise flood the results the way a single global threshold
    would.
    """
    n_freq_bins, n_time_frames = spectrogram.shape
    band_edges = np.linspace(0, n_freq_bins, config.NUM_BANDS + 1, dtype=int)

    peaks = []
    for t in range(n_time_frames):
        column = spectrogram[:, t]
        for b in range(config.NUM_BANDS):
            lo, hi = band_edges[b], band_edges[b + 1]
            if hi <= lo:
                continue
            band_slice = column[lo:hi]
            local_idx = int(np.argmax(band_slice))
            amplitude = band_slice[local_idx]
            if amplitude > config.MIN_PEAK_ENERGY:
                freq_idx = lo + local_idx
                peaks.append((t, freq_idx))

    return peaks


def generate_hashes(peaks):
    """
    Pair each peak ("anchor") with several peaks that follow it in time
    ("targets"), and encode each pair as a single hash:

        hash = (anchor_frequency, target_frequency, time_gap)

    Returns a list of (hash, anchor_time) tuples. The anchor_time is kept
    so that, during matching, we can check whether many hashes agree on
    the same time offset between the clip and a candidate song.
    """
    peaks = sorted(peaks, key=lambda p: p[0])
    hashes = []

    for i in range(len(peaks)):
        t1, f1 = peaks[i]
        for j in range(1, config.FAN_VALUE + 1):
            if i + j < len(peaks):
                t2, f2 = peaks[i + j]
                dt = t2 - t1
                if config.MIN_TIME_DELTA <= dt <= config.MAX_TIME_DELTA:
                    h = hash((f1, f2, dt))
                    hashes.append((h, t1))

    return hashes


def fingerprint_file(file_path):
    """
    Full pipeline: audio file -> cleaned waveform -> spectrogram -> peaks
    -> fingerprint hashes. This single function is the one source of truth
    used everywhere fingerprints are generated, so the database and any
    incoming clip are always processed identically.
    """
    y, sr = load_audio(file_path)
    spectrogram = compute_spectrogram(y)
    peaks = find_peaks(spectrogram)
    hashes = generate_hashes(peaks)
    return hashes


def get_duration_seconds(file_path):
    """Return the duration of an audio file in seconds (for metadata)."""
    return float(librosa.get_duration(path=file_path))
