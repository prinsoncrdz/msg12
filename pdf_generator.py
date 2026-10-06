import os
import io
import base64
import fitz # PyMuPDF
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage, KeepTogether
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas
from PIL import Image as PILImage

class NumberedCanvas(canvas.Canvas):
    """
    Two-pass canvas to draw page numbers and optional fallback decorations
    preserving strict original aspect ratio (NEVER stretched).
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        page_w, page_h = A4

        script_dir = os.path.dirname(os.path.abspath(__file__))
        template_pdf = os.path.join(script_dir, 'assets', 'letterhead_template.pdf')
        
        # If vector template is missing, fallback to drawing un-stretched raster images
        if not os.path.exists(template_pdf):
            header_path = os.path.join(script_dir, 'assets', 'msg_header.png')
            footer_path = os.path.join(script_dir, 'assets', 'msg_footer.png')

            if os.path.exists(header_path):
                try:
                    # PRESERVE ASPECT RATIO STRICTLY
                    self.drawImage(
                        header_path,
                        x=10 * mm,
                        y=page_h - 38 * mm,
                        width=page_w - 20 * mm,
                        height=30 * mm,
                        preserveAspectRatio=True,
                        mask='auto'
                    )
                except Exception as e:
                    print("Header draw warning:", e)

            if os.path.exists(footer_path):
                try:
                    self.drawImage(
                        footer_path,
                        x=10 * mm,
                        y=6 * mm,
                        width=page_w - 20 * mm,
                        height=20 * mm,
                        preserveAspectRatio=True,
                        mask='auto'
                    )
                except Exception as e:
                    print("Footer draw warning:", e)

        # Page Number (bottom right) if multi-page
        if page_count > 1:
            self.setFont("Helvetica", 7.5)
            self.setFillColor(colors.HexColor("#666666"))
            self.drawRightString(page_w - 14 * mm, 5 * mm, f"Page {self._pageNumber} of {page_count}")

        self.restoreState()


def get_image_dimensions(img_source, max_w, max_h):
    """Calculate proportional dimensions for ReportLab RLImage from file path or BytesIO."""
    try:
        if isinstance(img_source, str):
            im = PILImage.open(img_source)
        else:
            im = PILImage.open(img_source)
            img_source.seek(0)
            
        w, h = im.size
        aspect = w / float(h)
        target_w = max_w
        target_h = max_w / aspect
        if target_h > max_h:
            target_h = max_h
            target_w = max_h * aspect
        return target_w, target_h
    except Exception as e:
        print("Image dimension check error:", e)
        return max_w, max_h


def parse_image_data(img_data_str_or_bytes):
    """Parses base64 data URL or path into a BytesIO or path for ReportLab."""
    if not img_data_str_or_bytes:
        return None
    if isinstance(img_data_str_or_bytes, str) and img_data_str_or_bytes.startswith('data:image'):
        try:
            header, base64_str = img_data_str_or_bytes.split(',', 1)
            img_bytes = base64.b64decode(base64_str)
            return io.BytesIO(img_bytes)
        except Exception as e:
            print("Failed to decode base64 image:", e)
            return None
    return img_data_str_or_bytes


def remove_white_background(img_src, threshold=210):
    """
    Automatically detects and converts white/light background pixels to transparent alpha channels
    so that seal stamps and signatures overlay cleanly onto PDFs with zero white box backgrounds.
    """
    if not img_src:
        return None

    try:
        if isinstance(img_src, str):
            if not os.path.exists(img_src):
                return img_src
            im = PILImage.open(img_src)
        elif hasattr(img_src, 'seek'):
            img_src.seek(0)
            im = PILImage.open(img_src)
        else:
            im = PILImage.open(img_src)

        im = im.convert("RGBA")

        try:
            import numpy as np
            arr = np.array(im)
            r, g, b, a = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2], arr[:, :, 3]
            light_mask = (r > threshold) & (g > threshold) & (b > threshold)
            arr[:, :, 3][light_mask] = 0
            clean_im = PILImage.fromarray(arr, mode="RGBA")
        except Exception:
            pixels = im.load()
            w, h = im.size
            for x in range(w):
                for y in range(h):
                    r, g, b, a = pixels[x, y]
                    if r > threshold and g > threshold and b > threshold:
                        pixels[x, y] = (255, 255, 255, 0)
            clean_im = im

        out = io.BytesIO()
        clean_im.save(out, format="PNG")
        out.seek(0)
        return out
    except Exception as e:
        print("Automatic background removal notice:", e)
        if hasattr(img_src, 'seek'):
            img_src.seek(0)
        return img_src


def create_signature_seal_composite(stamp_src, sig_src, metadata=None):
    """
    Creates a combined Flowable PNG image containing both QA/QC Seal and Signature.
    Allows Seal & Signature to overlap naturally right above 'Vijay Dsouza'
    with customizable size scale & position offsets (Adobe-style movable placement).
    """
    metadata = metadata or {}

    try:
        stamp_scale = float(metadata.get('stamp_scale', 0.28))
    except (ValueError, TypeError):
        stamp_scale = 0.28

    try:
        sig_scale = float(metadata.get('sig_scale', 0.25))
    except (ValueError, TypeError):
        sig_scale = 0.25

    try:
        stamp_x = int(metadata.get('stamp_x', 0))
        stamp_y = int(metadata.get('stamp_y', 0))
        sig_x = int(metadata.get('sig_x', 20)) # Overlaps directly above Vijay Dsouza on the left
        sig_y = int(metadata.get('sig_y', 10))
    except (ValueError, TypeError):
        stamp_x, stamp_y, sig_x, sig_y = 0, 0, 20, 10

    st_w, st_h = 0, 0
    sg_w, sg_h = 0, 0

    im_stamp = None
    if stamp_src:
        try:
            if isinstance(stamp_src, str):
                im_stamp = PILImage.open(stamp_src)
            elif hasattr(stamp_src, 'seek'):
                stamp_src.seek(0)
                im_stamp = PILImage.open(stamp_src)
            else:
                im_stamp = PILImage.open(stamp_src)

            im_stamp = im_stamp.convert("RGBA")
            st_w = max(10, int(im_stamp.width * stamp_scale))
            st_h = max(10, int(im_stamp.height * stamp_scale))
            im_stamp = im_stamp.resize((st_w, st_h), PILImage.Resampling.LANCZOS)
        except Exception as e:
            print("Stamp composite loading error:", e)

    im_sig = None
    if sig_src:
        try:
            if isinstance(sig_src, str):
                im_sig = PILImage.open(sig_src)
            elif hasattr(sig_src, 'seek'):
                sig_src.seek(0)
                im_sig = PILImage.open(sig_src)
            else:
                im_sig = PILImage.open(sig_src)

            im_sig = im_sig.convert("RGBA")
            sg_w = max(10, int(im_sig.width * sig_scale))
            sg_h = max(10, int(im_sig.height * sig_scale))
            im_sig = im_sig.resize((sg_w, sg_h), PILImage.Resampling.LANCZOS)
        except Exception as e:
            print("Signature composite loading error:", e)

    max_w = max(stamp_x + st_w, sig_x + sg_w, 30) + 4
    max_h = max(stamp_y + st_h, sig_y + sg_h, 30) + 4

    canvas = PILImage.new("RGBA", (max_w, max_h), (255, 255, 255, 0))

    if im_stamp:
        canvas.paste(im_stamp, (max(0, stamp_x), max(0, stamp_y)), im_stamp)

    if im_sig:
        canvas.paste(im_sig, (max(0, sig_x), max(0, sig_y)), im_sig)

    out = io.BytesIO()
    canvas.save(out, format="PNG")
    out.seek(0)
    
    return out, max_w * 0.65, max_h * 0.65


def build_compliance_wording(action_type):
    """
    Builds dynamic verb and noun combinations for the compliance statement.
    """
    action_str = str(action_type or 'fabricated').lower()

    verbs = []
    nouns = []

    if 'fabricat' in action_str or 'make' in action_str or 'plate' in action_str:
        verbs.append('fabricated')
        nouns.append('fabrication')
    if 'machin' in action_str or 'mac' in action_str or 'thread' in action_str:
        verbs.append('machined')
        nouns.append('machining')
    if 'modif' in action_str or 'mod' in action_str:
        verbs.append('modified')
        nouns.append('modification')

    if not verbs:
        verbs = ['fabricated']
        nouns = ['fabrication']

    verb_text = " / ".join(verbs)
    noun_text = " / ".join(nouns)

    return verb_text, noun_text


def apply_vector_letterhead_overlay(raw_pdf_bytes_or_path, output_target):
    """
    Overlays the original vector MSG letterhead PDF template onto every page
    of the generated document. Guarantees 100% crisp, professional, un-stretched letterhead.
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    template_pdf_path = os.path.join(script_dir, 'assets', 'letterhead_template.pdf')

    if not os.path.exists(template_pdf_path):
        # If template missing, write raw PDF as is
        if isinstance(output_target, str):
            with open(output_target, 'wb') as f:
                f.write(raw_pdf_bytes_or_path if isinstance(raw_pdf_bytes_or_path, bytes) else raw_pdf_bytes_or_path.getvalue())
        elif hasattr(output_target, 'write'):
            output_target.write(raw_pdf_bytes_or_path if isinstance(raw_pdf_bytes_or_path, bytes) else raw_pdf_bytes_or_path.getvalue())
        return

    # Load vector template and generated content
    doc_template = fitz.open(template_pdf_path)
    
    if isinstance(raw_pdf_bytes_or_path, bytes):
        doc_content = fitz.open(stream=raw_pdf_bytes_or_path, filetype="pdf")
    elif isinstance(raw_pdf_bytes_or_path, str):
        doc_content = fitz.open(raw_pdf_bytes_or_path)
    else:
        doc_content = fitz.open(stream=raw_pdf_bytes_or_path.getvalue(), filetype="pdf")

    final_doc = fitz.open()

    for page_idx in range(len(doc_content)):
        page_rect = fitz.Rect(0, 0, 595.27, 841.89) # A4 size in points
        new_page = final_doc.new_page(width=595.27, height=841.89)
        
        # 1. Overlay original vector letterhead graphics
        new_page.show_pdf_page(page_rect, doc_template, 0)
        
        # 2. Overlay document text content
        new_page.show_pdf_page(page_rect, doc_content, page_idx)

    # Save to output_target
    if isinstance(output_target, str):
        final_doc.save(output_target)
    elif hasattr(output_target, 'write'):
        final_bytes = final_doc.write()
        output_target.write(final_bytes)


