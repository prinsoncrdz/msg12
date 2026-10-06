import os
from excel_parser import parse_excel_summary
from pdf_generator import generate_loc_pdf
import fitz

def main():
    metadata = {
        'date': '28/09/2026',
        'to_client': 'REI Oil & Gas Process Services',
        'po_number': 'U-PO003447',
        'msg_ref': 'MSG-0926-2127',
        'signatory_name': 'Vijay Dsouza',
        'signatory_title': '( QA / QC Dept )',
        'action_type': 'fabricated'
    }
    
    items = [
        {
            'sl_no': '10000',
            'description': '3/4", SPECTACLE BLIND, 300LB, RF, ASTM A350 Gr.LF2 CL.1, ASME B16.48',
            'po_qty': '3',
            'uom': 'EA',
            'heat_number': 'S83305',
            'remarks': 'MADE FROM PLATE THK. 25MM , ASTM A/SA 516 GR.70'
        }
    ]
    
    out_pdf = 'test_loc.pdf'
    generate_loc_pdf(metadata, items, out_pdf)
    print('Generated PDF successfully:', out_pdf)

    doc = fitz.open(out_pdf)
    pix = doc[0].get_pixmap(dpi=150)
    img_path = 'test_loc_page1.png'
    pix.save(img_path)
    print('Rendered page 1 to:', img_path)

if __name__ == '__main__':
    main()
