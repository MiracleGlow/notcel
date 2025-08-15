from flask import Flask, render_template, request, redirect, url_for, send_from_directory, abort
import os
import mimetypes
from werkzeug.utils import secure_filename

app = Flask(__name__)

# Konfigurasi
BASE_DIR = "/tmp/notes"
os.makedirs(BASE_DIR, exist_ok=True)
SESSIONS_PER_PAGE = 10

# Set ekstensi file
IMAGE_EXT = {"png", "jpg", "jpeg", "gif", "webp", "svg"}
VIDEO_EXT = {"mp4", "webm", "ogg", "mov"}
AUDIO_EXT = {"mp3", "wav", "ogg", "m4a"}
TEXT_EXT  = {"txt", "md", "log", "py", "json", "csv", "ini"}
# Batas aman untuk memuat file teks ke dalam textarea di browser
MAX_EDITABLE_TEXT_BYTES = 5 * 1024 * 1024  # 5 MB

def safe_session_name(name: str) -> str:
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
    search_query = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)

    all_sessions = get_sessions()
    
    if search_query:
        filtered_sessions = [s for s in all_sessions if search_query.lower() in s.lower()]
    else:
        filtered_sessions = all_sessions

    total_sessions = len(filtered_sessions)
    total_pages = (total_sessions + SESSIONS_PER_PAGE - 1) // SESSIONS_PER_PAGE
    
    if page < 1: page = 1
    if page > total_pages and total_pages > 0: page = total_pages
        
    start_index = (page - 1) * SESSIONS_PER_PAGE
    end_index = start_index + SESSIONS_PER_PAGE
    
    paginated_sessions = filtered_sessions[start_index:end_index]

    return render_template(
        'index.html', 
        sessions=paginated_sessions,
        current_page=page,
        total_pages=total_pages,
        search_query=search_query
    )

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

@app.route('/session/<session_name>')
def edit_session(session_name):
    safe_name = safe_session_name(session_name)
    if not safe_name:
        return "Sesi tidak valid!", 400

    session_dir = os.path.join(BASE_DIR, safe_name)
    if not os.path.exists(session_dir):
        return "Sesi tidak ditemukan!", 404

    files_meta = []
    for fname in sorted(os.listdir(session_dir)):
        fpath = os.path.join(session_dir, fname)
        if not os.path.isfile(fpath):
            continue

        kind = classify_file(fname)
        url = url_for('serve_file', session_name=safe_name, filename=fname)
        mimetype, _ = mimetypes.guess_type(fname)

        item = { "name": fname, "url": url, "kind": kind, "mimetype": mimetype or "", "text": None }

        if kind == "text":
            # Muat seluruh file teks untuk diedit, dengan batas aman
            with open(fpath, "rb") as f:
                chunk = f.read(MAX_EDITABLE_TEXT_BYTES)
            try:
                item["text"] = chunk.decode("utf-8", errors="replace")
            except Exception:
                item["text"] = "(Gagal decode sebagai UTF-8)"
        files_meta.append(item)

    return render_template('session.html', session_name=safe_name, files=files_meta)
    
# --- RUTE BARU UNTUK MENYIMPAN FILE ---
@app.route('/session/<session_name>/save/<path:filename>', methods=['POST'])
def save_text_file(session_name, filename):
    safe_name = safe_session_name(session_name)
    safe_filename = secure_filename(filename)

    if not safe_name or not safe_filename:
        return abort(400) # Bad Request

    session_dir = os.path.join(BASE_DIR, safe_name)
    file_path = os.path.join(session_dir, safe_filename)

    if not os.path.exists(file_path):
        return abort(404) # Not Found

    # Ambil konten baru dari form
    new_content = request.form.get('content', '')

    # Tulis konten baru ke file
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(new_content)
    except Exception as e:
        # Sebaiknya ada logging di sini
        return "Gagal menyimpan file.", 500

    # Redirect kembali ke halaman sesi
    return redirect(url_for('edit_session', session_name=safe_name))


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