def generate_loc_pdf(metadata, items, output_target, signature_data=None, stamp_data=None, include_signature=True, include_stamp=True):
    """
    Generates a Letter of Compliance (LOC) PDF based on exact MSG specifications.
    Uses vector letterhead overlay for 100% professional un-stretched output.
    """
    content_buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        content_buffer,
        pagesize=A4,
        leftMargin=14 * mm,
        rightMargin=14 * mm,
        topMargin=44 * mm,
        bottomMargin=30 * mm
    )

    page_w, _ = A4
    printable_w = page_w - (28 * mm) # ~515.8 pt

    styles = getSampleStyleSheet()

    # Typography styles
    hdr_label_style = ParagraphStyle(
        'HdrLabel',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#000000')
    )

    title_style = ParagraphStyle(
        'LocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=16,
        textColor=colors.HexColor('#000000'),
        alignment=1
    )

    body_style = ParagraphStyle(
        'LocBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=14,
        textColor=colors.HexColor('#1A1A1A')
    )

    tbl_hdr_style = ParagraphStyle(
        'TblHdr',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=11,
        textColor=colors.HexColor('#000000'),
        alignment=1
    )

    tbl_cell_center = ParagraphStyle(
        'TblCellCenter',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor('#000000'),
        alignment=1
    )

    tbl_cell_left = ParagraphStyle(
        'TblCellLeft',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor('#000000'),
        alignment=0
    )

    sig_company_style = ParagraphStyle(
        'SigCompany',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#000000')
    )

    sig_name_style = ParagraphStyle(
        'SigName',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=13,
        textColor=colors.HexColor('#000000')
    )

    sig_title_style = ParagraphStyle(
        'SigTitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=13,
        textColor=colors.HexColor('#333333')
    )

    elements = []

    # 1. Header Metadata Section
    date_val = metadata.get('date', '')
    to_val = metadata.get('to_client', '')
    po_val = metadata.get('po_number', '')
    ref_val = metadata.get('msg_ref', '')

    hdr_text = (
        f"<b>Date:</b> {date_val}<br/>"
        f"<b>TO:</b> {to_val}<br/>"
        f"<b>PO Number:</b> {po_val}<br/>"
        f"<b>MSG Ref:</b> {ref_val}"
    )

    hdr_p = Paragraph(hdr_text, hdr_label_style)
    elements.append(hdr_p)
    elements.append(Spacer(1, 14))

    # 2. Document Title
    title_p = Paragraph("<u><b>LETTER OF COMPLIANCE</b></u>", title_style)
    elements.append(title_p)
    elements.append(Spacer(1, 14))

    # 3. Dynamic Action Compliance Declaration
    action_type = metadata.get('action_type', 'fabricated')
    verb_text, noun_text = build_compliance_wording(action_type)

    statement_text = (
        f"We hereby confirm that below listed items have been <b>{verb_text}</b> as per the client PO requirements. "
        f"Subsequent to the <b>{noun_text}</b>, dimensional verification and visual inspection were conducted, "
        f"and the items are found to be acceptable and in full compliance with the applicable standards."
    )
    elements.append(Paragraph(statement_text, body_style))
    elements.append(Spacer(1, 14))

    # 4. Table Construction
    col_w = [40, 210, 40, 35, 60, printable_w - (40 + 210 + 40 + 35 + 60)]

    table_data = [
        [
            Paragraph("<b>Sl.No</b>", tbl_hdr_style),
            Paragraph("<b>Description</b>", tbl_hdr_style),
            Paragraph("<b>PO Qty</b>", tbl_hdr_style),
            Paragraph("<b>UOM</b>", tbl_hdr_style),
            Paragraph("<b>Heat Number</b>", tbl_hdr_style),
            Paragraph("<b>Remarks</b>", tbl_hdr_style)
        ]
    ]

    for item in items:
        table_data.append([
            Paragraph(str(item.get('sl_no', '')), tbl_cell_center),
            Paragraph(str(item.get('description', '')), tbl_cell_left),
            Paragraph(str(item.get('po_qty', '')), tbl_cell_center),
            Paragraph(str(item.get('uom', '')), tbl_cell_center),
            Paragraph(str(item.get('heat_number', '')), tbl_cell_center),
            Paragraph(str(item.get('remarks', '')), tbl_cell_left)
        ])

    items_table = Table(table_data, colWidths=col_w, repeatRows=1)
    items_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('GRID', (0,0), (-1,-1), 0.75, colors.HexColor('#000000')),
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#FFFFFF')),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('LEFTPADDING', (0,0), (-1,-1), 4),
        ('RIGHTPADDING', (0,0), (-1,-1), 4),
    ]))

    elements.append(items_table)
    elements.append(Spacer(1, 24))

    # 5. Signature Section
    script_dir = os.path.dirname(os.path.abspath(__file__))
    default_sig_path = os.path.join(script_dir, 'assets', 'signature.png')
    default_stamp_path = os.path.join(script_dir, 'assets', 'stamp.png')

    sig_src = None
    if include_signature:
        sig_raw = parse_image_data(signature_data) or (default_sig_path if os.path.exists(default_sig_path) else None)
        if sig_raw:
            sig_src = remove_white_background(sig_raw, threshold=210)

    stamp_src = None
    if include_stamp:
        stamp_raw = parse_image_data(stamp_data) or (default_stamp_path if os.path.exists(default_stamp_path) else None)
        if stamp_raw:
            stamp_src = remove_white_background(stamp_raw, threshold=210)

    sig_elements = []
    sig_elements.append(Paragraph("<b>For MSG Oilfield Equipment Trading,</b>", sig_company_style))
    sig_elements.append(Spacer(1, 6))

    if sig_src or stamp_src:
        composite_buf, comp_w, comp_h = create_signature_seal_composite(stamp_src, sig_src, metadata)
        img_obj = RLImage(composite_buf, width=comp_w, height=comp_h)
        img_obj.hAlign = 'LEFT'
        sig_elements.append(img_obj)
        sig_elements.append(Spacer(1, 2))
    else:
        sig_elements.append(Spacer(1, 35))

    sig_name = metadata.get('signatory_name', 'Vijay Dsouza')
    sig_title = metadata.get('signatory_title', '( QA / QC Dept )')

    sig_elements.append(Paragraph(f"<b>{sig_name}</b>", sig_name_style))
    sig_elements.append(Spacer(1, 2))
    sig_elements.append(Paragraph(sig_title, sig_title_style))

    elements.append(KeepTogether(sig_elements))

    # Build intermediate ReportLab content PDF
    doc.build(elements, canvasmaker=NumberedCanvas)

    # Overlay vector letterhead onto generated content
    content_buffer.seek(0)
    apply_vector_letterhead_overlay(content_buffer, output_target)
    return True
