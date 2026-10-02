import os
import io
import re
import zipfile
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image

def generate_single_supplier_pdf(supplier_name, supplier_items, header_data, logo_path=None):
    """
    Generates a PDF document for a specific supplier.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(letter),
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    elements = []
    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=18,
        textColor=colors.HexColor('#1e3c72'),
        spaceAfter=6
    )
    
    meta_style = ParagraphStyle(
        'MetaText',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#2c3e50')
    )

    cell_style = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=12
    )

    cell_style_bold = ParagraphStyle(
        'TableCellBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=12
    )

    cell_style_center = ParagraphStyle(
        'TableCellCenter',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=12,
        alignment=1
    )

    header_cell_style = ParagraphStyle(
        'HeaderCell',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=12,
        textColor=colors.white,
        alignment=1
    )

    # 1. Header Block with Logo
    # Get Supplier PO from items if available
    supplier_po = ""
    for it in supplier_items:
        if it.get("supplier_po"):
            supplier_po = it.get("supplier_po")
            break

    header_text = f"""<b>SUPPLIER SUMMARY SHEET</b><br/>
<font size="10" color="#555555">Supplier Purchase Order & Specification Document</font>"""
    
    header_p = Paragraph(header_text, title_style)

    # Logo image
    if not logo_path or not os.path.exists(logo_path):
        logo_path = os.path.join(os.path.dirname(__file__), 'static', 'msg_logo.png')
    
    logo_img = ""
    if os.path.exists(logo_path):
        try:
            logo_img = Image(logo_path, width=130, height=50)
        except Exception:
            logo_img = ""

    header_table_data = [[header_p, logo_img]]
    header_table = Table(header_table_data, colWidths=[550, 150])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN', (1,0), (1,0), 'RIGHT')
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 12))

    # 2. Metadata Box
    meta_info_text = f"""<b>Supplier Name:</b> {supplier_name}<br/>
<b>Supplier PO #:</b> {supplier_po or 'N/A'}<br/>
<b>Client Name:</b> {header_data.get('client', 'N/A')}"""

    meta_info_right = f"""<b>MSG Ref #:</b> {header_data.get('msg_ref', 'N/A')}<br/>
<b>Client PO #:</b> {header_data.get('po_number', 'N/A')}<br/>
<b>Total Items:</b> {len(supplier_items)}"""

    meta_table_data = [[
        Paragraph(meta_info_text, meta_style),
        Paragraph(meta_info_right, meta_style)
    ]]
    meta_table = Table(meta_table_data, colWidths=[360, 340])
    meta_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f4f6f9')),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#dcdfe6')),
        ('PADDING', (0,0), (-1,-1), 8),
        ('VALIGN', (0,0), (-1,-1), 'TOP')
    ]))
    elements.append(meta_table)
    elements.append(Spacer(1, 15))

    # 3. Items Table
    table_headers = [
        "SL NO", "Description", "PO Qty", "UOM",
        "Heat Number", "Certificate #", "MAKE", "Machining / Remarks"
    ]
    
    table_data = [[Paragraph(h, header_cell_style) for h in table_headers]]

    for it in supplier_items:
        desc_text = it.get("description", "").replace("\n", "<br/>")
        rem_text = it.get("remarks", "")
        mach_text = it.get("machining_names", "")
        combined_remarks = f"{mach_text}<br/>{rem_text}" if mach_text and rem_text else (mach_text or rem_text)

        row = [
            Paragraph(str(it.get("sl_no", "")), cell_style_center),
            Paragraph(desc_text, cell_style),
            Paragraph(str(it.get("qty", "")), cell_style_center),
            Paragraph(str(it.get("uom", "")), cell_style_center),
            Paragraph(str(it.get("heat_number", "")), cell_style_center),
            Paragraph(str(it.get("certificate_number", "")), cell_style_center),
            Paragraph(str(it.get("make", "")), cell_style_center),
            Paragraph(combined_remarks, cell_style)
        ]
        table_data.append(row)

    # Column widths (Total landscape width available ~720pt)
    col_widths = [45, 230, 60, 45, 80, 85, 75, 100]
    
    items_table = Table(table_data, colWidths=col_widths, repeatRows=1)
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1e3c72')),
        ('ALIGN', (0,0), (-1,0), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cccccc')),
        ('PADDING', (0,0), (-1,-1), 6),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#f9fafc')])
    ]))

    elements.append(items_table)
    doc.build(elements)
    
    buffer.seek(0)
    return buffer

def generate_all_supplier_pdfs_zip(data, logo_path=None):
    """
    Groups items by supplier and generates a zip archive containing PDF documents for each supplier.
    """
    items = data.get("items", [])
    grouped = {}

    for it in items:
        supp = it.get("supplier_name", "").strip() or "UNASSIGNED_STORES"
        if supp not in grouped:
            grouped[supp] = []
        grouped[supp].append(it)

    zip_buffer = io.BytesIO()
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for supplier_name, supp_items in grouped.items():
            pdf_stream = generate_single_supplier_pdf(supplier_name, supp_items, data, logo_path)
            clean_name = re.sub(r"[^A-Za-z0-9_\-]", "_", supplier_name)
            filename = f"Supplier_PO_{clean_name}.pdf"
            zip_file.writestr(filename, pdf_stream.getvalue())

    zip_buffer.seek(0)
    return zip_buffer
