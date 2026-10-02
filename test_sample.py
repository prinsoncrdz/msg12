import json
from pdf_parser import extract_pdf_data
from excel_generator import generate_summary_excel

sample_ocr_text = """
SALES ORDER
Sales Order# MSG-0926-2127
Bill To
REI OIL & GAS PROCESS SERVICES L.L.C-AED
ARENCO PROPERTIES, OFFICE 110, 111,
DUBAI INVESTMENT PARK, DUBAI, Dubai, United Arab Emirates, 125115
Ref# : U-PO003447

# Item & Description Client PO Item No Qty Rate Amount
1 3/4", SPECTACLE BLIND, 300LB, RF, ASTM A350 Gr.LF2 CL.1, 
ASME B16.48
(LOCALLY MADE FROM A516 GR. 70 PLATE) 
10000 3.00 150.00 450.00
2 LTO156KA350LF2 
THREADOLET 1/2" X 3", 6000#, A350 GR. LF2 CL1, MSS SP-97 
20000 2.00
pcs
945.00 1,890.00
3 LTO156KA350LF2 
THREADOLET 1/2" X 2", 6000#, A350 GR. LF2 CL1, MSS SP-97 
30000 1.00
pcs
945.00 945.00
Sub Total 3,285.00
"""

# Test direct parse function
import tempfile
import os

with tempfile.NamedTemporaryFile('w', delete=False, suffix='.txt') as f:
    f.write(sample_ocr_text)
    tmp_path = f.name

# Test generator directly with sample dictionary
sample_data = {
    "client": "REI Oil & Gas Process Services",
    "po_number": "U-PO003447",
    "msg_ref": "MSG-0926-2127",
    "items": [
        {
            "sl_no": 1,
            "description": '3/4", SPECTACLE BLIND, 300LB, RF, ASTM A350 Gr.LF2 CL.1, ASME B16.48 (LOCALLY MADE FROM A516 GR. 70 PLATE)',
            "qty": "3.00",
            "uom": "",
            "heat_number": "",
            "certificate_number": "",
            "make": "",
            "remarks": ""
        },
        {
            "sl_no": 2,
            "description": 'LTO156KA350LF2 THREADOLET 1/2" X 3", 6000#, A350 GR. LF2 CL1, MSS SP-97',
            "qty": "2.00",
            "uom": "pcs",
            "heat_number": "",
            "certificate_number": "",
            "make": "",
            "remarks": ""
        },
        {
            "sl_no": 3,
            "description": 'LTO156KA350LF2 THREADOLET 1/2" X 2", 6000#, A350 GR. LF2 CL1, MSS SP-97',
            "qty": "1.00",
            "uom": "pcs",
            "heat_number": "",
            "certificate_number": "",
            "make": "",
            "remarks": ""
        }
    ]
}

out_excel = "test_summary_sheet.xlsx"
generate_summary_excel(sample_data, output_path=out_excel)
print("Excel successfully created:", out_excel)
