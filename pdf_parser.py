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

COMMON_ITEM_WORDS = {
    "THREADOLET", "SPECTACLE", "UNION", "ELBOW", "FLANGE", "GASKET",
    "NIPPOLET", "WELDOLET", "SOCKOLET", "VALVE", "REDUCER", "COUPLING",
    "NIPPLE", "PIPE", "STUD", "BOLT", "NUT", "BLEED", "ORIFICE",
    "INSULATING", "SWAGELOK", "NEEDLE", "TEE", "CAP", "CROSS", "BUSHING", "PLUG"
}

REMARK_PATTERN = re.compile(
    r"\b(machined(?:\s+from)?|modified(?:\s+from)?|offered|made\s+from|fabricated(?:\s+from)?|locally)\b.*",
    re.IGNORECASE
)

MAKE_MAPPINGS = [
    (r"OMSA[-_]?STOCK|OMSA", "OMSA GERMANY"),
    (r"JD[-_]?STOCK|\bDELCORTE\b", "DELCORTE GERMANY"),
    (r"W[-_]?STOCK|WMA?ASS", "WMASS GERMANY"),
    (r"TK[-_]?STOCK", "TK KOREA"),
    (r"ST&H(?:[-_]?STOCK)?|STH", "ST&H KOREA"),
    (r"\bMFF\b|METALFAR", "Metalfar Italy"),
    (r"BENKAN", "BENKAN THAILAND"),
    (r"ULMA", "ULMA SPAIN"),
    (r"MELESI", "MELESI ITALY"),
]

def auto_detect_make(raw_text):
    """
    Auto-detects manufacturer / MAKE name from raw item description or product code.
    Mappings:
      - MFF -> Metalfar Italy
      - BENKAN -> BENKAN THAILAND
      - ST&H / STH -> ST&H KOREA
      - W-STOCK / WMAASS / WMASS -> WMASS GERMANY
      - JD-STOCK / DELCORTE -> DELCORTE GERMANY
      - OMSA-STOCK / OMSA -> OMSA GERMANY
      - TK-STOCK -> TK KOREA
      - ULMA -> ULMA SPAIN
      - MELESI -> MELESI ITALY
    """
    if not raw_text:
        return ""
    for pattern, make_val in MAKE_MAPPINGS:
        if re.search(pattern, raw_text, re.IGNORECASE):
            return make_val
    return ""

def strip_leading_item_number(description, sl_no=None):
    """
    Strips leading item sequence numbers (e.g. '1 ', '2 ', '1. ', '01 ') from the beginning of descriptions,
    while preserving actual size measurements like '1"', '1/2"', '2"'.
    """
    if not description:
        return ""
    desc = description.strip()
    if sl_no is not None:
        pattern = rf"^0*{sl_no}\s*[\.\-]?\s+(?![\"\/])"
        desc = re.sub(pattern, "", desc, flags=re.IGNORECASE).strip()
    # Also strip generic leading index number if followed by dot/dash
    desc = re.sub(r"^\d{1,3}\s*[\.\-]\s+(?![\"\/])", "", desc).strip()
    return desc

def strip_internal_product_code(description):
    """
    Strips internal product codes like LBL25300RF, LTO156KA350LF2, LUN256KNPTA105N,
    XEL90250S40SRWPB, BL151500RF, EL90256KNPTA105JD-STOCK from the beginning of item descriptions.
    Preserves standard fitting names (THREADOLET, SPECTACLE, UNION, ELBOW, etc.).
    """
    if not description:
        return ""
    desc = description.strip()
    tokens = desc.split(maxsplit=1)
    if tokens and len(tokens) > 1:
        first_token = tokens[0].strip()
        if first_token.upper() not in COMMON_ITEM_WORDS:
            # Alphanumeric codes starting with 2+ uppercase letters, length 5-45 (supporting &, -, _, /)
            if re.match(r"^[A-Z]{2,}[A-Z0-9\-_\/&]{3,45}$", first_token):
                desc = tokens[1].strip()
    return desc

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

                client_po_item_no = ""
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
                                client_po_item_no = desc_sub[-1]
                                desc_sub = desc_sub[:-1]
                            
                            description = " ".join(desc_sub)
                            break

                current_item = {
                    "sl_no": int(sl_no),
                    "client_po_item_no": client_po_item_no if client_po_item_no else str(sl_no),
                    "description": description.strip(),
                    "qty": qty if qty else "1.00",
                    "uom": uom if uom else "",
                    "heat_number": "",
                    "certificate_number": "",
                    "make": "",
                    "remarks": "",
                    "supplier_name": "",
                    "supplier_po": ""
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
                            rem_m = REMARK_PATTERN.search(clean_line)
                            if rem_m:
                                remark_txt = rem_m.group(0).strip()
                                if current_item["remarks"]:
                                    current_item["remarks"] += "; " + remark_txt
                                else:
                                    current_item["remarks"] = remark_txt
                                
                                desc_part = REMARK_PATTERN.sub('', clean_line).rstrip(' -:,;')
                                if desc_part:
                                    current_item["description"] += " " + desc_part
                            else:
                                current_item["description"] += " " + clean_line

    if current_item:
        items.append(current_item)

    # Post-process items to strip product codes & auto-detect supplier
    for item in items:
        # Strip leading item sequence numbers e.g. "1 ECC. RED..." -> "ECC. RED..."
        item["description"] = strip_leading_item_number(item["description"], item["sl_no"])

        raw_full = item["description"] + " " + item["remarks"]

        # Auto-detect MAKE from code / raw item description if empty
        if not item["make"]:
            detected_make = auto_detect_make(raw_full)
            if detected_make:
                item["make"] = detected_make
        
        # Check if code or description contains STOCK
        if re.search(r"[-_\s/]?STOCK\b", raw_full, re.IGNORECASE):
            item["supplier_name"] = "STOCK"

        # Check if description itself contains remark patterns
        rem_match = REMARK_PATTERN.search(item["description"])
        if rem_match:
            remark_text = rem_match.group(0).strip()
            cleaned_desc = REMARK_PATTERN.sub('', item["description"]).rstrip(' -:,;')
            item["description"] = cleaned_desc
            if item["remarks"]:
                if remark_text.lower() not in item["remarks"].lower():
                    item["remarks"] += "; " + remark_text
            else:
                item["remarks"] = remark_text

        # Strip internal product codes e.g. LBL25300RF, LTO156KA350LF2, LUN256KNPTA105N
        item["description"] = strip_internal_product_code(item["description"])

        # Strip leading item number again if revealed after code stripping
        item["description"] = strip_leading_item_number(item["description"], item["sl_no"])

        # Master Supplier Auto-match (if supplier_name is not already set)
        if not item["supplier_name"]:
            desc_rem = (item["description"] + " " + item["remarks"]).lower()
            for supplier in MASTER_SUPPLIERS:
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
