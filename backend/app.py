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
    url = request.json.get("url")
    if not url:
        return jsonify({"error": "No URL"}), 400

    ydl_opts = {
        "quiet": True,
        "skip_download": True,
        "nocheckcertificate": True
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

    videos = []
    audios = []

    for f in info.get("formats", []):
        if not f.get("url"):
            continue

        # Audio only
        if f.get("vcodec") == "none":
            audios.append({
                "id": str(uuid.uuid4()),
                "type": "audio",
                "ext": "mp3",
                "quality": f.get("abr"),
                "url": f.get("url")
            })
        # Video
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
    filename = request.args.get("name", "videovault")

    if not file_url:
        return jsonify({"error": "No file URL"}), 400

    r = requests.get(file_url, stream=True)

    def generate():
        for chunk in r.iter_content(chunk_size=1024 * 1024):
            if chunk:
                yield chunk

    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "Content-Type": "application/octet-stream"
    }

    return Response(
        stream_with_context(generate()),
        headers=headers
    )

if __name__ == "__main__":
    app.run()