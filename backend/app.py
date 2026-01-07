from flask import Flask, request, jsonify, Response, stream_with_context
from flask_cors import CORS
import yt_dlp
import uuid
import requests

app = Flask(__name__)
CORS(app)

@app.route("/")
def home():
    return "VideoVault API running"


# ================= FETCH METADATA =================
@app.route("/fetch", methods=["POST"])
def fetch():
    data = request.get_json()
    url = data.get("url") if data else None

    if not url:
        return jsonify({"error": "No URL"}), 400

    ydl_opts = {
        "quiet": True,
        "skip_download": True,
        "nocheckcertificate": True
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception:
        return jsonify({"error": "Failed to fetch video info"}), 500

    videos = []
    audios = []

    for f in info.get("formats", []):
        if not f.get("url"):
            continue

        # Audio-only formats
        if f.get("vcodec") == "none":
            audios.append({
                "id": str(uuid.uuid4()),
                "type": "audio",
                "ext": "mp3",
                "quality": f.get("abr"),
                "url": f.get("url")
            })

        # Video formats (with audio)
        elif f.get("acodec") != "none":
            videos.append({
                "id": str(uuid.uuid4()),
                "type": "video",
                "ext": f.get("ext"),
                "quality": f.get("format_note") or f.get("resolution"),
                "url": f.get("url")
            })

    return jsonify({
        "title": info.get("title"),
        "thumbnail": info.get("thumbnail"),
        "duration": info.get("duration"),
        "videos": videos,
        "audios": audios
    })


# ================= DOWNLOAD PROXY =================
@app.route("/download", methods=["GET"])
def download():
    file_url = request.args.get("url")
    filename = request.args.get("name", "VideoVault_Download")

    if not file_url:
        return jsonify({"error": "No file URL"}), 400

    try:
        r = requests.get(file_url, stream=True, timeout=15)

        def generate():
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    yield chunk

        headers = {
            "Content-Disposition": f'attachment; filename="{filename}"'
        }

        return Response(
            stream_with_context(generate()),
            headers=headers,
            content_type=r.headers.get("Content-Type", "application/octet-stream")
        )

    except Exception:
        return jsonify({"error": "Download failed"}), 500


if __name__ == "__main__":
    app.run()