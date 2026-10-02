import unittest
import io
import zipfile
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

    def test_suppliers_api(self):
        response = self.app.get('/api/suppliers')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data['success'])
        self.assertIn("K.HASHIM LLC", data['suppliers'])

    def test_download_internal_stores_excel(self):
        payload = {
            "client": "Dubai Petroleum Establishment",
            "po_number": "50307533",
            "msg_ref": "MSG-1026-2171",
            "is_internal": True,
            "filter_machined_only": True,
            "items": [
                {
                    "sl_no": "1",
                    "client_po_item_no": "10000",
                    "description": "UNION 1\", 6000#",
                    "qty": "3 OF 5",
                    "uom": "pcs",
                    "heat_number": "HN123",
                    "certificate_number": "MTC-001",
                    "make": "WMAASS",
                    "remarks": "Machined from S.40 to Sch.20",
                    "supplier_name": "K.HASHIM LLC",
                    "supplier_po": "PO-1026-3789"
                }
            ]
        }
        response = self.app.post('/api/download', json=payload)
        self.assertEqual(response.status_code, 200)
        
        excel_bytes = io.BytesIO(response.data)
        wb = openpyxl.load_workbook(excel_bytes)
        ws = wb.active
        self.assertEqual(ws['A1'].value, "SUMMARY SHEET")
        self.assertEqual(ws['A5'].value, "SL NO")
        self.assertEqual(ws['B5'].value, "CLIENT PO ITEM NO")
        self.assertEqual(ws['C5'].value, "Description")
        self.assertEqual(ws['B6'].value, "10000")

    def test_export_supplier_pdfs_zip(self):
        payload = {
            "client": "Dubai Petroleum Establishment",
            "po_number": "50307533",
            "msg_ref": "MSG-1026-2171",
            "items": [
                {
                    "sl_no": "1",
                    "client_po_item_no": "10000",
                    "description": "UNION 1\", 6000#",
                    "qty": "12.00",
                    "uom": "pcs",
                    "heat_number": "HN999",
                    "certificate_number": "CERT-111",
                    "make": "WMAASS",
                    "remarks": "Locally made from plate",
                    "supplier_name": "K.HASHIM LLC",
                    "supplier_po": "PO-1026-3789"
                }
            ]
        }
        response = self.app.post('/api/export-supplier-pdfs', json=payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, 'application/zip')

if __name__ == '__main__':
    unittest.main()
