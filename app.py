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
app.config['MAX_CONTENT_LENGTH'] = 128 * 1024 * 1024

# Hosting platforms (Render, Hugging Face Spaces, Cloud Run...) set $PORT.
PORT = int(os.environ.get('PORT', '5000'))
HOSTED = bool(os.environ.get('PORT'))   # when hosted: uploads only, no server-filesystem access


def _safe(name):
    keep = '-_.() '
    stem = ''.join(c for c in os.path.splitext(name)[0] if c.isalnum() or c in keep)
    return (stem.strip().replace(' ', '_') or 'GIS_output')


@app.route('/')
def index():
    return render_template('index.html', hosted=HOSTED)


@app.route('/default-input')
def default_input():
    """Return the most recently modified Excel file in the user's Downloads."""
    if HOSTED:                              # never expose the server filesystem
        return jsonify({'path': None, 'name': None})
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

        sources = []                       # list of (path, display_name)
        # uploaded files (multiple) + legacy single 'file'
        uploads = request.files.getlist('files')
        single = request.files.get('file')
        if single and single.filename:
            uploads = list(uploads) + [single]
        for i, up in enumerate(uploads):
            if up and up.filename:
                ext = os.path.splitext(up.filename)[1]
                src = os.path.join(UPLOAD_DIR, f'{token}_{i}_{_safe(up.filename)}{ext}')
                up.save(src)
                sources.append((src, up.filename))
        # paths (newline separated) + legacy single 'path' -- local mode only
        if not HOSTED:
            raw_paths = (request.form.get('paths') or '').splitlines()
            raw_paths.append(request.form.get('path') or '')
            for line in raw_paths:
                p = line.strip().strip('"')
                if p and os.path.isfile(p):
                    sources.append((p, os.path.basename(p)))

        if not sources:
            return jsonify({'ok': False, 'error': 'No spreadsheet provided.'}), 400

        base = _safe(sources[0][1]) if len(sources) == 1 else 'merged_data'
        info = converter.convert(sources, out, base)
        info.update({'ok': True, 'token': token, 'base': base,
                     'input': sources[0][1] if len(sources) == 1 else f'{len(sources)} files'})
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
    if not HOSTED:
        threading.Thread(target=open_browser, daemon=True).start()
        print('GIS Shapefile Generator running at  http://127.0.0.1:5000/')
    app.run(host='0.0.0.0' if HOSTED else '127.0.0.1', port=PORT, debug=False)
