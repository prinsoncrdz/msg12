import os
import io
import argparse
import base64
import fitz # PyMuPDF
from flask import Flask, render_template, request, jsonify, send_file, session, redirect, url_for
from functools import wraps
from excel_parser import parse_excel_summary
from pdf_generator import generate_loc_pdf

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'msg-oilfield-loc-secret-key-2026')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB max upload

# Strong production login credentials
DEFAULT_USER_EMAIL = "info@msgoilfield.com"
STRONG_PASSWORD = os.environ.get('MSG_PASSWORD', 'MSG@Oilfield#2026!')

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('user_logged_in'):
            if request.path.startswith('/api/'):
                return jsonify({'success': False, 'error': 'Authentication required. Please log in.'}), 401
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/login', methods=['GET'])
def login():
    if session.get('user_logged_in'):
        return redirect(url_for('index'))
    return render_template('login.html', email=DEFAULT_USER_EMAIL)

@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.get_json() or {}
    email = data.get('email', '').strip()
    password = data.get('password', '').strip()

    if email.lower() == DEFAULT_USER_EMAIL.lower() and password == STRONG_PASSWORD:
        session['user_logged_in'] = True
        session['user_email'] = DEFAULT_USER_EMAIL
        return jsonify({'success': True, 'redirect': '/'})
    else:
        return jsonify({'success': False, 'error': 'Invalid email or password.'}), 401

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    return render_template('index.html', user_email=session.get('user_email', DEFAULT_USER_EMAIL))

@app.route('/api/upload', methods=['POST'])
@login_required
def upload_excel():
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'No file uploaded'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'error': 'No selected file'}), 400

    include_all = request.form.get('include_all', 'false').lower() == 'true'

    try:
        data = parse_excel_summary(file, include_all=include_all)
        return jsonify({
            'success': True,
            'metadata': data['metadata'],
            'items': data['items']
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

def filter_loc_items(items, filter_empty_remarks=True):
    """Filter out items that do not have remarks if filter_empty_remarks is True."""
    if not filter_empty_remarks:
        return items
    return [it for it in items if it.get('remarks') and str(it.get('remarks')).strip()]

@app.route('/api/generate-pdf', methods=['POST'])
@login_required
def generate_pdf():
    req_data = request.get_json()
    if not req_data:
        return jsonify({'success': False, 'error': 'Invalid request payload'}), 400

    metadata = req_data.get('metadata', {})
    items = req_data.get('items', [])
    filter_empty = req_data.get('filter_empty_remarks', True)
    signature_data = req_data.get('signature_data', None)
    stamp_data = req_data.get('stamp_data', None)
    include_signature = req_data.get('include_signature', True)
    include_stamp = req_data.get('include_stamp', True)

    filtered_items = filter_loc_items(items, filter_empty)

    if not filtered_items:
        return jsonify({
            'success': False,
            'error': 'No items with Remarks found. Letter of Compliance is only issued for modified/fabricated materials with Remarks.'
        }), 400

    try:
        pdf_buffer = io.BytesIO()
        generate_loc_pdf(metadata, filtered_items, pdf_buffer, signature_data=signature_data, stamp_data=stamp_data, include_signature=include_signature, include_stamp=include_stamp)
        pdf_buffer.seek(0)
        
        filename = f"LOC_{metadata.get('po_number', 'Document')}.pdf".replace(' ', '_')
        return send_file(
            pdf_buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/preview-pdf', methods=['POST'])
@login_required
def preview_pdf():
    req_data = request.get_json()
    if not req_data:
        return jsonify({'success': False, 'error': 'Invalid request payload'}), 400

    metadata = req_data.get('metadata', {})
    items = req_data.get('items', [])
    filter_empty = req_data.get('filter_empty_remarks', True)
    signature_data = req_data.get('signature_data', None)
    stamp_data = req_data.get('stamp_data', None)
    include_signature = req_data.get('include_signature', True)
    include_stamp = req_data.get('include_stamp', True)

    filtered_items = filter_loc_items(items, filter_empty)

    if not filtered_items:
        return jsonify({
            'success': False,
            'error': 'No items with Remarks. Add a remark to an item to print on the LOC PDF.'
        }), 400

    try:
        pdf_buffer = io.BytesIO()
        generate_loc_pdf(metadata, filtered_items, pdf_buffer, signature_data=signature_data, stamp_data=stamp_data, include_signature=include_signature, include_stamp=include_stamp)
        pdf_bytes = pdf_buffer.getvalue()

        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        page_imgs = []
        for i in range(len(doc)):
            pix = doc[i].get_pixmap(dpi=140)
            img_b64 = base64.b64encode(pix.tobytes("png")).decode('utf-8')
            page_imgs.append(f"data:image/png;base64,{img_b64}")

        pdf_b64 = base64.b64encode(pdf_bytes).decode('utf-8')

        return jsonify({
            'success': True,
            'page_count': len(doc),
            'page_images': page_imgs,
            'item_count': len(filtered_items),
            'pdf_data': f"data:application/pdf;base64,{pdf_b64}"
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

from cloudinary_storage import (
    is_cloudinary_configured,
    save_summary_backup,
    search_summary_backups,
    restore_summary_backup,
    delete_summary_backup
)

@app.route('/api/backups/status', methods=['GET'])
@login_required
def backup_status():
    return jsonify({
        'success': True,
        'cloudinary_configured': is_cloudinary_configured()
    })

@app.route('/api/backups/save', methods=['POST'])
@login_required
def save_backup_endpoint():
    req_data = request.get_json() or {}
    metadata = req_data.get('metadata', {})
    items = req_data.get('items', [])
    pdf_b64 = req_data.get('pdf_b64', None)

    if not metadata or not items:
        return jsonify({'success': False, 'error': 'Metadata and items are required to save a backup'}), 400

    try:
        user_email = session.get('user_email', DEFAULT_USER_EMAIL)
        res = save_summary_backup(metadata, items, user_email=user_email, pdf_b64=pdf_b64)
        return jsonify(res)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/backups/search', methods=['GET'])
@login_required
def search_backups_endpoint():
    query = request.args.get('query', '')
    try:
        results = search_summary_backups(query)
        return jsonify({
            'success': True,
            'query': query,
            'count': len(results),
            'backups': results,
            'cloudinary_configured': is_cloudinary_configured()
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/backups/restore/<path:backup_id>', methods=['GET'])
@login_required
def restore_backup_endpoint(backup_id):
    try:
        data = restore_summary_backup(backup_id)
        return jsonify({
            'success': True,
            'data': data
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 404

@app.route('/api/backups/delete/<path:backup_id>', methods=['DELETE'])
@login_required
def delete_backup_endpoint(backup_id):
    try:
        res = delete_summary_backup(backup_id)
        return jsonify(res)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="LOC PDF Generator Web Server")
    parser.add_argument('--port', type=int, default=int(os.environ.get('PORT', 5050)), help="Port to run the server on (default: 5050)")
    parser.add_argument('--host', type=str, default='0.0.0.0', help="Host address (default: 0.0.0.0)")
    args = parser.parse_args()

    print("=" * 60)
    print("MSG OILFIELD EQUIPMENT TRADING LLC - LOC GENERATOR")
    print(f"Login Email: {DEFAULT_USER_EMAIL}")
    print(f"Server URL: http://localhost:{args.port}")
    print("=" * 60)

    app.run(host=args.host, port=args.port, debug=True)
