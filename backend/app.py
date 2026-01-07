from flask import Flask, request, jsonify
from flask_cors import CORS
import yt_dlp
import uuid

app = Flask(__name__)
CORS(app)

@app.route("/")
def home():
    return "VideoVault API running"

@app.route("/fetch", methods=["POST"])
def fetch():
    url = request.json.get("url")
    if not url:
        return jsonify({"error": "No URL"}), 400

    ydl_opts = {
        "quiet": True,
        "skip_download": True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

    video_formats = []
    audio_formats = []

    for f in info.get("formats", []):
        if not f.get("url"):
            continue

        if f.get("vcodec") == "none":
            audio_formats.append({
                "ext": "mp3",
                "quality": f.get("abr"),
                "url": f.get("url")
            })
        else:
            video_formats.append({
                "ext": f.get("ext"),
                "quality": f.get("format_note") or f.get("resolution"),
                "url": f.get("url")
            })

    return jsonify({
        "title": info.get("title"),
        "thumbnail": info.get("thumbnail"),
        "duration": info.get("duration"),
        "videos": video_formats,
        "audios": audio_formats
    })
