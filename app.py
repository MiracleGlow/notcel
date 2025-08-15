from flask import Flask, render_template, request, redirect, url_for, make_response, send_from_directory
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
BASE_DIR = "/tmp/notes"

# Pastikan direktori base ada
os.makedirs(BASE_DIR, exist_ok=True)

def get_sessions():
    return sorted([d for d in os.listdir(BASE_DIR) if os.path.isdir(os.path.join(BASE_DIR, d))])

@app.route('/')
def index():
    return render_template('index.html', sessions=get_sessions())

@app.route('/new', methods=['GET', 'POST'])
def new_session():
    if request.method == 'POST':
        session_name = request.form.get('session_name', '').strip()
        mode = request.form.get('mode', 'manual')

        if not session_name:
            return "Nama sesi wajib diisi!", 400

        session_dir = os.path.join(BASE_DIR, session_name)
        os.makedirs(session_dir, exist_ok=True)

        if mode == 'manual':
            content = request.form.get('content', '').strip()
            with open(os.path.join(session_dir, "notes.txt"), "w", encoding="utf-8") as f:
                f.write(content)
        elif mode == 'upload':
            uploaded_file = request.files.get('file')
            if uploaded_file and uploaded_file.filename:
                filename = secure_filename(uploaded_file.filename)
                uploaded_file.save(os.path.join(session_dir, filename))

        return redirect(url_for('edit_session', session_name=session_name))

    return render_template('new_session.html')

@app.route('/session/<session_name>', methods=['GET', 'POST'])
def edit_session(session_name):
    session_dir = os.path.join(BASE_DIR, session_name)
    if not os.path.exists(session_dir):
        return "Sesi tidak ditemukan!", 404

    files = os.listdir(session_dir)
    return render_template('session.html', session_name=session_name, files=files)

@app.route('/session/<session_name>/upload', methods=['POST'])
def upload_to_session(session_name):
    session_dir = os.path.join(BASE_DIR, session_name)
    if not os.path.exists(session_dir):
        return "Sesi tidak ditemukan!", 404

    uploaded_file = request.files.get('file')
    if uploaded_file and uploaded_file.filename:
        filename = secure_filename(uploaded_file.filename)
        uploaded_file.save(os.path.join(session_dir, filename))

    return redirect(url_for('edit_session', session_name=session_name))

@app.route('/files/<session_name>/<filename>')
def serve_file(session_name, filename):
    session_dir = os.path.join(BASE_DIR, session_name)
    return send_from_directory(session_dir, filename)

if __name__ == '__main__':
    app.run(debug=True)
