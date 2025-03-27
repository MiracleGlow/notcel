from flask import Flask, render_template, request, redirect, url_for, make_response

app = Flask(__name__)

# Menggunakan direktori writable di Vercel
FILE_PATH = "/tmp/notes.txt"

def read_notes():
    try:
        with open(FILE_PATH, "r") as file:
            return file.read()
    except FileNotFoundError:
        return ""

def write_notes(content):
    with open(FILE_PATH, "w") as file:
        file.write(content)

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        content = request.form.get('content')
        write_notes(content)
        return redirect(url_for('index'))
    else:
        content = read_notes()
        return render_template('index.html', content=content)

@app.route('/download')
def download():
    content = read_notes()
    response = make_response(content)
    response.headers["Content-Disposition"] = "attachment; filename=notes.txt"
    response.headers["Content-Type"] = "text/plain"
    return response

if __name__ == '__main__':
    app.run(debug=True)
