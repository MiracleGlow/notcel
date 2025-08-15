from flask import Flask, render_template, request, redirect, url_for, send_from_directory, abort
import os
import mimetypes
from werkzeug.utils import secure_filename

app = Flask(__name__)

BASE_DIR = "/tmp/notes"
os.makedirs(BASE_DIR, exist_ok=True)

IMAGE_EXT = {"png", "jpg", "jpeg", "gif", "webp", "svg"}
VIDEO_EXT = {"mp4", "webm", "ogg", "mov"}
AUDIO_EXT = {"mp3", "wav", "ogg", "m4a"}
TEXT_EXT  = {"txt", "md", "log", "py", "json", "csv", "ini"}

MAX_TEXT_PREVIEW_BYTES = 128 * 1024  # 128 KB agar aman di template

def safe_session_name(name: str) -> str:
    """
    Amankan nama sesi agar jadi nama folder yang valid & tidak kosong.
    secure_filename mengubah spasi jadi underscore, hapus karakter berbahaya.
    """
    cleaned = secure_filename(name).strip("._")
    return cleaned

def get_sessions():
    return sorted([d for d in os.listdir(BASE_DIR) if os.path.isdir(os.path.join(BASE_DIR, d))])

def classify_file(filename: str):
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext in IMAGE_EXT: return "image"
    if ext in VIDEO_EXT: return "video"
    if ext in AUDIO_EXT: return "audio"
    if ext in TEXT_EXT:  return "text"
    return "other"

@app.route('/')
def index():
    return render_template('index.html', sessions=get_sessions())

@app.route('/new', methods=['GET', 'POST'])
def new_session():
    if request.method == 'POST':
        mode = request.form.get('mode', 'manual')
        raw_session = request.form.get('session_name', '')
        session_name = safe_session_name(raw_session)

        if not session_name:
            return "Nama sesi tidak valid!", 400

        session_dir = os.path.join(BASE_DIR, session_name)
        os.makedirs(session_dir, exist_ok=True)

        if mode == 'manual':
            content = (request.form.get('content') or "")
            # Simpan ke notes.txt (UTF-8)
            with open(os.path.join(session_dir, "notes.txt"), "w", encoding="utf-8") as f:
                f.write(content)

        elif mode == 'upload':
            uploaded_file = request.files.get('file')
            if uploaded_file and uploaded_file.filename:
                filename = secure_filename(uploaded_file.filename)
                if not filename:
                    return "Nama file upload tidak valid!", 400
                uploaded_file.save(os.path.join(session_dir, filename))

        return redirect(url_for('edit_session', session_name=session_name))

    return render_template('new_session.html')

@app.route('/session/<session_name>', methods=['GET', 'POST'])
def edit_session(session_name):
    safe_name = safe_session_name(session_name)
    if not safe_name:
        return "Sesi tidak valid!", 400

    session_dir = os.path.join(BASE_DIR, safe_name)
    if not os.path.exists(session_dir):
        return "Sesi tidak ditemukan!", 404

    # Daftar & siapkan metadata file untuk template
    files_meta = []
    for fname in sorted(os.listdir(session_dir)):
        fpath = os.path.join(session_dir, fname)
        if not os.path.isfile(fpath):
            continue

        kind = classify_file(fname)
        url = url_for('serve_file', session_name=safe_name, filename=fname)
        mimetype, _ = mimetypes.guess_type(fname)

        item = {
            "name": fname,
            "url": url,
            "kind": kind,
            "mimetype": mimetype or "",
            "text": None
        }

        if kind == "text":
            # Baca sebagian saja untuk preview agar aman
            with open(fpath, "rb") as f:
                chunk = f.read(MAX_TEXT_PREVIEW_BYTES)
            try:
                item["text"] = chunk.decode("utf-8", errors="replace")
            except Exception:
                item["text"] = "(Gagal decode sebagai UTF-8)"
        files_meta.append(item)

    return render_template('session.html', session_name=safe_name, files=files_meta)

@app.route('/session/<session_name>/upload', methods=['POST'])
def upload_to_session(session_name):
    safe_name = safe_session_name(session_name)
    if not safe_name:
        return "Sesi tidak valid!", 400

    session_dir = os.path.join(BASE_DIR, safe_name)
    if not os.path.exists(session_dir):
        return "Sesi tidak ditemukan!", 404

    uploaded_file = request.files.get('file')
    if uploaded_file and uploaded_file.filename:
        filename = secure_filename(uploaded_file.filename)
        if not filename:
            return "Nama file upload tidak valid!", 400
        uploaded_file.save(os.path.join(session_dir, filename))

    return redirect(url_for('edit_session', session_name=safe_name))

@app.route('/files/<session_name>/<path:filename>')
def serve_file(session_name, filename):
    safe_name = safe_session_name(session_name)
    if not safe_name:
        return abort(404)

    session_dir = os.path.join(BASE_DIR, safe_name)
    if not os.path.exists(session_dir):
        return abort(404)

    return send_from_directory(session_dir, filename)
    
if __name__ == '__main__':
    app.run(debug=True)
