from flask import Flask, render_template, request, redirect, url_for, send_from_directory, abort
import os
import mimetypes
import random
import re
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'super-secret-key-change-this' 

# --- KONFIGURASI ---
PUBLIC_DIR = "/tmp/notes_public"
PRIVATE_DIR = "/tmp/notes_private"
os.makedirs(PUBLIC_DIR, exist_ok=True)
os.makedirs(PRIVATE_DIR, exist_ok=True)

SESSIONS_PER_PAGE = 10
IMAGE_EXT = {"png", "jpg", "jpeg", "gif", "webp", "svg"}
VIDEO_EXT = {"mp4", "webm", "ogg", "mov"}
AUDIO_EXT = {"mp3", "wav", "ogg", "m4a"}
TEXT_EXT = {"txt", "md", "log", "py", "json", "csv", "ini", "html", "css", "js"}
MAX_EDITABLE_TEXT_BYTES = 5 * 1024 * 1024

def safe_session_name(name: str) -> str:
    # Mengamankan nama folder
    cleaned = secure_filename(name).strip("._")
    # Jika kosong setelah dibersihkan, beri default
    return cleaned if cleaned else "untitled_session"

def normalize_string(text: str) -> str:
    # Menghapus semua karakter non-alfanumerik untuk pencarian yang lebih fleksibel
    # Contoh: "Catatan_Harian" jadi "catatanharian", "My Note!" jadi "mynote"
    return re.sub(r'[\W_]+', '', text).lower()

def get_public_sessions():
    try:
        return sorted([d for d in os.listdir(PUBLIC_DIR) if os.path.isdir(os.path.join(PUBLIC_DIR, d))])
    except OSError:
        return []

def classify_file(filename: str):
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext in IMAGE_EXT: return "image"
    if ext in VIDEO_EXT: return "video"
    if ext in AUDIO_EXT: return "audio"
    if ext in TEXT_EXT:  return "text"
    return "other"

def get_session_dir(session_type: str, session_name: str) -> str:
    base = PRIVATE_DIR if session_type == 'private' else PUBLIC_DIR
    return os.path.join(base, session_name)

# --- ROUTES ---

@app.route('/')
def index():
    search_query = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)

    all_sessions = get_public_sessions()
    
    # --- LOGIKA SEARCH DIPERBAIKI ---
    if search_query:
        # Normalisasi query user (hapus spasi/simbol)
        clean_query = normalize_string(search_query)
        
        filtered_sessions = []
        for s in all_sessions:
            # Normalisasi nama folder (hapus underscore/dash)
            clean_session_name = normalize_string(s)
            
            # Bandingkan versi yang sudah bersih
            if clean_query in clean_session_name:
                filtered_sessions.append(s)
    else:
        filtered_sessions = all_sessions

    # Pagination Logic
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

@app.route('/access-private', methods=['POST'])
def access_private():
    code = request.form.get('private_code', '').strip()
    if not code or len(code) <= 4:
        return "Kode privat tidak valid (terlalu pendek).", 400

    session_name_part = code[:-4]
    code_part = code[-4:]
    
    safe_name = safe_session_name(session_name_part)
    session_dir = get_session_dir('private', safe_name)
    code_file = os.path.join(session_dir, '.pcode')

    if os.path.exists(code_file):
        with open(code_file, 'r') as f:
            stored_code = f.read().strip()
        if stored_code == code_part:
            return redirect(url_for('edit_session', session_type='private', session_name=safe_name))

    return "Kode privat salah atau sesi tidak ditemukan.", 404

