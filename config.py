"""
config.py
---------
Central place for every tunable constant in the system.
Keeping these in one file makes it easy to tune accuracy vs. speed
without hunting through multiple modules.
"""

# ---------------------------------------------------------------------------
# Audio processing
# ---------------------------------------------------------------------------
SAMPLE_RATE = 22050          # audio is resampled to this rate before analysis
N_FFT = 4096                  # FFT window size (bigger = better frequency
                              # resolution, at the cost of time resolution).
                              # Raised from 2048 -> 4096 for higher accuracy.
HOP_LENGTH = 1024              # step size between FFT windows (in samples)

# ---------------------------------------------------------------------------
# Peak detection ("constellation map")
# ---------------------------------------------------------------------------
NUM_BANDS = 10                 # number of frequency bands per time frame.
                              # Raised from 6 -> 10 for finer-grained peaks,
                              # which improves matching accuracy on short clips.
MIN_PEAK_ENERGY = 1e-4         # peaks quieter than this (near silence) are
                              # ignored so silence doesn't generate noise hashes
NOISE_PEAK_FACTOR = 1.4        # dynamic threshold factor used per band to
                              # ignore weak noise peaks in noisy clips.
BEAT_FREQ_INDEX = 10000        # synthetic frequency used for beat-based fingerprinting

# ---------------------------------------------------------------------------
# Fingerprint hashing
# ---------------------------------------------------------------------------
FAN_VALUE = 8                  # how many neighboring peaks each anchor peak
                              # pairs with. Raised from 5 -> 8: more hashes
                              # per song = more chances of a correct match,
                              # at a small storage/speed cost.
MIN_TIME_DELTA = 1              # ignore same-instant pairs
MAX_TIME_DELTA = 300             # ignore pairs spread too far apart in time

# ---------------------------------------------------------------------------
# Recording (frontend requests this many seconds from the browser)
# ---------------------------------------------------------------------------
RECORD_SECONDS = 12              # Raised from 6 -> 12 seconds. Longer clips
                              # provide far more fingerprint data, which is
                              # the single biggest lever for accuracy on
                              # noisy or ambiguous recordings.

# ---------------------------------------------------------------------------
# Matching / confidence thresholds  <-- THIS SECTION FIXES THE FALSE-POSITIVE 
# ---------------------------------------------------------------------------
# The old version accepted a match if it found >= 5 aligned hashes, no matter
# how small that number was relative to the clip. On a clip that doesn't
# exist in the database, random hash collisions could still reach 5+ votes,
# especially as the database grows - causing confident-looking wrong answers.
#
# The fix uses THREE independent checks, and a match is only accepted if
# ALL three pass:
MIN_ABSOLUTE_MATCHES = 12        # 1) raw vote count must clear a floor
MIN_CONFIDENCE_PERCENT = 2.0      # 2) votes as a % of the clip's own hash
                                  #    count must also clear a floor (this
                                  #    scales correctly with clip length,
                                  #    unlike a fixed absolute number).
                                  #    Kept low-ish because heavy background
                                  #    noise inflates the clip's total hash
                                  #    count without adding real votes - the
                                  #    absolute-vote and lead-ratio checks
                                  #    below are what really guard against
                                  #    false positives in that situation.
MIN_LEAD_RATIO = 1.5              # 3) the best-scoring song must beat the
                                  #    SECOND-best song by at least this
                                  #    ratio. Real matches dominate; random
                                  #    noise tends to spread votes evenly
                                  #    across many songs instead.

# ---------------------------------------------------------------------------
# Short / partial clip handling
# ---------------------------------------------------------------------------
SHORT_CLIP_HASH_COUNT = 80      # clips with fewer hashes are treated as short/partial
MIN_ABSOLUTE_MATCHES_SHORT = 6  # lower absolute vote floor for short clips
MIN_SHORT_VOTE_RATE = 0.12      # require at least this fraction of clip hashes for short clips

# ---------------------------------------------------------------------------
# Upload limits
# ---------------------------------------------------------------------------
MAX_UPLOAD_MB = 20
ALLOWED_EXTENSIONS = {"mp3", "wav", "m4a", "flac", "ogg", "webm"}
