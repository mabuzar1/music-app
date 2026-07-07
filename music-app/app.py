"""
app.py
------
Flask backend for the music recognition prototype.

Endpoints:
    GET  /            -> serves the frontend page
    POST /identify     -> accepts an audio file, returns the matched song as JSON
"""

import os
import tempfile
from flask import Flask, request, jsonify, send_from_directory
from match import identify_song

app = Flask(__name__, static_folder="static")


@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/identify", methods=["POST"])
def identify():
    if "audio" not in request.files:
        return jsonify({"error": "No audio file received"}), 400

    audio_file = request.files["audio"]

    # Save the uploaded clip to a temporary file so librosa can read it
    with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as tmp:
        audio_file.save(tmp.name)
        tmp_path = tmp.name

    try:
        result = identify_song(tmp_path)
    finally:
        os.remove(tmp_path)  # clean up temp file regardless of outcome

    if result is None:
        return jsonify({"match": False, "message": "No confident match found"})

    return jsonify({
        "match": True,
        "song": result["song"],
        "confidence_score": result["confidence_score"],
    })


if __name__ == "__main__":
    # host="0.0.0.0" makes it reachable from other devices on the network
    # (useful for testing on your phone). debug=True is for development only.
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
