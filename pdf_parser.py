import re
import pdfplumber
from pypdf import PdfReader

def extract_pdf_data(pdf_path_or_file):
    """
    Extracts header metadata (Client, PO Number, MSG Ref) and line items
    from Sales Order / Purchase Order PDFs.
    """
    text = ""
    # 1. Try pdfplumber first
    try:
        with pdfplumber.open(pdf_path_or_file) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
    except Exception as e:
        print(f"pdfplumber error: {e}")

    # Fallback to pypdf if text is short
    if not text.strip():
        try:
            reader = PdfReader(pdf_path_or_file)
            for page in reader.pages:
                t = page.extract_text()
                if t:
                    text += t + "\n"
        except Exception as e:
            print(f"pypdf error: {e}")

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    full_text = "\n".join(lines)

    # --- Header Parsing ---
    client = ""
    po_number = ""
    msg_ref = ""

    # MSG Ref: Sales Order# MSG-0926-2127 or MSG Ref: MSG-0926-2127
    so_match = re.search(r"(?:Sales\s*Order\s*#|MSG\s*Ref\s*:?)\s*([A-Z0-9\-_]+)", full_text, re.IGNORECASE)
    if so_match:
        msg_ref = so_match.group(1).strip()

    # PO Number: Ref# : U-PO003447 or PO Number: U-PO003447
    po_match = re.search(r"(?:Ref\s*#\s*:?|PO\s*(?:Number|#)?\s*:?)\s*([A-Z0-9\-_]+)", full_text, re.IGNORECASE)
    if po_match:
        po_number = po_match.group(1).strip()

    # Client Name: Under "Bill To" or "Client :"
    client_match = re.search(r"(?:Bill\s*To|Client\s*:?)\s*\n?([^\n]+)", full_text, re.IGNORECASE)
    if client_match:
        raw_client = client_match.group(1).strip()
        # Clean suffix if present like "-AED" or common trailing terms
        raw_client = re.sub(r"-AED$", "", raw_client, flags=re.IGNORECASE).strip()
        client = raw_client

    # --- Line Items Parsing ---
    items = []
    item_pattern = re.compile(r"^(\d+)\s+(.+)")
    
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
                    "machining_names": ""
                }
            else:
                if current_item:
                    if not re.search(r"pcs|Sub\s*Total|Page|\d+\s*of\s*\d+", line, re.IGNORECASE):
                        current_item["description"] += " " + line
                    elif "pcs" in line.lower() and not current_item["uom"]:
                        current_item["uom"] = "pcs"

    if current_item:
        items.append(current_item)

    # Post-process items to auto-detect machining instructions in description or remarks
    machining_keywords = [r"machin", r"sch\.?\s*\d+", r"from\s+S\.", r"schedule"]
    for item in items:
        desc_rem = (item["description"] + " " + item["remarks"]).lower()
        if any(re.search(kw, desc_rem, re.IGNORECASE) for kw in machining_keywords):
            if not item["machining_names"]:
                item["machining_names"] = "Machining Required"

    return {
        "client": client,
        "po_number": po_number,
        "msg_ref": msg_ref,
        "items": items
    }

