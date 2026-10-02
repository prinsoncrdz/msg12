import os
import json
import re
import pdfplumber
from pypdf import PdfReader

def load_master_suppliers():
    json_path = os.path.join(os.path.dirname(__file__), 'static', 'suppliers.json')
    if os.path.exists(json_path):
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return []

MASTER_SUPPLIERS = load_master_suppliers()

def extract_pdf_data(pdf_path_or_file):
    """
    Extracts header metadata (Client, PO Number, MSG Ref) and line items
    from Sales Order / Purchase Order PDFs.
    Auto-detects supplier names from master list and machining instructions.
    """
    text = ""
    try:
        with pdfplumber.open(pdf_path_or_file) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
    except Exception as e:
        print(f"pdfplumber error: {e}")

    if not text.strip() and isinstance(pdf_path_or_file, str):
        try:
            with open(pdf_path_or_file, 'r', encoding='utf-8', errors='ignore') as f:
                text = f.read()
        except Exception:
            pass

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    full_text = "\n".join(lines)

    # --- Header Parsing ---
    client = ""
    po_number = ""
    msg_ref = ""

    so_match = re.search(r"(?:Sales\s*Order\s*#|MSG\s*Ref\s*:?)\s*([A-Z0-9\-_]+)", full_text, re.IGNORECASE)
    if so_match:
        msg_ref = so_match.group(1).strip()

    po_match = re.search(r"(?:Ref\s*#\s*:?|PO\s*(?:Number|#)?\s*:?)\s*([A-Z0-9\-_]+)", full_text, re.IGNORECASE)
    if po_match:
        po_number = po_match.group(1).strip()

    client_match = re.search(r"(?:Bill\s*To|Client\s*:?)\s*\n?([^\n]+)", full_text, re.IGNORECASE)
    if client_match:
        raw_client = client_match.group(1).strip()
        raw_client = re.sub(r"-AED$", "", raw_client, flags=re.IGNORECASE).strip()
        client = raw_client

    # --- Line Items Parsing ---
    items = []
    item_pattern = re.compile(r"^([1-9]\d{0,2})\s+(.+)")
    
    in_items = False
    current_item = None

    for i, line in enumerate(lines):
        if re.search(r"#\s*Item\s*&\s*Description", line, re.IGNORECASE):
            in_items = True
            continue
        
        if in_items and re.search(r"Sub\s*Total|Standard\s*Rate|Total|VAT", line, re.IGNORECASE):
            if current_item:
                items.append(current_item)
                current_item = None
            break

        if in_items:
            m = item_pattern.match(line)
            if m:
                if current_item:
                    items.append(current_item)
                    current_item = None

                sl_no = m.group(1)
                rest = m.group(2)
                
                num_pattern = re.compile(r"([\d,]+\.\d{2})")
                matches = list(num_pattern.finditer(rest))

                qty = ""
                uom = ""
                description = rest

                if len(matches) >= 2:
                    rate_idx = matches[-2].start()
                    desc_part = rest[:rate_idx].strip()
                    
                    sub_tokens = desc_part.split()
                    
                    for idx in range(len(sub_tokens) - 1, -1, -1):
                        token = sub_tokens[idx]
                        if re.match(r"^\d+(?:\.\d+)?$", token):
                            qty = token
                            if idx + 1 < len(sub_tokens) and not re.match(r"^\d+$", sub_tokens[idx + 1]):
                                uom = sub_tokens[idx + 1]
                            
                            desc_sub = sub_tokens[:idx]
                            if desc_sub and re.match(r"^\d{4,5}$", desc_sub[-1]):
                                desc_sub = desc_sub[:-1]
                            
                            description = " ".join(desc_sub)
                            break

                current_item = {
                    "sl_no": int(sl_no),
                    "description": description.strip(),
                    "qty": qty if qty else "1.00",
                    "uom": uom if uom else "",
                    "heat_number": "",
                    "certificate_number": "",
                    "make": "",
                    "remarks": "",
                    "supplier_name": "",
                    "supplier_po": "",
                    "machining_names": ""
                }
            else:
                if current_item:
                    if not re.search(r"Sub\s*Total|Standard\s*Rate|Total|VAT|Page|\d+\s*of\s*\d+", line, re.IGNORECASE):
                        # Filter out lines that are purely prices or standalone numbers e.g. "10000 3.00 150.00 450.00"
                        if re.match(r"^[\d\s.,pcsEAea\/]+$", line) and re.search(r"\d+\.\d{2}", line):
                            # Contains rate/amount numeric values - extract UOM if missing
                            uom_m = re.search(r"\b(pcs|ea|set|mtr|nos|pkg)\b", line, re.IGNORECASE)
                            if uom_m and not current_item["uom"]:
                                current_item["uom"] = uom_m.group(1).lower()
                            continue

                        clean_line = line
                        uom_match = re.search(r"\b(pcs|ea|set|mtr|nos|pkg)\b", clean_line, re.IGNORECASE)
                        if uom_match:
                            if not current_item["uom"]:
                                current_item["uom"] = uom_match.group(1).lower()
                            clean_line = re.sub(r"\b(pcs|ea|set|mtr|nos|pkg)\b", "", clean_line, flags=re.IGNORECASE).strip()
                        
                        if clean_line and not re.match(r"^\d{4,5}$", clean_line):
                            current_item["description"] += " " + clean_line

    if current_item:
        items.append(current_item)

    # Post-process items to auto-detect supplier and machining instructions
    machining_keywords = [r"machin", r"sch\.?\s*\d+", r"from\s+S\.", r"schedule"]
    
    for item in items:
        desc_rem = (item["description"] + " " + item["remarks"]).lower()
        
        # 1. Machining keyword check
        if any(re.search(kw, desc_rem, re.IGNORECASE) for kw in machining_keywords):
            if not item["machining_names"]:
                item["machining_names"] = "Machining Required"
        
        # 2. Master Supplier Auto-match
        if not item["supplier_name"]:
            for supplier in MASTER_SUPPLIERS:
                # Extract clean core name (e.g. "K.HASHIM", "GERAB", "DELCORTE", "Wilhelm Maass")
                core_name = re.sub(r"\b(LLC|FZE|FZC|L\.L\.C|PTE|LTD|CO|INC|S\.P\.A|BV)\b", "", supplier, flags=re.IGNORECASE).strip()
                if len(core_name) > 3 and core_name.lower() in desc_rem:
                    item["supplier_name"] = supplier
                    break

    return {
        "client": client,
        "po_number": po_number,
        "msg_ref": msg_ref,
        "items": items
    }
