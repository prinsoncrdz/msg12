import unittest
import io
import openpyxl
from app import app

class SummaryAppTestCase(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    def test_index_route(self):
        response = self.app.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'PDF to Summary Sheet Excel Generator', response.data)

    def test_download_client_excel(self):
        payload = {
            "client": "Dubai Petroleum Establishment",
            "po_number": "50307533",
            "msg_ref": "MSG-1026-2171",
            "is_internal": False,
            "items": [
                {
                    "sl_no": "1",
                    "description": "LUN256KNPTA105N UNION 1\", 6000#",
                    "qty": "3 OF 5",
                    "uom": "pcs",
                    "heat_number": "HN123",
                    "certificate_number": "MTC-001",
                    "make": "WMAASS",
                    "remarks": "Stock item",
                    "supplier_name": "K.HASHIM LLC",
                    "machining_names": ""
                },
                {
                    "sl_no": "1",
                    "description": "LUN256KNPTA105N UNION 1\", 6000#",
                    "qty": "2 OF 5",
                    "uom": "pcs",
                    "heat_number": "HN456",
                    "certificate_number": "MTC-002",
                    "make": "WMAASS",
                    "remarks": "Local market",
                    "supplier_name": "K.HASHIM LLC",
                    "machining_names": ""
                }
            ]
        }
        response = self.app.post('/api/download', json=payload)
        self.assertEqual(response.status_code, 200)
        
        # Verify generated client excel (Strictly 8 columns)
        excel_bytes = io.BytesIO(response.data)
        wb = openpyxl.load_workbook(excel_bytes)
        ws = wb.active
        self.assertEqual(ws['A1'].value, "SUMMARY SHEET")
        self.assertEqual(ws['A5'].value, "SL NO")
        self.assertEqual(ws['H5'].value, "Remarks")
        # Ensure 9th & 10th column headers do NOT exist in client export
        self.assertIsNone(ws['I5'].value)
        self.assertEqual(ws['A6'].value, 1)
        self.assertEqual(ws['C6'].value, "3 OF 5")
        self.assertEqual(ws['C7'].value, "2 OF 5")

    def test_download_internal_stores_excel(self):
        payload = {
            "client": "Dubai Petroleum Establishment",
            "po_number": "50307533",
            "msg_ref": "MSG-1026-2171",
            "is_internal": True,
            "items": [
                {
                    "sl_no": "1",
                    "description": "LUN256KNPTA105N UNION 1\", 6000#",
                    "qty": "3 OF 5",
                    "uom": "pcs",
                    "heat_number": "HN123",
                    "certificate_number": "MTC-001",
                    "make": "WMAASS",
                    "remarks": "Stock item",
                    "supplier_name": "K.HASHIM LLC",
                    "machining_names": "Machined from S.40 to Sch.20"
                }
            ]
        }
        response = self.app.post('/api/download', json=payload)
        self.assertEqual(response.status_code, 200)
        
        excel_bytes = io.BytesIO(response.data)
        wb = openpyxl.load_workbook(excel_bytes)
        ws = wb.active
        self.assertEqual(ws['I5'].value, "SUPPLIER NAME")
        self.assertEqual(ws['J5'].value, "MACHINING NAMES")
        self.assertEqual(ws['I6'].value, "K.HASHIM LLC")
        self.assertEqual(ws['J6'].value, "Machined from S.40 to Sch.20")

if __name__ == '__main__':
    unittest.main()
