# Lightweight official Python base image
FROM python:3.11-slim

# libsndfile1 is required by the soundfile/librosa audio decoding backend
RUN apt-get update && apt-get install -y --no-install-recommends \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install dependencies first for better Docker layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code, songs, and the prebuilt fingerprint database
COPY . .

ENV PORT=5000
EXPOSE 5000

# gunicorn is a production-grade WSGI server (Flask's dev server is not
# meant to handle real traffic or run in the background reliably)
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:$PORT --timeout 180 --workers 2 app:app"]
