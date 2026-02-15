from flask import Flask, render_template, request, redirect, url_for, abort, send_from_directory, jsonify
import os
import shutil
import mimetypes
import random
import re
from datetime import datetime
import uuid
from werkzeug.utils import secure_filename
from database import (init_db, create_session, get_session, get_public_sessions,
                      get_session_files, save_file, get_file, get_file_by_id, delete_file_record,
                      add_note, get_session_notes, get_note, update_note, delete_note,
                      delete_expired_sessions, get_session_storage_usage)

app = Flask(__name__)
app.secret_key = 'sukamelon'

# --- FILTER JINJA2 ---
HARI_INDO = ['Senin', 'Selasa', 'Rabu', 'Kamis', 'Jumat', 'Sabtu', 'Minggu']
BULAN_INDO = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun', 'Jul', 'Agu', 'Sep', 'Okt', 'Nov', 'Des']

@app.template_filter('format_waktu')
def format_waktu(value):
    """Format datetime string ke format Indonesia: Jumat, 14 Feb 2026 • 16:50"""
    try:
        if isinstance(value, str):
            dt = datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
        else:
            dt = value
        hari = HARI_INDO[dt.weekday()]
        bulan = BULAN_INDO[dt.month]
        return f"{hari}, {dt.day} {bulan} {dt.year} • {dt.strftime('%H:%M')}"
    except Exception:
        return value

# --- KONFIGURASI ---
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')
os.makedirs(UPLOAD_DIR, exist_ok=True)

MAX_SESSION_STORAGE = 140 * 1024 * 1024  # 128MB total per sesi
app.config['MAX_CONTENT_LENGTH'] = MAX_SESSION_STORAGE  # Flask built-in protection

SESSION_LIFETIME_HOURS = 3  # Sesi dihapus otomatis setelah X jam (ubah angka ini sesuai kebutuhan)

init_db(app)

SESSIONS_PER_PAGE = 10
IMAGE_EXT = {"png", "jpg", "jpeg", "gif", "webp", "svg"}
VIDEO_EXT = {"mp4", "webm", "ogg", "mov"}
AUDIO_EXT = {"mp3", "wav", "ogg", "m4a"}

@app.before_request
def cleanup_expired_sessions():
    """Auto-delete sessions older than SESSION_LIFETIME_HOURS on every request."""
    try:
        expired_ids = delete_expired_sessions(SESSION_LIFETIME_HOURS)
        # Delete upload folders from disk
        for sid in expired_ids:
            folder = os.path.join(UPLOAD_DIR, str(sid))
            if os.path.isdir(folder):
                shutil.rmtree(folder, ignore_errors=True)
    except Exception:
        pass  # Jangan sampai cleanup error mengganggu request user


def safe_session_name(name: str) -> str:
    cleaned = secure_filename(name).strip("._")
    return cleaned if cleaned else "untitled_session"

def classify_file(filename: str):
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext in IMAGE_EXT: return "image"
    if ext in VIDEO_EXT: return "video"
    if ext in AUDIO_EXT: return "audio"
    return "other"

def make_unique_filename(original_filename: str) -> str:
    """Generate a unique filename with UUID suffix."""
    safe_name = secure_filename(original_filename)
    ext = ""
    if "." in original_filename:
        ext = "." + original_filename.rsplit(".", 1)[-1].lower()
    if not safe_name or safe_name == ext.lstrip("."):
        safe_name = "file" + ext
    if "." in safe_name:
        base, dot_ext = safe_name.rsplit(".", 1)
        return f"{base}_{uuid.uuid4().hex[:8]}.{dot_ext}"
    else:
        return f"{safe_name}_{uuid.uuid4().hex[:8]}"

