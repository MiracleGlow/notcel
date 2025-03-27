from flask import Flask, render_template, request, redirect, url_for

app = Flask(__name__)

# Path file yang akan digunakan (memanfaatkan direktori writable di Vercel)
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
        # Mengambil data dari form dan menyimpannya ke file txt
        content = request.form.get('content')
        write_notes(content)
        return redirect(url_for('index'))
    else:
        # Membaca konten file untuk ditampilkan
        content = read_notes()
        return render_template('index.html', content=content)

if __name__ == '__main__':
    app.run(debug=True)
