from flask import Flask, request, jsonify, send_file, stream_with_context, Response
from flask_cors import CORS
import yt_dlp
import uuid
import os
import tempfile
from moviepy.editor import VideoFileClip, AudioFileClip
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
        # Audio-only
        if f.get("vcodec") == "none":
            audios.append({
                "id": str(uuid.uuid4()),
                "type": "audio",
                "ext": "mp3",
                "quality": f.get("abr"),
                "url": f.get("url")
            })
        # Video with audio
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


# ================= DOWNLOAD/CONVERT PROXY =================
@app.route("/download", methods=["GET"])
def download():
    file_url = request.args.get("url")
    convert_mp3 = request.args.get("mp3", "false") == "true"
    filename = request.args.get("name", "VideoVault_Download")

    if not file_url:
        return jsonify({"error": "No file URL"}), 400

    try:
        # Download the file to temp
        r = requests.get(file_url, stream=True, timeout=20)
        tmp_file = tempfile.NamedTemporaryFile(delete=False)
        for chunk in r.iter_content(chunk_size=8192):
            if chunk:
                tmp_file.write(chunk)
        tmp_file.close()

        if convert_mp3:
            # Convert video/audio to MP3 using moviepy
            output_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
            clip = VideoFileClip(tmp_file.name) if file_url.endswith((".mp4", ".webm")) else AudioFileClip(tmp_file.name)
            clip.audio.write_audiofile(output_file.name, verbose=False, logger=None)
            clip.close()
            os.unlink(tmp_file.name)
            return send_file(output_file.name, as_attachment=True, download_name=f"{filename}.mp3", mimetype="audio/mpeg")
        else:
            # Serve the video/audio as-is
            return send_file(tmp_file.name, as_attachment=True, download_name=filename, mimetype=r.headers.get("Content-Type", "application/octet-stream"))

    except Exception as e:
        print(e)
        return jsonify({"error": "Download or conversion failed"}), 500