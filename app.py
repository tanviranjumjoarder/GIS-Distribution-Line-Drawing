"""Local web app: GIS Base sheet (Excel)  ->  points + lines shapefiles
matching the exact schemas of the Kushtia PBS June-2026 layers."""
import os, io, time, zipfile, threading, webbrowser, traceback
from flask import Flask, request, jsonify, send_file, render_template
import converter

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, 'uploads')
OUT_DIR = os.path.join(BASE_DIR, 'outputs')
DOWNLOADS = os.path.join(os.path.expanduser('~'), 'Downloads')
SIDE = ('.shp', '.shx', '.dbf', '.prj', '.cpg', '.shp.xml')
for d in (UPLOAD_DIR, OUT_DIR):
    os.makedirs(d, exist_ok=True)

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 64 * 1024 * 1024


def _safe(name):
    keep = '-_.() '
    stem = ''.join(c for c in os.path.splitext(name)[0] if c.isalnum() or c in keep)
    return (stem.strip().replace(' ', '_') or 'GIS_output')


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/default-input')
def default_input():
    """Return the most recently modified Excel file in the user's Downloads."""
    best = None
    try:
        cands = [os.path.join(DOWNLOADS, f) for f in os.listdir(DOWNLOADS)
                 if f.lower().endswith(('.xls', '.xlsx', '.xlsm')) and not f.startswith('~$')]
        if cands:
            best = max(cands, key=os.path.getmtime)
    except Exception:
        pass
    return jsonify({'path': best, 'name': os.path.basename(best) if best else None})


@app.route('/convert', methods=['POST'])
def convert_route():
    try:
        token = time.strftime('%Y%m%d_%H%M%S')
        out = os.path.join(OUT_DIR, token)
        os.makedirs(out, exist_ok=True)

        up = request.files.get('file')
        path = (request.form.get('path') or '').strip().strip('"')
        if up and up.filename:
            src = os.path.join(UPLOAD_DIR, f'{token}_{_safe(up.filename)}{os.path.splitext(up.filename)[1]}')
            up.save(src); display = up.filename
        elif path and os.path.isfile(path):
            src = path; display = os.path.basename(path)
        else:
            return jsonify({'ok': False, 'error': 'No Excel file uploaded and no valid file path given.'}), 400

        base = _safe(display)
        info = converter.convert(src, out, base)
        info.update({'ok': True, 'token': token, 'base': base, 'input': display})
        return jsonify(info)
    except Exception as e:
        traceback.print_exc()
        return jsonify({'ok': False, 'error': f'{type(e).__name__}: {e}'}), 500


def _zip(token, base, which):
    folder = os.path.join(OUT_DIR, token)
    mem = io.BytesIO()
    with zipfile.ZipFile(mem, 'w', zipfile.ZIP_DEFLATED) as z:
        layers = ['_points', '_lines'] if which == 'both' else [f'_{which}']
        for lay in layers:
            for ext in SIDE:
                fp = os.path.join(folder, base + lay + ext)
                if os.path.exists(fp):
                    z.write(fp, arcname=os.path.basename(fp))
    mem.seek(0)
    return mem


@app.route('/download/<token>/<which>')
def download(token, which):
    base = _safe(request.args.get('base', 'GIS_output'))
    if which not in ('points', 'lines', 'both'):
        return 'bad request', 400
    mem = _zip(token, base, which)
    name = f'{base}_{which}.zip' if which != 'both' else f'{base}_shapefiles.zip'
    return send_file(mem, mimetype='application/zip', as_attachment=True, download_name=name)


def open_browser():
    time.sleep(1.0)
    webbrowser.open('http://127.0.0.1:5000/')


if __name__ == '__main__':
    threading.Thread(target=open_browser, daemon=True).start()
    print('GIS Shapefile Generator running at  http://127.0.0.1:5000/')
    app.run(host='127.0.0.1', port=5000, debug=False)