def save_uploaded_file(session_id, uploaded_file):
    """Save an uploaded file to static/uploads/<session_id>/ and record in DB. Returns filesize."""
    original_name = uploaded_file.filename
    unique_filename = make_unique_filename(original_name)
    
    session_upload_dir = os.path.join(UPLOAD_DIR, str(session_id))
    os.makedirs(session_upload_dir, exist_ok=True)
    
    disk_path = os.path.join(session_upload_dir, unique_filename)
    uploaded_file.save(disk_path)
    
    # Get actual file size from disk
    filesize = os.path.getsize(disk_path)
    
    relative_path = f"{session_id}/{unique_filename}"
    file_mimetype = mimetypes.guess_type(unique_filename)[0] or ""
    file_kind = classify_file(unique_filename)
    
    save_file(session_id, unique_filename,
             filepath=relative_path,
             mimetype=file_mimetype,
             kind=file_kind,
             filesize=filesize)
    return filesize


def get_storage_info(session_id):
    """Get storage usage info for a session."""
    used = get_session_storage_usage(session_id)
    limit = MAX_SESSION_STORAGE
    percentage = round((used / limit) * 100, 1) if limit > 0 else 0
    return {
        'used': used,
        'limit': limit,
        'used_mb': round(used / (1024 * 1024), 2),
        'limit_mb': round(limit / (1024 * 1024), 0),
        'percentage': min(percentage, 100),
    }


# --- ROUTES ---

@app.route('/')
def index():
    search_query = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)

    all_sessions = get_public_sessions(search_query if search_query else None)

    total_sessions = len(all_sessions)
    total_pages = (total_sessions + SESSIONS_PER_PAGE - 1) // SESSIONS_PER_PAGE

    if page < 1: page = 1
    if page > total_pages and total_pages > 0: page = total_pages

    start_index = (page - 1) * SESSIONS_PER_PAGE
    end_index = start_index + SESSIONS_PER_PAGE
    paginated_sessions = all_sessions[start_index:end_index]

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
    session = get_session(safe_name, 'private')

    if session and session['private_code'] == code_part:
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

        private_code = None
        if session_type == 'private':
            private_code = str(random.randint(1000, 9999))

        session = create_session(session_name, session_type, private_code)
        if session is None:
            return "Nama sesi sudah digunakan. Harap pilih nama lain.", 409

        if session_type == 'private':
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
    session = get_session(safe_name, session_type)
    if not session: return abort(404)

    notes = get_session_notes(session['id'])
    db_files = get_session_files(session['id'])
    storage_info = get_storage_info(session['id'])

    # Build unified items list
    items = []
    for n in notes:
        items.append({
            "type": "note",
            "id": n['id'],
            "content": n['content'],
            "created_at": n['created_at'],
        })
    for f in db_files:
        items.append({
            "type": "file",
            "id": f['id'],
            "name": f['filename'],
            "url": url_for('serve_file', session_type=session_type, session_name=safe_name, filename=f['filename']),
            "kind": f['kind'] or classify_file(f['filename']),
            "mimetype": f['mimetype'] or "",
            "created_at": f['created_at'],
        })

    # Sort by creation time (oldest first)
    items.sort(key=lambda x: x['created_at'])

    return render_template('session.html',
                           session_type=session_type,
                           session_name=safe_name,
                           items=items,
                           storage_info=storage_info)

# --- Note CRUD ---

@app.route('/session/<session_type>/<session_name>/note/add', methods=['POST'])
def add_note_route(session_type, session_name):
    safe_name = safe_session_name(session_name)
    session = get_session(safe_name, session_type)
    if not session: return abort(404)

    content = request.form.get('content', '').strip()
    if content:
        add_note(session['id'], content)

    return redirect(url_for('edit_session', session_type=session_type, session_name=safe_name))

@app.route('/session/<session_type>/<session_name>/note/<int:note_id>/edit', methods=['POST'])
def edit_note_route(session_type, session_name, note_id):
    safe_name = safe_session_name(session_name)
    session = get_session(safe_name, session_type)
    if not session: return abort(404)

    note = get_note(note_id)
    if not note or note['session_id'] != session['id']: return abort(404)

    content = request.form.get('content', '').strip()
    if content:
        update_note(note_id, content)

    return redirect(url_for('edit_session', session_type=session_type, session_name=safe_name))

