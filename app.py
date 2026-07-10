import os
import time
import tempfile
import logging

from flask import Flask, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename

import config
from match import identify_song

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("music-app")

app = Flask(__name__, static_folder="static")
app.config["MAX_CONTENT_LENGTH"] = config.MAX_UPLOAD_MB * 1024 * 1024


def allowed_file(filename):
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return ext in config.ALLOWED_EXTENSIONS


@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/api/health")
def health():
    return jsonify({"status": "ok"})


@app.route("/api/identify", methods=["POST"])
def identify():
    start_time = time.time()

    if "audio" not in request.files:
        return jsonify({"error": "No audio file was received."}), 400

    audio_file = request.files["audio"]

    if audio_file.filename == "":
        return jsonify({"error": "The uploaded file has no name."}), 400
    filename = secure_filename(audio_file.filename) or "clip.webm"
    if "." not in filename:
        filename += ".webm"

    if not allowed_file(filename):
        return jsonify({
            "error": f"Unsupported file type. Allowed types: "
                     f"{', '.join(sorted(config.ALLOWED_EXTENSIONS))}"
        }), 400

    tmp_path = None
    try:
        suffix = "." + filename.rsplit(".", 1)[-1].lower()
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            audio_file.save(tmp.name)
            tmp_path = tmp.name

        if os.path.getsize(tmp_path) == 0:
            return jsonify({"error": "The uploaded audio file is empty."}), 400

        result = identify_song(tmp_path)

    except Exception as exc:
        logger.exception("Error while identifying audio")
        return jsonify({
            "error": "Something went wrong while analyzing the audio. "
                     "Please try recording again."
        }), 500

    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)

    recognition_time_ms = round((time.time() - start_time) * 1000)

    if not result["match"]:
        return jsonify({
            "match": False,
            "match_status": "No confident match found.",
            "confidence_score": round(result.get("confidence_score", 0), 1),
            "recognition_time_ms": recognition_time_ms,
        })

    return jsonify({
        "match": True,
        "match_status": "Match Found",
        "title": result["song"],
        "artist": result["artist"],
        "album": result["album"],
        "genre": result["genre"],
        "duration_seconds": round(result["duration_seconds"], 1),
        "confidence_score": result["confidence_score"],
        "cover_url": result["cover_path"],
        "recognition_time_ms": recognition_time_ms,
    })


@app.errorhandler(413)
def file_too_large(e):
    return jsonify({
        "error": f"File too large. Maximum allowed size is {config.MAX_UPLOAD_MB}MB."
    }), 413


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug_mode = os.environ.get("FLASK_DEBUG", "true").lower() == "true"
    app.run(host="0.0.0.0", port=port, debug=debug_mode)
