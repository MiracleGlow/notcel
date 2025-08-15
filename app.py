from flask import Flask, render_template, request, redirect, url_for, make_response
import os

app = Flask(__name__)
NOTES_DIR = "/tmp"

# NOTES_DIR = r"C:\tmp"

# Baca semua nama sesi (file .txt)
def get_sessions():
    sessions = []
    for filename in os.listdir(NOTES_DIR):
        if filename.endswith(".txt"):
            sessions.append(filename[:-4])  # hapus .txt
    return sorted(sessions)

# Baca catatan dari file
def read_notes(session_name):
    path = os.path.join(NOTES_DIR, f"{session_name}.txt")
    try:
        with open(path, "r") as file:
            return file.read()
    except FileNotFoundError:
        return ""

# Tulis catatan ke file
def write_notes(session_name, content):
    path = os.path.join(NOTES_DIR, f"{session_name}.txt")
    with open(path, "w") as file:
        file.write(content)

@app.route('/')
def index():
    sessions = get_sessions()
    return render_template('index.html', sessions=sessions)

@app.route('/new', methods=['GET', 'POST'])
def new_session():
    if request.method == 'POST':
        session_name = request.form.get('session_name').strip()
        content = request.form.get('content', '')
        if session_name:
            write_notes(session_name, content)
            return redirect(url_for('index'))
    return render_template('new_session.html')


@app.route('/session/<session_name>', methods=['GET', 'POST'])
def edit_session(session_name):
    if request.method == 'POST':
        content = request.form.get('content')
        write_notes(session_name, content)
        return redirect(url_for('edit_session', session_name=session_name))
    else:
        content = read_notes(session_name)
        return render_template('session.html', session_name=session_name, content=content)

@app.route('/download/<session_name>')
def download(session_name):
    content = read_notes(session_name)
    response = make_response(content)
    response.headers["Content-Disposition"] = f"attachment; filename={session_name}.txt"
    response.headers["Content-Type"] = "text/plain"
    return response

if __name__ == '__main__':
    app.run(debug=True)