@app.route('/session/<session_type>/<session_name>/note/<int:note_id>/delete', methods=['POST'])
def delete_note_route(session_type, session_name, note_id):
    safe_name = safe_session_name(session_name)
    session = get_session(safe_name, session_type)
    if not session: return abort(404)

    note = get_note(note_id)
    if not note or note['session_id'] != session['id']: return abort(404)

    delete_note(note_id)
    return redirect(url_for('edit_session', session_type=session_type, session_name=safe_name))

# --- File Upload & Delete ---

@app.route('/session/<session_type>/<session_name>/upload', methods=['POST'])
def upload_to_session(session_type, session_name):
    safe_name = safe_session_name(session_name)
    session = get_session(safe_name, session_type)
    if not session:
        return jsonify({'error': 'Sesi tidak ditemukan!'}), 404

    uploaded_file = request.files.get('file')
    if not uploaded_file or not uploaded_file.filename:
        return jsonify({'error': 'Tidak ada file yang dipilih.'}), 400

    # Check file size via Content-Length header (quick pre-check)
    content_length = request.content_length
    if content_length and content_length > MAX_SESSION_STORAGE:
        return jsonify({'error': f'File terlalu besar! Maksimal {MAX_SESSION_STORAGE // (1024*1024)}MB per sesi.'}), 413

    # Check remaining session storage
    current_usage = get_session_storage_usage(session['id'])
    remaining = MAX_SESSION_STORAGE - current_usage

    # Save file to temp first to check actual size
    uploaded_file.seek(0, 2)  # Seek to end
    file_size = uploaded_file.tell()  # Get position = file size
    uploaded_file.seek(0)  # Seek back to start

    if file_size > remaining:
        used_mb = round(current_usage / (1024 * 1024), 1)
        limit_mb = MAX_SESSION_STORAGE // (1024 * 1024)
        return jsonify({
            'error': f'Penyimpanan sesi penuh! Terpakai {used_mb}MB dari {limit_mb}MB. '
                     f'Sisa ruang: {round(remaining / (1024*1024), 1)}MB.'
        }), 413

    save_uploaded_file(session['id'], uploaded_file)
    storage_info = get_storage_info(session['id'])

    # Support both AJAX and regular form submission
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'success': True, 'storage': storage_info})

    return redirect(url_for('edit_session', session_type=session_type, session_name=safe_name))


@app.route('/session/<session_type>/<session_name>/storage')
def session_storage(session_type, session_name):
    """API endpoint to get session storage info."""
    safe_name = safe_session_name(session_name)
    session = get_session(safe_name, session_type)
    if not session:
        return jsonify({'error': 'Sesi tidak ditemukan!'}), 404
    return jsonify(get_storage_info(session['id']))


@app.errorhandler(413)
def request_entity_too_large(error):
    """Handle file too large error from Flask's MAX_CONTENT_LENGTH."""
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'error': f'File terlalu besar! Maksimal {MAX_SESSION_STORAGE // (1024*1024)}MB.'}), 413
    return f'File terlalu besar! Maksimal {MAX_SESSION_STORAGE // (1024*1024)}MB.', 413

@app.route('/session/<session_type>/<session_name>/file/<int:file_id>/delete', methods=['POST'])
def delete_file_route(session_type, session_name, file_id):
    safe_name = safe_session_name(session_name)
    session = get_session(safe_name, session_type)
    if not session: return abort(404)

    file_record = get_file_by_id(file_id)
    if not file_record or file_record['session_id'] != session['id']: return abort(404)

    # Delete file from disk
    if file_record['filepath']:
        disk_path = os.path.join(UPLOAD_DIR, file_record['filepath'])
        if os.path.exists(disk_path):
            os.remove(disk_path)

    delete_file_record(file_id)
    return redirect(url_for('edit_session', session_type=session_type, session_name=safe_name))

@app.route('/files/<session_type>/<session_name>/<path:filename>')
def serve_file(session_type, session_name, filename):
    safe_name = safe_session_name(session_name)
    session = get_session(safe_name, session_type)
    if not session: return abort(404)

    file_record = get_file(session['id'], filename)
    if not file_record: return abort(404)

    if file_record['filepath']:
        session_upload_dir = os.path.join(UPLOAD_DIR, str(session['id']))
        return send_from_directory(session_upload_dir, filename)

    return abort(404)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)