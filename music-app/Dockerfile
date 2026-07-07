# Use a lightweight official Python image
FROM python:3.11-slim

# Install system library needed by librosa/soundfile for audio decoding
RUN apt-get update && apt-get install -y --no-install-recommends \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first (better Docker layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code, songs, and prebuilt database
COPY . .

# Render/Railway inject the PORT environment variable automatically
ENV PORT=5000
EXPOSE 5000

# Use gunicorn (production-grade server) instead of Flask's dev server
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:$PORT --timeout 120 app:app"]
