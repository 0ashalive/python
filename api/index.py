import re
import json
from flask import Flask, request, render_template_string, jsonify

app = Flask(__name__)

GLOBAL_PLAYLIST_CACHE = {"hero": [], "categories": []}

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>M3U & Manual Playlist Generator</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #f4f6f9; color: #333; }
        .container { max-width: 950px; margin: auto; }
        .card { background: #fff; padding: 25px; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        .form-group { margin-bottom: 15px; }
        label { display: block; font-weight: bold; margin-bottom: 5px; }
        input[type="text"], input[type="file"] { width: 100%; padding: 8px; box-sizing: border-box; border: 1px solid #ccc; border-radius: 4px; }
        .btn { background: #007bff; color: white; border: none; padding: 10px 18px; border-radius: 4px; cursor: pointer; font-weight: bold; text-decoration: none; display: inline-block; }
        .btn:hover { background: #0056b3; }
        .btn-danger { background: #dc3545; }
        .btn-danger:hover { background: #bd2130; }
        .btn-success { background: #28a745; }
        .btn-success:hover { background: #218838; }
        pre { background: #272822; color: #f8f8f2; padding: 15px; border-radius: 5px; overflow-x: auto; max-height: 350px; }
        table { width: 100%; border-collapse: collapse; margin-top: 15px; }
        th, td { border: 1px solid #ddd; padding: 10px; text-align: left; font-size: 14px; word-break: break-all; }
        th { background: #007bff; color: white; }
        tr:nth-child(even) { background-color: #f9f9f9; }
        .badge { display: inline-block; padding: 3px 7px; font-size: 11px; font-weight: bold; color: #fff; background: #17a2b8; border-radius: 4px; }
        .badge-hero { background: #ffc107; color: #000; }
        .poster-img { width: 45px; height: 65px; object-fit: cover; border-radius: 4px; background: #eee; }
        .download-bar { display: flex; align-items: center; gap: 10px; }
        .download-bar input { width: 220px; }
    </style>
</head>
<body>

<div class="container">
    <div class="card">
        <h2>M3U & Manual Playlist Generator</h2>

        <form method="POST" enctype="multipart/form-data" id="playlistForm">
            <input type="hidden" name="existing_payload" id="existing_payload" value='{{ current_json_str }}'>

            <div class="form-group">
                <label>Category Name:</label>
                <input type="text" name="category_name" placeholder="e.g. Movies, Live Sports" required>
            </div>
            
            <div class="form-group">
                <label>Default Referer Header (Optional):</label>
                <input type="text" name="referer" placeholder="https://example.com/">
            </div>

            <hr>
            <h3>Option A: Upload M3U / M3U8 File</h3>
            <div class="form-group">
                <label>Select Playlist File:</label>
                <input type="file" name="m3u_file" accept=".m3u,.m3u8">
            </div>

            <hr>
            <h3>Option B: Add Single Item Manually</h3>
            <div class="form-group">
                <label>Title:</label>
                <input type="text" name="manual_title" placeholder="e.g. Fast & Furious">
            </div>
            <div class="form-group">
                <label>Poster URL:</label>
                <input type="text" name="manual_poster" placeholder="https://.../poster.jpg">
            </div>
            <div class="form-group">
                <label>Stream URL (HLS / m3u8 / http):</label>
                <input type="text" name="manual_url" placeholder="https://.../stream.m3u8">
            </div>

            <button type="submit" class="btn">Add to Playlist</button>
            <button type="button" onclick="clearData()" class="btn btn-danger">Clear All Data</button>
        </form>
    </div>

    {% if total_items > 0 %}
    <div class="card">
        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px;">
            <h3>Uploaded Links Details ({{ total_items }} Total)</h3>
            
            <!-- Custom Filename & Download Controls -->
            <div class="download-bar">
                <input type="text" id="custom_filename" placeholder="movies.json">
                <button onclick="downloadJSON()" class="btn btn-success">Export JSON</button>
            </div>
        </div>

        <table>
            <thead>
                <tr>
                    <th>Poster</th>
                    <th>ID / Title</th>
                    <th>Section / Category</th>
                    <th>Stream URL</th>
                    <th>Headers</th>
                </tr>
            </thead>
            <tbody>
                {% for item in all_details %}
                <tr>
                    <td>
                        {% if item.poster %}
                            <img src="{{ item.poster }}" class="poster-img" alt="Poster" onerror="this.src='https://via.placeholder.com/45x65?text=No+Cover'">
                        {% else %}
                            <span style="color:#aaa;">No Image</span>
                        {% endif %}
                    </td>
                    <td>
                        <strong>{{ item.title }}</strong><br>
                        <small style="color: #666;">ID: {{ item.id }}</small>
                    </td>
                    <td>
                        {% if item.category == 'HERO' %}
                            <span class="badge badge-hero">HERO SECTION</span>
                        {% else %}
                            <span class="badge">{{ item.category }}</span>
                        {% endif %}
                    </td>
                    <td><a href="{{ item.stream_url }}" target="_blank">{{ item.stream_url }}</a></td>
                    <td>
                        {% if item.headers and item.headers.Referer %}
                            <small>Referer: {{ item.headers.Referer }}</small>
                        {% else %}
                            <small style="color: #aaa;">None</small>
                        {% endif %}
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>

    <div class="card">
        <h3>Generated JSON Output Preview</h3>
        <pre id="jsonPreview">{{ current_json_pretty }}</pre>
    </div>
    {% endif %}
</div>

<script>
    const STORAGE_KEY = 'm3u_playlist_data_v5';

    document.addEventListener("DOMContentLoaded", () => {
        const payloadInput = document.getElementById('existing_payload');
        const storedData = localStorage.getItem(STORAGE_KEY);

        if (storedData && payloadInput.value === '{"hero":[],"categories":[]}') {
            payloadInput.value = storedData;
        }

        if (payloadInput.value && payloadInput.value !== '{"hero":[],"categories":[]}') {
            localStorage.setItem(STORAGE_KEY, payloadInput.value);
        }
    });

    function clearData() {
        if (confirm("Are you sure you want to delete all playlist links?")) {
            localStorage.removeItem(STORAGE_KEY);
            window.location.href = window.location.pathname;
        }
    }

    function downloadJSON() {
        const payloadInput = document.getElementById('existing_payload').value;
        let filename = document.getElementById('custom_filename').value.trim();

        // Add default filename if input is empty
        if (!filename) {
            filename = 'playlist.json';
        }
        
        // Append .json extension if omitted by user
        if (!filename.toLowerCase().endsWith('.json')) {
            filename += '.json';
        }

        const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(JSON.parse(payloadInput), null, 4));
        const downloadAnchor = document.createElement('a');
        downloadAnchor.setAttribute("href", dataStr);
        downloadAnchor.setAttribute("download", filename);
        document.body.appendChild(downloadAnchor);
        downloadAnchor.click();
        downloadAnchor.remove();
    }
</script>

</body>
</html>
"""

def generate_id(title):
    return re.sub(r'[^a-zA-Z0-9]', '_', title).lower()

@app.route('/playlist.json', methods=['GET'])
@app.route('/api/playlist.json', methods=['GET'])
def get_json_api():
    return jsonify(GLOBAL_PLAYLIST_CACHE)

@app.route('/', defaults={'path': ''}, methods=['GET', 'POST'])
@app.route('/<path:path>', methods=['GET', 'POST'])
def catch_all(path):
    global GLOBAL_PLAYLIST_CACHE
    playlist_data = {"hero": [], "categories": []}
    
    if request.method == 'POST':
        raw_payload = request.form.get('existing_payload', '')
        if raw_payload:
            try:
                playlist_data = json.loads(raw_payload)
            except Exception:
                playlist_data = {"hero": [], "categories": []}

        category_name = request.form.get('category_name', 'General').strip()
        referer = request.form.get('referer', '').strip()
        new_items = []

        # 1. Parse M3U File Upload
        m3u_file = request.files.get('m3u_file')
        if m3u_file and m3u_file.filename != '':
            content = m3u_file.read().decode('utf-8', errors='ignore')
            lines = content.splitlines()

            current_item = {}
            for line in lines:
                line = line.strip()
                if not line:
                    continue

                if line.startswith('#EXTINF:'):
                    logo_match = re.search(r'tvg-logo="([^"]+)"', line)
                    poster = logo_match.group(1) if logo_match else ''

                    comma_pos = line.rfind(',')
                    title = line[comma_pos + 1:].strip() if comma_pos != -1 else 'Untitled'

                    current_item = {
                        'id': generate_id(title),
                        'title': title,
                        'poster': poster
                    }
                elif line.startswith(('http://', 'https://')):
                    if current_item:
                        current_item['stream_url'] = line
                        current_item['headers'] = {'Referer': referer} if referer else {}
                        new_items.append(current_item)
                        current_item = {}

        # 2. Parse Manual Single Item
        manual_title = request.form.get('manual_title', '').strip()
        manual_url = request.form.get('manual_url', '').strip()
        manual_poster = request.form.get('manual_poster', '').strip()

        if manual_title and manual_url:
            new_items.append({
                'id': generate_id(manual_title),
                'title': manual_title,
                'poster': manual_poster,
                'stream_url': manual_url,
                'headers': {'Referer': referer} if referer else {}
            })

        # 3. Dynamic Split: Up to 5 items to Hero, remainder to Categories
        if new_items:
            current_hero_count = len(playlist_data.get('hero', []))
            needed_for_hero = 5 - current_hero_count

            if needed_for_hero > 0:
                hero_additions = new_items[:needed_for_hero]
                playlist_data['hero'].extend(hero_additions)
                category_items = new_items[needed_for_hero:]
            else:
                category_items = new_items

            if category_items:
                category_found = False
                for cat in playlist_data.get('categories', []):
                    if cat.get('name') == category_name:
                        cat['items'].extend(category_items)
                        category_found = True
                        break

                if not category_found:
                    if 'categories' not in playlist_data:
                        playlist_data['categories'] = []
                    playlist_data['categories'].append({
                        'name': category_name,
                        'items': category_items
                    })

    GLOBAL_PLAYLIST_CACHE = playlist_data

    all_details = []
    total_items = 0

    for item in playlist_data.get('hero', []):
        total_items += 1
        all_details.append({
            'category': 'HERO',
            'id': item.get('id', ''),
            'title': item.get('title', ''),
            'poster': item.get('poster', ''),
            'stream_url': item.get('stream_url', ''),
            'headers': item.get('headers', {})
        })

    for cat in playlist_data.get('categories', []):
        cat_name = cat.get('name', 'General')
        for item in cat.get('items', []):
            total_items += 1
            all_details.append({
                'category': cat_name,
                'id': item.get('id', ''),
                'title': item.get('title', ''),
                'poster': item.get('poster', ''),
                'stream_url': item.get('stream_url', ''),
                'headers': item.get('headers', {})
            })

    current_json_str = json.dumps(playlist_data)
    current_json_pretty = json.dumps(playlist_data, indent=4, ensure_ascii=False)

    return render_template_string(
        HTML_TEMPLATE,
        current_json_str=current_json_str,
        current_json_pretty=current_json_pretty,
        all_details=all_details,
        total_items=total_items
    )

handler = app
