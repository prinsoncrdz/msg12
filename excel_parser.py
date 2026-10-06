import openpyxl
import re
import datetime

def parse_excel_summary(file_path_or_stream, include_all=False):
    """
    Parses an Excel summary sheet for LOC generation.
    Extracts header metadata (Date, Client/TO, PO Number, MSG Ref, Action Type)
    and line items (sl_no, description, po_qty, uom, heat_number, remarks).
    """
    wb = openpyxl.load_workbook(file_path_or_stream, data_only=True)
    sheet = wb.active

    metadata = {
        "date": datetime.date.today().strftime("%d/%m/%Y"),
        "to_client": "",
        "po_number": "",
        "msg_ref": "",
        "signatory_name": "Vijay Dsouza",
        "signatory_title": "( QA / QC Dept )",
        "action_type": "fabricated"
    }

    items = []
    rows = list(sheet.iter_rows(values_only=True))

    if not rows:
        return {"metadata": metadata, "items": items}

    # Extract metadata from top rows before table
    for r in rows[:15]:
        if not r:
            continue
        row_str = " ".join([str(cell) for cell in r if cell is not None])
        
        # Check Client / TO
        client_match = re.search(r'(?:CLIENT|TO)\s*[:=\-]\s*([^\n\r]+)', row_str, re.IGNORECASE)
        if client_match and not metadata["to_client"]:
            metadata["to_client"] = client_match.group(1).strip()
            
        # Check PO Number
        po_match = re.search(r'(?:PO\s*NUMBER|PO\s*NO|PO#)\s*[:=\-]\s*([^\n\r]+)', row_str, re.IGNORECASE)
        if po_match and not metadata["po_number"]:
            metadata["po_number"] = po_match.group(1).strip()
            
        # Check MSG Ref
        ref_match = re.search(r'(?:MSG\s*REF|REF\s*NO|REF#)\s*[:=\-]\s*([^\n\r]+)', row_str, re.IGNORECASE)
        if ref_match and not metadata["msg_ref"]:
            metadata["msg_ref"] = ref_match.group(1).strip()

        # Check Date
        date_match = re.search(r'(?:DATE)\s*[:=\-]\s*([^\n\r]+)', row_str, re.IGNORECASE)
        if date_match:
            d_val = date_match.group(1).strip()
            if d_val:
                metadata["date"] = d_val

    # Locate table header row dynamically
    header_idx = -1
    headers = []
    for idx, row in enumerate(rows[:20]):
        if not row:
            continue
        row_upper = [str(cell).upper().strip() if cell is not None else '' for cell in row]
        if any('DESCRIPTION' in h for h in row_upper) or any('SL' in h for h in row_upper):
            header_idx = idx
            headers = [str(cell).strip() if cell is not None else '' for cell in row]
            break

    if header_idx == -1:
        header_idx = 0
        headers = [str(cell).strip() if cell is not None else '' for cell in rows[0]]

    def find_col_idx(candidates):
        for candidate in candidates:
            cand_clean = re.sub(r'[^A-Z0-9]', '', candidate.upper())
            for i, h in enumerate(headers):
                h_clean = re.sub(r'[^A-Z0-9]', '', h.upper())
                if cand_clean == h_clean or cand_clean in h_clean:
                    return i
        return -1

    col_sl = find_col_idx(['SL NO', 'SL.NO', 'S.NO', 'SLNO', 'SERIAL', 'ITEM NO'])
    col_desc = find_col_idx(['DESCRIPTION', 'ITEM DESCRIPTION', 'DESC'])
    col_qty = find_col_idx(['PO QTY', 'PO QUANTITY', 'QTY', 'QUANTITY'])
    col_uom = find_col_idx(['UOM', 'UNIT'])
    col_heat = find_col_idx(['HEAT NUMBER', 'HEAT NO', 'HEAT#'])
    col_rem = find_col_idx(['REMARKS', 'REMARK', 'REMARKS-1', 'REMARKS 1'])

    found_actions = set()

    for row in rows[header_idx + 1:]:
        if not row or all(c is None or str(c).strip() == '' for c in row):
            continue

        def get_val(col_i):
            if col_i != -1 and col_i < len(row):
                v = row[col_i]
                if v is not None:
                    if isinstance(v, float) and v.is_integer():
                        return str(int(v))
                    return str(v).strip()
            return ''

        sl_no = get_val(col_sl)
        desc = get_val(col_desc)
        remarks = get_val(col_rem)

        if not desc and not sl_no:
            continue
        if 'TOTAL' in desc.upper() or 'SUMMARY' in desc.upper():
            continue

        # Detect actions from remarks text:
        # 'MADE', 'MADE FROM', 'FABRICAT', 'PLATE' -> FABRICATED
        rem_lower = remarks.lower()
        if 'made' in rem_lower or 'fabricat' in rem_lower or 'plate' in rem_lower:
            found_actions.add('fabricated')
        if 'machin' in rem_lower or 'thread' in rem_lower:
            found_actions.add('machined')
        if 'modif' in rem_lower or 'modified' in rem_lower:
            found_actions.add('modified')

        if not include_all and not remarks.strip():
            continue

        item = {
            "sl_no": sl_no or str(len(items) + 1),
            "description": desc,
            "po_qty": get_val(col_qty),
            "uom": get_val(col_uom),
            "heat_number": get_val(col_heat),
            "remarks": remarks
        }
        items.append(item)

    ordered_actions = []
    for act in ['fabricated', 'machined', 'modified']:
        if act in found_actions:
            ordered_actions.append(act)

    if ordered_actions:
        metadata['action_type'] = " / ".join(ordered_actions)
    else:
        metadata['action_type'] = 'fabricated'

    return {"metadata": metadata, "items": items}