@app.route('/new/<session_type>', methods=['GET', 'POST'])
def new_session(session_type):
    if session_type not in ['public', 'private']:
        return abort(404)

    if request.method == 'POST':
        raw_session = request.form.get('session_name', '')
        session_name = safe_session_name(raw_session)
        
        if not session_name: 
            return "Nama sesi tidak valid (gunakan huruf dan angka).", 400

        session_dir = get_session_dir(session_type, session_name)
        if os.path.exists(session_dir):
            return "Nama sesi sudah digunakan. Harap pilih nama lain.", 409

        os.makedirs(session_dir, exist_ok=True)
        
        mode = request.form.get('mode', 'manual')
        if mode == 'manual':
            content = (request.form.get('content') or "")
            # Simpan default text jika ada
            if content:
                with open(os.path.join(session_dir, "notes.txt"), "w", encoding="utf-8") as f:
                    f.write(content)
        elif mode == 'upload':
            file = request.files.get('file')
            if file and file.filename:
                filename = secure_filename(file.filename)
                file.save(os.path.join(session_dir, filename))

        if session_type == 'private':
            private_code = str(random.randint(1000, 9999))
            with open(os.path.join(session_dir, '.pcode'), 'w') as f:
                f.write(private_code)
            full_code = f"{session_name}{private_code}"
            return redirect(url_for('new_session_success', session_name=session_name, code=full_code))

        return redirect(url_for('edit_session', session_type='public', session_name=session_name))

    return render_template('new_session.html', session_type=session_type)

@app.route('/success')
def new_session_success():
    session_name = request.args.get('session_name')
    code = request.args.get('code')
    return render_template('new_session_success.html', session_name=session_name, code=code)

@app.route('/session/<session_type>/<session_name>')
def edit_session(session_type, session_name):
    if session_type not in ['public', 'private']: return abort(404)
    
    safe_name = safe_session_name(session_name)
    session_dir = get_session_dir(session_type, safe_name)
    
    if not os.path.exists(session_dir): 
        # Jika user memaksa URL tapi folder tidak ada
        return abort(404)

    files_meta = []
    # List directory dengan error handling sederhana
    try:
        dir_content = sorted(os.listdir(session_dir))
    except OSError:
        return abort(404)

    for fname in dir_content:
        if fname.startswith('.'): continue # Skip hidden files like .pcode
        
        fpath = os.path.join(session_dir, fname)
        if not os.path.isfile(fpath): continue

        item = {
            "name": fname,
            "url": url_for('serve_file', session_type=session_type, session_name=safe_name, filename=fname),
            "kind": classify_file(fname),
            "mimetype": mimetypes.guess_type(fname)[0] or "",
            "text": None
        }

        if item["kind"] == "text":
            try:
                # Batasi baca file teks agar tidak berat
                if os.path.getsize(fpath) < MAX_EDITABLE_TEXT_BYTES:
                    with open(fpath, "rb") as f:
                        item["text"] = f.read().decode("utf-8", "replace")
                else:
                    item["text"] = "File terlalu besar untuk dipratinjau/edit."
            except Exception:
                item["text"] = "Error membaca file."
                
        files_meta.append(item)

    return render_template('session.html', session_type=session_type, session_name=safe_name, files=files_meta)

@app.route('/session/<session_type>/<session_name>/save/<path:filename>', methods=['POST'])
def save_text_file(session_type, session_name, filename):
    safe_name = safe_session_name(session_name)
    safe_filename = secure_filename(filename)
    session_dir = get_session_dir(session_type, safe_name)
    file_path = os.path.join(session_dir, safe_filename)

    if not os.path.exists(file_path): return abort(404)
    
    new_content = request.form.get('content', '')
    # Tulis dengan newline normal
    with open(file_path, "w", encoding="utf-8", newline='') as f:
        f.write(new_content)

    return redirect(url_for('edit_session', session_type=session_type, session_name=safe_name))

@app.route('/session/<session_type>/<session_name>/upload', methods=['POST'])
def upload_to_session(session_type, session_name):
    safe_name = safe_session_name(session_name)
    session_dir = get_session_dir(session_type, safe_name)
    if not os.path.exists(session_dir): return "Sesi tidak ditemukan!", 404

    uploaded_file = request.files.get('file')
    if uploaded_file and uploaded_file.filename:
        filename = secure_filename(uploaded_file.filename)
        uploaded_file.save(os.path.join(session_dir, filename))

    return redirect(url_for('edit_session', session_type=session_type, session_name=safe_name))

@app.route('/files/<session_type>/<session_name>/<path:filename>')
def serve_file(session_type, session_name, filename):
    safe_name = safe_session_name(session_name)
    session_dir = get_session_dir(session_type, safe_name)
    return send_from_directory(session_dir, filename)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)