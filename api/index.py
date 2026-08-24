import os
import re
import json
from flask import Flask, request, render_template_string

app = Flask(__name__)

# Base directory where all JSON files and uploads are stored
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>M3U to JSON Playlist Converter</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 30px; background: #f4f6f9; }
        .card { background: #fff; padding: 25px; border-radius: 8px; max-width: 650px; margin: auto; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        .form-group { margin-bottom: 15px; }
        label { display: block; font-weight: bold; margin-bottom: 5px; }
        input[type="text"], input[type="file"] { width: 100%; padding: 8px; box-sizing: border-box; }
        button { background: #007bff; color: white; border: none; padding: 10px 20px; border-radius: 4px; cursor: pointer; }
        button:hover { background: #0056b3; }
        pre { background: #272822; color: #f8f8f2; padding: 15px; border-radius: 5px; overflow-x: auto; max-height: 400px; }
        .msg-success { color: green; margin-bottom: 15px; }
        .msg-error { color: red; margin-bottom: 15px; }
    </style>
</head>
<body>

<div class="card">
    <h2>M3U to JSON Generator</h2>
    {% if message %}
        {{ message | safe }}
    {% endif %}
    
    <form method="POST" enctype="multipart/form-data">
        <div class="form-group">
            <label>JSON Output File Name:</label>
            <input type="text" name="json_filename" value="{{ current_file }}" placeholder="e.g. playlist.json" required>
        </div>

        <div class="form-group">
            <label>Category Name:</label>
            <input type="text" name="category_name" placeholder="e.g. Movies, Live Sports" required>
        </div>
        
        <div class="form-group">
            <label>Default Referer Header (Optional):</label>
            <input type="text" name="referer" placeholder="https://example.com/">
        </div>

        <hr>
        <h3>Option A: Upload M3U File</h3>
        <div class="form-group">
            <label>Select .m3u / .m3u8 file:</label>
            <input type="file" name="m3u_file" accept=".m3u,.m3u8">
        </div>

        <hr>
        <h3>Option B: Add Single Item Manually</h3>
        <div class="form-group">
            <label>Title:</label>
            <input type="text" name="manual_title" placeholder="Gehraiyaan">
        </div>
        <div class="form-group">
            <label>Poster URL:</label>
            <input type="text" name="manual_poster" placeholder="https://.../image.jpg">
        </div>
        <div class="form-group">
            <label>Stream URL (HLS / m3u8):</label>
            <input type="text" name="manual_url" placeholder="https://.../h264_high.m3u8">
        </div>

        <button type="submit">Generate & Save JSON</button>
    </form>

    {% if json_content %}
        <hr>
        <h3>Current Output ({{ current_file }}):</h3>
        <pre>{{ json_content }}</pre>
    {% endif %}
</div>

</body>
</html>
"""

def generate_id(title):
    return re.sub(r'[^a-zA-Z0-9]', '_', title).lower()

@app.route('/', methods=['GET', 'POST'])
def index():
    message = ''
    json_filename = 'playlist.json'
    items = []

    if request.method == 'POST':
        # Get custom filename or default
        json_filename = request.form.get('json_filename', 'playlist.json').strip()
        if not json_filename.endswith('.json'):
            json_filename += '.json'

        category_name = request.form.get('category_name', 'General').strip()
        referer = request.form.get('referer', '').strip()

        # 1. Process M3U File Upload
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
                    # Extract tvg-logo
                    logo_match = re.search(r'tvg-logo="([^"]+)"', line)
                    poster = logo_match.group(1) if logo_match else ''

                    # Extract title (after comma)
                    comma_pos = line.rfind(',')
                    title = line[comma_pos + 1:].strip() if comma_pos != -1 else 'Untitled'

                    current_item = {
                        'id': generate_id(title),
                        'title': title,
                        'poster': poster
                    }
                elif line.startswith('http://') or line.startswith('https://'):
                    if current_item:
                        current_item['stream_url'] = line
                        current_item['headers'] = {'Referer': referer}
                        items.append(current_item)
                        current_item = {}

        # 2. Process Manual Single Item
        manual_title = request.form.get('manual_title', '').strip()
        manual_url = request.form.get('manual_url', '').strip()
        manual_poster = request.form.get('manual_poster', '').strip()

        if manual_title and manual_url:
            items.append({
                'id': generate_id(manual_title),
                'title': manual_title,
                'poster': manual_poster,
                'stream_url': manual_url,
                'headers': {'Referer': referer}
            })

        # 3. Build / Update JSON Structure
        if items:
            json_filepath = os.path.join(BASE_DIR, json_filename)

            # Load existing JSON or create a new template structure
            if os.path.exists(json_filepath):
                try:
                    with open(json_filepath, 'r', encoding='utf-8') as f:
                        existing_data = json.load(f)
                except Exception:
                    existing_data = {'hero': [], 'categories': []}
            else:
                existing_data = {'hero': [], 'categories': []}

            # Populate Hero section if currently empty
            if not existing_data.get('hero'):
                existing_data['hero'] = [items[0]]

            # Add to targeted category or update existing category
            category_found = False
            for cat in existing_data.get('categories', []):
                if cat.get('name') == category_name:
                    cat['items'].extend(items)
                    category_found = True
                    break

            if not category_found:
                if 'categories' not in existing_data:
                    existing_data['categories'] = []
                existing_data['categories'].append({
                    'name': category_name,
                    'items': items
                })

            # Save updated JSON to the same directory
            try:
                with open(json_filepath, 'w', encoding='utf-8') as f:
                    json.dump(existing_data, f, indent=4, ensure_ascii=False)
                message = f'<div class="msg-success">Successfully saved to <strong>{json_filename}</strong>!</div>'
            except Exception as e:
                message = f'<div class="msg-error">Error saving JSON file: {str(e)}</div>'
        else:
            message = '<div class="msg-error">No valid M3U file or manual entry provided.</div>'

    # Read the current/selected JSON file contents to display on the page
    json_filepath = os.path.join(BASE_DIR, json_filename)
    json_content = ''
    if os.path.exists(json_filepath):
        with open(json_filepath, 'r', encoding='utf-8') as f:
            json_content = f.read()

    return render_template_string(
        HTML_TEMPLATE,
        message=message,
        current_file=json_filename,
        json_content=json_content
    )

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
    
