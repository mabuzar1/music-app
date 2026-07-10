import numpy as np
import librosa

import config
def load_audio(file_path): 
    y, sr = librosa.load(file_path, sr=config.SAMPLE_RATE, mono=True)
    y_trimmed, _ = librosa.effects.trim(y, top_db=30)
    if len(y_trimmed) > 0:
        y = y_trimmed
    peak = np.max(np.abs(y))
    if peak > 1e-8:
        y = y / peak
    y = librosa.effects.preemphasis(y)

    return y, sr
def compute_spectrogram(y):
    stft_result = librosa.stft(y, n_fft=config.N_FFT, hop_length=config.HOP_LENGTH)
    magnitude = np.abs(stft_result)
    log_magnitude = np.log1p(magnitude)  # log1p avoids log(0) issues
    return log_magnitude
def find_peaks(spectrogram):
    n_freq_bins, n_time_frames = spectrogram.shape
    band_edges = np.linspace(0, n_freq_bins, config.NUM_BANDS + 1, dtype=int)

    global_noise_floor = np.percentile(spectrogram, 35) * config.NOISE_PEAK_FACTOR
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
            band_noise_floor = np.median(band_slice) * config.NOISE_PEAK_FACTOR
            threshold = max(config.MIN_PEAK_ENERGY, global_noise_floor, band_noise_floor)
            if amplitude > threshold:
                freq_idx = lo + local_idx
                peaks.append((t, freq_idx))

    return peaks
def find_beat_peaks(y, sr):
    onset_env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=config.HOP_LENGTH)
    _, beat_frames = librosa.beat.beat_track(onset_envelope=onset_env, sr=sr, hop_length=config.HOP_LENGTH)
    return [(int(frame), config.BEAT_FREQ_INDEX) for frame in beat_frames]
def generate_hashes(peaks):
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
    y, sr = load_audio(file_path)
    spectrogram = compute_spectrogram(y)
    peaks = find_peaks(spectrogram)
    beat_peaks = find_beat_peaks(y, sr)
    combined_peaks = sorted(peaks + beat_peaks, key=lambda p: p[0])
    hashes = generate_hashes(combined_peaks)
    return hashes
def get_duration_seconds(file_path):
    return float(librosa.get_duration(path=file_path))
