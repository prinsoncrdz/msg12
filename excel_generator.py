import os
import re
import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.drawing.image import Image

MANUFACTURING_KEYWORDS = ["machined", "fabricated", "made from", "modified", "locally"]

def is_meaningful_item(item):
    """
    Checks if an item contains meaningful manufacturing/sourcing keywords in remarks or description.
    Keywords: Machined From, Fabricated From, Made from, Modified from, Locally.
    """
    text = (str(item.get("remarks", "")) + " " + str(item.get("description", ""))).lower()
    return any(re.search(r"\b" + kw, text, re.IGNORECASE) for kw in MANUFACTURING_KEYWORDS)

def generate_summary_excel(data, logo_path=None, output_path=None, is_internal=False, filter_machined_only=True):
    """
    Generates a Summary Sheet Excel workbook.
    - If is_internal=False (Client export): 8 columns (SL NO, Description [width=85], PO Qty, UOM, Heat Number, Certificate Number, MAKE, Remarks).
    - If is_internal=True (Stores export): 11 columns (includes CLIENT PO ITEM NO, SUPPLIER NAME, SUPPLIER PO #).
    - filter_machined_only=True: Exports only items matching Machined/Fabricated/Made from/Modified/Locally remarks.
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "SUMMARY SHEET"
    ws.views.sheetView[0].showGridLines = True

    thin_border = Border(
        left=Side(style='thin', color='000000'),
        right=Side(style='thin', color='000000'),
        top=Side(style='thin', color='000000'),
        bottom=Side(style='thin', color='000000')
    )

    header_font = Font(name='Calibri', size=16, bold=True)
    meta_label_font = Font(name='Calibri', size=11, bold=True)
    table_header_font = Font(name='Calibri', size=10, bold=True)
    data_font = Font(name='Calibri', size=10)

    # Determine column count & headers based on target audience
    if is_internal:
        headers = [
            "SL NO", "CLIENT PO ITEM NO", "Description", "PO Qty", "UOM",
            "Heat Number", "Certificate Number", "MAKE", "Remarks",
            "SUPPLIER NAME", "SUPPLIER PO #"
        ]
        max_col_letter = 'K'
        total_cols = 11
        logo_cell = 'J2'
    else:
        # Client export: strictly 8 columns
        headers = [
            "SL NO", "Description", "PO Qty", "UOM",
            "Heat Number", "Certificate Number", "MAKE", "Remarks"
        ]
        max_col_letter = 'H'
        total_cols = 8
        logo_cell = 'H2'

    # Filter items if filter_machined_only is True
    raw_items = data.get("items", [])
    if filter_machined_only:
        filtered_items = [it for it in raw_items if is_meaningful_item(it)]
        # Fall back to all items if none matched the keyword filter
        items = filtered_items if len(filtered_items) > 0 else raw_items
    else:
        items = raw_items

    # 1. Title Row: SUMMARY SHEET
    ws.merge_cells(f'A1:{max_col_letter}1')
    title_cell = ws['A1']
    title_cell.value = "MSG OILFIELD - STORES SUMMARY SHEET" if is_internal else "MSG OILFIELD - SUMMARY SHEET"
    title_cell.font = header_font
    title_cell.alignment = Alignment(horizontal='center', vertical='center')
    ws.row_dimensions[1].height = 30

    for col in range(1, total_cols + 1):
        ws.cell(row=1, column=col).border = thin_border

    # 2. Metadata Block (Rows 2, 3, 4)
    ws.merge_cells('A2:E2')
    cell_a2 = ws['A2']
    cell_a2.value = f"Client : {data.get('client', '')}"
    cell_a2.font = meta_label_font
    cell_a2.alignment = Alignment(horizontal='left', vertical='center')
    ws.row_dimensions[2].height = 22

    ws.merge_cells('A3:E3')
    cell_a3 = ws['A3']
    cell_a3.value = f"PO Number: {data.get('po_number', '')}"
    cell_a3.font = meta_label_font
    cell_a3.alignment = Alignment(horizontal='left', vertical='center')
    ws.row_dimensions[3].height = 22

    ws.merge_cells('A4:E4')
    cell_a4 = ws['A4']
    cell_a4.value = f"MSG Ref: {data.get('msg_ref', '')}"
    cell_a4.font = meta_label_font
    cell_a4.alignment = Alignment(horizontal='left', vertical='center')
    ws.row_dimensions[4].height = 22

    # Spacer and Logo merged blocks
    if is_internal:
        ws.merge_cells('F2:I4')
        ws.merge_cells('J2:K4')
    else:
        ws.merge_cells('F2:G4')
        ws.merge_cells('H2:H4')

    for r in range(2, 5):
        for c in range(1, total_cols + 1):
            ws.cell(row=r, column=c).border = thin_border

    # Insert Logo
    if not logo_path or not os.path.exists(logo_path):
        logo_path = os.path.join(os.path.dirname(__file__), 'static', 'logo.png')
        if not os.path.exists(logo_path):
            logo_path = os.path.join(os.path.dirname(__file__), 'static', 'msg_logo.png')
    
    if os.path.exists(logo_path):
        try:
            img = Image(logo_path)
            img.width = 135
            img.height = 55
            ws.add_image(img, logo_cell)
        except Exception as e:
            print(f"Error embedding logo: {e}")

    # 3. Table Headers (Row 5)
    ws.row_dimensions[5].height = 24
    header_fill = PatternFill(start_color="F2F2F2", end_color="F2F2F2", fill_type="solid")

    for col_idx, h_text in enumerate(headers, 1):
        c = ws.cell(row=5, column=col_idx)
        c.value = h_text
        c.font = table_header_font
        c.fill = header_fill
        c.border = thin_border
        
        if h_text in ["SL NO", "CLIENT PO ITEM NO", "PO Qty", "UOM", "Heat Number", "Certificate Number", "MAKE", "SUPPLIER NAME", "SUPPLIER PO #"]:
            c.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        else:
            c.alignment = Alignment(horizontal='left', vertical='center', wrap_text=True)

    # 4. Data Rows (Row 6 onwards)
    start_row = 6

    for idx, item in enumerate(items):
        row_idx = start_row + idx
        ws.row_dimensions[row_idx].height = 26

        if is_internal:
            # Internal Stores Layout (11 Cols: SL NO, CLIENT PO ITEM NO, Description, PO Qty...)
            c_sl = ws.cell(row=row_idx, column=1, value=item.get("sl_no", idx + 1))
            c_sl.alignment = Alignment(horizontal='center', vertical='center')

            c_cpo = ws.cell(row=row_idx, column=2, value=item.get("client_po_item_no", item.get("sl_no", idx + 1)))
            c_cpo.alignment = Alignment(horizontal='center', vertical='center')

            c_desc = ws.cell(row=row_idx, column=3, value=item.get("description", ""))
            c_desc.alignment = Alignment(horizontal='left', vertical='center', wrap_text=True)

            raw_qty = item.get("qty", "")
            if isinstance(raw_qty, str) and ("OF" in raw_qty.upper() or "of" in raw_qty):
                val_qty = raw_qty.upper()
            else:
                try:
                    val_qty = float(raw_qty) if raw_qty != "" else ""
                except (ValueError, TypeError):
                    val_qty = raw_qty
            
            c_qty = ws.cell(row=row_idx, column=4, value=val_qty)
            c_qty.alignment = Alignment(horizontal='center', vertical='center')
            if isinstance(val_qty, (int, float)):
                c_qty.number_format = '#,##0.00'

            c_uom = ws.cell(row=row_idx, column=5, value=item.get("uom", ""))
            c_uom.alignment = Alignment(horizontal='center', vertical='center')

            c_heat = ws.cell(row=row_idx, column=6, value=item.get("heat_number", ""))
            c_heat.alignment = Alignment(horizontal='center', vertical='center')

            c_cert = ws.cell(row=row_idx, column=7, value=item.get("certificate_number", ""))
            c_cert.alignment = Alignment(horizontal='center', vertical='center')

            c_make = ws.cell(row=row_idx, column=8, value=item.get("make", ""))
            c_make.alignment = Alignment(horizontal='center', vertical='center')

            c_rem = ws.cell(row=row_idx, column=9, value=item.get("remarks", ""))
            c_rem.alignment = Alignment(horizontal='left', vertical='center', wrap_text=True)

            c_supp = ws.cell(row=row_idx, column=10, value=item.get("supplier_name", ""))
            c_supp.alignment = Alignment(horizontal='center', vertical='center')

            c_spo = ws.cell(row=row_idx, column=11, value=item.get("supplier_po", ""))
            c_spo.alignment = Alignment(horizontal='center', vertical='center')
        else:
            # Client Layout (8 Cols: SL NO, Description, PO Qty...)
            c_sl = ws.cell(row=row_idx, column=1, value=item.get("sl_no", idx + 1))
            c_sl.alignment = Alignment(horizontal='center', vertical='center')

            c_desc = ws.cell(row=row_idx, column=2, value=item.get("description", ""))
            c_desc.alignment = Alignment(horizontal='left', vertical='center', wrap_text=True)

            raw_qty = item.get("qty", "")
            if isinstance(raw_qty, str) and ("OF" in raw_qty.upper() or "of" in raw_qty):
                val_qty = raw_qty.upper()
            else:
                try:
                    val_qty = float(raw_qty) if raw_qty != "" else ""
                except (ValueError, TypeError):
                    val_qty = raw_qty
            
            c_qty = ws.cell(row=row_idx, column=3, value=val_qty)
            c_qty.alignment = Alignment(horizontal='center', vertical='center')
            if isinstance(val_qty, (int, float)):
                c_qty.number_format = '#,##0.00'

            c_uom = ws.cell(row=row_idx, column=4, value=item.get("uom", ""))
            c_uom.alignment = Alignment(horizontal='center', vertical='center')

            c_heat = ws.cell(row=row_idx, column=5, value=item.get("heat_number", ""))
            c_heat.alignment = Alignment(horizontal='center', vertical='center')

            c_cert = ws.cell(row=row_idx, column=6, value=item.get("certificate_number", ""))
            c_cert.alignment = Alignment(horizontal='center', vertical='center')

            c_make = ws.cell(row=row_idx, column=7, value=item.get("make", ""))
            c_make.alignment = Alignment(horizontal='center', vertical='center')

            c_rem = ws.cell(row=row_idx, column=8, value=item.get("remarks", ""))
            c_rem.alignment = Alignment(horizontal='left', vertical='center', wrap_text=True)

        for c_i in range(1, total_cols + 1):
            cell = ws.cell(row=row_idx, column=c_i)
            cell.font = data_font
            cell.border = thin_border

    max_data_row = max(start_row + len(items) - 1, start_row)
    ws.auto_filter.ref = f"A5:{max_col_letter}{max_data_row}"

    if is_internal:
        column_widths = {
            'A': 10,  # SL NO
            'B': 18,  # CLIENT PO ITEM NO
            'C': 85,  # Description (Extended width to the right!)
            'D': 12,  # PO Qty
            'E': 10,  # UOM
            'F': 18,  # Heat Number
            'G': 22,  # Certificate Number
            'H': 16,  # MAKE
            'I': 25,  # Remarks
            'J': 24,  # SUPPLIER NAME
            'K': 18   # SUPPLIER PO #
        }
    else:
        column_widths = {
            'A': 10,  # SL NO
            'B': 85,  # Description (Extended width to the right!)
            'C': 12,  # PO Qty
            'D': 10,  # UOM
            'E': 18,  # Heat Number
            'F': 22,  # Certificate Number
            'G': 16,  # MAKE
            'H': 25   # Remarks
        }

    for col_letter, width in column_widths.items():
        if col_letter <= max_col_letter:
            ws.column_dimensions[col_letter].width = width

    if output_path:
        wb.save(output_path)
        return output_path
    else:
        import io
        stream = io.BytesIO()
        wb.save(stream)
        stream.seek(0)
        return stream
