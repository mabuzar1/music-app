# Resona — Song Identifier (v2)

A Shazam/Spotify-inspired music recognition web app, upgraded from a basic
prototype to a modular, production-minded application.

## Project structure
```
music-app-v2/
├── app.py              # Flask backend: routes, error handling
├── config.py             # ALL tunable constants live here (accuracy/speed knobs)
├── fingerprint.py         # Audio -> spectrogram -> peaks -> fingerprint hashes
├── match.py               # Matching engine + confidence scoring + false-positive gate
├── metadata.py            # ID3/tag + embedded cover-art extraction (Mutagen)
├── build_database.py      # One-time script: fingerprints + metadata for your songs
├── requirements.txt
├── Dockerfile
├── songs/                 # Put your song files here
└── static/
    ├── index.html
    ├── logo.svg / favicon.svg     # Original "Resona" brand mark
    ├── css/style.css                # Dark glassmorphism theme
    └── js/app.js                     # Recording, waveform, upload, results
```

## Run locally
```bash
pip install -r requirements.txt
# Add your songs (mp3/wav/m4a/flac) into songs/
python build_database.py
python app.py
```
Open http://localhost:5000

## Deploy
```bash
docker build -t resona .
docker run -p 5000:5000 resona
```
Push to GitHub and deploy the Dockerfile on Render/Railway as before.

## Tuning accuracy vs. speed
Every threshold that affects accuracy lives in `config.py`, with comments
explaining what each one trades off:
- `N_FFT`, `NUM_BANDS`, `FAN_VALUE` — fingerprint detail (higher = more
  accurate, slightly slower to build/match)
- `RECORD_SECONDS` — how long the browser records (longer = more data = 
  higher accuracy, especially in noisy environments)
- `MIN_ABSOLUTE_MATCHES`, `MIN_CONFIDENCE_PERCENT`, `MIN_LEAD_RATIO` — the
  three-part check that decides Match vs. No Match Found

**Important:** these thresholds were tuned and validated against synthetic
test audio (since real songs weren't available in development). Real music
has much richer, more distinctive spectral content than synthetic test
tones, so once you build the database with your actual 10 songs, do a
quick round of testing and nudge these numbers in `config.py` if you see
too many false accepts (raise the thresholds) or false rejects (lower them).
