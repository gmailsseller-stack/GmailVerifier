from flask import Flask, render_template, request, jsonify
import threading
import os
import json
from datetime import datetime

app = Flask(__name__)

# استيراد المدقق
from gmail_verifier import GmailVerifier

# تهيئة المدقق
verifier = GmailVerifier(base_path="/app/data")
verification_thread = None

# ========== Routes ==========
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/health')
def health():
    return "OK", 200

@app.route('/api/start', methods=['POST'])
def start_verification():
    global verification_thread
    
    if verifier.is_running:
        return jsonify({'error': 'فحص قيد التشغيل حالياً'}), 400
    
    def run():
        verifier.start_verification()
    
    verification_thread = threading.Thread(target=run)
    verification_thread.daemon = True
    verification_thread.start()
    
    return jsonify({'status': 'started'})

@app.route('/api/stop', methods=['POST'])
def stop_verification():
    verifier.stop_verification()
    return jsonify({'status': 'stopped'})

@app.route('/api/status', methods=['GET'])
def get_status():
    return jsonify(verifier.get_status())

@app.route('/api/results', methods=['GET'])
def get_results():
    return jsonify({
        'live': verifier.results.get('live', [])[-100:],
        'new_disabled': verifier.results.get('new_disabled', [])[-100:],
        'invalid': verifier.results.get('invalid', [])[-100:]
    })

@app.route('/api/download/<category>', methods=['GET'])
def download_results(category):
    from flask import send_file
    
    file_map = {
        'live': verifier.live_file,
        'new_disabled': verifier.new_disabled_file,
        'invalid': verifier.invalid_file
    }
    
    if category in file_map and os.path.exists(file_map[category]):
        return send_file(
            file_map[category],
            as_attachment=True,
            download_name=f"{category}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        )
    
    return jsonify({'error': 'File not found'}), 404
@app.route('/api/list-files', methods=['GET'])
def list_files():
    import os
    disabled_path = "/app/data/disabled"
    result = {
        'path': disabled_path,
        'exists': os.path.exists(disabled_path),
        'files': []
    }
    
    if os.path.exists(disabled_path):
        for file in os.listdir(disabled_path):
            if file.endswith('.txt'):
                file_path = os.path.join(disabled_path, file)
                with open(file_path, 'r') as f:
                    lines = f.readlines()
                    result['files'].append({
                        'name': file,
                        'count': len([l for l in lines if '@gmail.com' in l])
                    })
    
    return jsonify(result)

@app.route('/api/debug', methods=['GET'])
def debug():
    import os
    disabled_path = "/app/data/disabled"
    files = []
    
    if os.path.exists(disabled_path):
        for f in os.listdir(disabled_path):
            if f.endswith('.txt'):
                path = os.path.join(disabled_path, f)
                with open(path, 'r') as file:
                    lines = file.readlines()
                files.append({
                    'name': f,
                    'lines': len(lines),
                    'sample': [l.strip() for l in lines[:3]]
                })
    
    return jsonify({
        'path_exists': os.path.exists(disabled_path),
        'disabled_path': disabled_path,
        'files': files
    })
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)
