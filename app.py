import os
import sys
import json
import tempfile
from flask import Flask, render_template, request, jsonify, send_file

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from pdf_parser import extract_pdf_data, load_master_suppliers
from excel_generator import generate_summary_excel
from supplier_pdf_generator import generate_all_supplier_pdfs_zip

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, 'templates'),
    static_folder=os.path.join(BASE_DIR, 'static')
)
app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/suppliers', methods=['GET'])
def get_suppliers():
    suppliers = load_master_suppliers()
    return jsonify({"success": True, "suppliers": suppliers})

@app.route('/api/parse', methods=['POST'])
def parse_pdf():
    if 'pdf_file' not in request.files:
        return jsonify({"success": False, "error": "No PDF file uploaded"}), 400
    
    file = request.files['pdf_file']
    if file.filename == '':
        return jsonify({"success": False, "error": "No selected file"}), 400

    if not file.filename.lower().endswith('.pdf'):
        return jsonify({"success": False, "error": "Uploaded file must be a PDF"}), 400

    temp_dir = tempfile.gettempdir()
    temp_pdf_path = os.path.join(temp_dir, file.filename)
    file.save(temp_pdf_path)

    try:
        extracted = extract_pdf_data(temp_pdf_path)
        return jsonify({
            "success": True,
            "data": extracted
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        if os.path.exists(temp_pdf_path):
            try:
                os.remove(temp_pdf_path)
            except Exception:
                pass

@app.route('/api/download', methods=['POST'])
def download_excel():
    try:
        data = request.json
        if not data:
            return jsonify({"error": "No JSON payload provided"}), 400

        msg_ref = data.get("msg_ref", "SUMMARY").replace(" ", "_")
        po_num = data.get("po_number", "").replace(" ", "_")
        is_internal = bool(data.get("is_internal", False))
        
        prefix = "Internal_Stores_Summary" if is_internal else "Client_Summary"
        filename = f"{prefix}_{msg_ref}_{po_num}.xlsx" if po_num else f"{prefix}_{msg_ref}.xlsx"
        
        stream = generate_summary_excel(data, is_internal=is_internal)
        
        return send_file(
            stream,
            as_attachment=True,
            download_name=filename,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/export-supplier-pdfs', methods=['POST'])
def export_supplier_pdfs():
    try:
        data = request.json
        if not data:
            return jsonify({"error": "No JSON payload provided"}), 400

        msg_ref = data.get("msg_ref", "SO").replace(" ", "_")
        zip_filename = f"Supplier_PO_Package_{msg_ref}.zip"
        
        zip_stream = generate_all_supplier_pdfs_zip(data)
        
        return send_file(
            zip_stream,
            as_attachment=True,
            download_name=zip_filename,
            mimetype="application/zip"
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=True)
