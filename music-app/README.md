# Song Identifier - 10 Song Prototype

A minimal SoundHound/Shazam-style music recognition web app.

## Project structure
```
music-app/
├── app.py              # Flask backend (serves frontend + /identify API)
├── fingerprint.py       # Audio fingerprinting logic (FFT, peaks, hashes)
├── match.py             # Matching logic (compares clip vs database)
├── build_database.py    # One-time script to fingerprint your 10 songs
├── requirements.txt     # Python dependencies
├── Dockerfile           # Container definition for deployment
├── songs/               # Put your 10 song files here
└── static/
    └── index.html        # Frontend (record button + result display)
```

## Run locally
```
pip install -r requirements.txt
# Add your 10 songs (mp3/wav/m4a/flac) into the songs/ folder
python build_database.py
python app.py
```
Open http://localhost:5000 in your browser.

## Deploy with Docker
```
docker build -t song-identifier .
docker run -p 5000:5000 song-identifier
```

## Deploy to Render (free tier)
1. Push this project to a GitHub repository (include the songs/ folder
   and the generated fingerprints.db).
2. On Render.com: New -> Web Service -> connect your GitHub repo.
3. Render detects the Dockerfile automatically and builds/deploys it.
4. You'll get a public URL like https://your-app.onrender.com
