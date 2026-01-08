from flask import Flask, request, jsonify, Response, stream_with_context
from flask_cors import CORS
import yt_dlp
import uuid
import requests
import subprocess

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

    videos, audios = [], []

    for f in info.get("formats", []):
        if not f.get("url"):
            continue

        # audio-only
        if f.get("vcodec") == "none":
            audios.append({
                "id": str(uuid.uuid4()),
                "ext": "mp3",
                "quality": f.get("abr"),
                "url": f.get("url")
            })

        # video + audio
        elif f.get("acodec") != "none":
            videos.append({
                "id": str(uuid.uuid4()),
                "ext": f.get("ext"),
                "quality": f.get("format_note") or f.get("resolution"),
                "url": f.get("url")
            })

    return jsonify({
        "title": info.get("title"),
        "thumbnail": info.get("thumbnail"),
        "videos": videos,
        "audios": audios
    })


# ================= DOWNLOAD / CONVERT =================
@app.route("/download", methods=["GET"])
def download():
    file_url = request.args.get("url")
    mp3 = request.args.get("mp3", "false").lower() == "true"
    name = request.args.get("name", "VideoVault")

    if not file_url:
        return jsonify({"error": "No URL"}), 400

    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        if mp3:
            r = requests.get(file_url, headers=headers, stream=True, timeout=30)

            cmd = [
                "ffmpeg", "-i", "pipe:0",
                "-vn", "-ab", "192k",
                "-f", "mp3", "pipe:1"
            ]

            process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL
            )

            def generate():
                for chunk in r.iter_content(1024 * 32):
                    if chunk:
                        process.stdin.write(chunk)
                process.stdin.close()

                while True:
                    out = process.stdout.read(8192)
                    if not out:
                        break
                    yield out

            return Response(
                stream_with_context(generate()),
                headers={
                    "Content-Disposition": f'attachment; filename="{name}.mp3"'
                },
                content_type="audio/mpeg"
            )

        else:
            r = requests.get(file_url, headers=headers, stream=True, timeout=30)

            def generate():
                for chunk in r.iter_content(8192):
                    if chunk:
                        yield chunk

            return Response(
                stream_with_context(generate()),
                headers={
                    "Content-Disposition": f'attachment; filename="{name}.mp4"'
                },
                content_type="application/octet-stream"
            )

    except Exception as e:
        return jsonify({"error": "Download failed", "details": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)