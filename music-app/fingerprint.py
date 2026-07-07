"""
fingerprint.py
--------------
Core audio fingerprinting logic, inspired by the Shazam algorithm.

Steps:
1. Load audio and compute a spectrogram using the Short-Time Fourier
   Transform (STFT), which is the FFT applied over small time windows.
2. Find "peaks" in the spectrogram - points where a frequency is much
   louder than its neighbors. These peaks are stable and noise-resistant.
3. Pair up nearby peaks and turn each pair into a hash based on
   (frequency1, frequency2, time_difference). This hash is the
   "fingerprint" building block.
"""

import numpy as np
import librosa
from scipy.ndimage import maximum_filter

SAMPLE_RATE = 22050        # audio sample rate used for all processing
N_FFT = 2048                # FFT window size
HOP_LENGTH = 512            # step size between FFT windows
PEAK_NEIGHBORHOOD = 20       # size of the local area used to find peaks
FAN_VALUE = 5                # how many neighboring peaks to pair with
MIN_TIME_DELTA = 0            # ignore pairs with 0 time difference
MAX_TIME_DELTA = 200           # ignore pairs that are too far apart in time


def load_audio(file_path):
    """Load an audio file and resample it to a consistent sample rate."""
    y, sr = librosa.load(file_path, sr=SAMPLE_RATE, mono=True)
    return y, sr


def compute_spectrogram(y):
    """Convert the audio waveform into a spectrogram using STFT (FFT)."""
    stft_result = librosa.stft(y, n_fft=N_FFT, hop_length=HOP_LENGTH)
    spectrogram = np.abs(stft_result)  # magnitude only, ignore phase
    return spectrogram


def find_peaks(spectrogram, num_bands=6, min_amplitude=1e-6):
    """
    Find the strongest, most distinctive points in the spectrogram using
    a "banded peak" approach (the same idea used by Shazam's algorithm).

    Instead of picking peaks using one global loudness threshold (which
    background noise can easily distort, since noise raises the
    overall energy level everywhere), we split the frequency range into
    several bands and pick the single loudest point in each band, for
    every time frame. This keeps the number of peaks stable and keeps
    the peaks concentrated on the true musical tones rather than noise.
    """
    n_freq_bins, n_time_frames = spectrogram.shape
    band_edges = np.linspace(0, n_freq_bins, num_bands + 1, dtype=int)

    peaks = []
    for t in range(n_time_frames):
        column = spectrogram[:, t]
        for b in range(num_bands):
            lo, hi = band_edges[b], band_edges[b + 1]
            if hi <= lo:
                continue
            band_slice = column[lo:hi]
            local_idx = np.argmax(band_slice)
            amplitude = band_slice[local_idx]
            if amplitude > min_amplitude:
                freq_idx = lo + local_idx
                peaks.append((t, int(freq_idx)))

    return peaks


def generate_hashes(peaks):
    """
    Pair each peak with a few nearby peaks that come after it in time,
    and turn each pair into a single hash value:
        hash = (freq_of_peak_1, freq_of_peak_2, time_gap_between_them)
    Returns a list of (hash, time_offset_of_first_peak) tuples.
    """
    peaks = sorted(peaks, key=lambda p: p[0])  # sort by time
    hashes = []

    for i in range(len(peaks)):
        t1, f1 = peaks[i]
        for j in range(1, FAN_VALUE + 1):
            if i + j < len(peaks):
                t2, f2 = peaks[i + j]
                dt = t2 - t1
                if MIN_TIME_DELTA < dt <= MAX_TIME_DELTA:
                    h = hash((f1, f2, dt))
                    hashes.append((h, t1))

    return hashes


def fingerprint_file(file_path):
    """
    Full pipeline: audio file -> waveform -> spectrogram -> peaks -> hashes.
    This is the single function used both when building the database
    and when matching a newly recorded clip.
    """
    y, sr = load_audio(file_path)
    spectrogram = compute_spectrogram(y)
    peaks = find_peaks(spectrogram)
    hashes = generate_hashes(peaks)
    return hashes
