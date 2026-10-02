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
        self.assertIn("GERAB NATIONAL ENTERPRISES LLC", data['suppliers'])

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
                    "supplier_po": "PO-1026-3789",
                    "machining_names": ""
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
        self.assertEqual(ws['H5'].value, "Remarks")
        self.assertIsNone(ws['I5'].value)

    def test_export_supplier_pdfs_zip(self):
        payload = {
            "client": "Dubai Petroleum Establishment",
            "po_number": "50307533",
            "msg_ref": "MSG-1026-2171",
            "items": [
                {
                    "sl_no": "1",
                    "description": "UNION 1\", 6000#",
                    "qty": "12.00",
                    "uom": "pcs",
                    "heat_number": "HN999",
                    "certificate_number": "CERT-111",
                    "make": "WMAASS",
                    "remarks": "Urgent",
                    "supplier_name": "K.HASHIM LLC",
                    "supplier_po": "PO-1026-3789",
                    "machining_names": ""
                },
                {
                    "sl_no": "2",
                    "description": "ELBOW 1\", 90DEG",
                    "qty": "15.00",
                    "uom": "pcs",
                    "heat_number": "HN888",
                    "certificate_number": "CERT-222",
                    "make": "DELCORTE",
                    "remarks": "Stock",
                    "supplier_name": "DELCORTE SAS",
                    "supplier_po": "PO-1026-3790",
                    "machining_names": "Machined from S.40"
                }
            ]
        }
        response = self.app.post('/api/export-supplier-pdfs', json=payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, 'application/zip')

        # Verify ZIP contains 2 PDF files
        zip_bytes = io.BytesIO(response.data)
        with zipfile.ZipFile(zip_bytes, 'r') as zip_file:
            filenames = zip_file.namelist()
            self.assertEqual(len(filenames), 2)
            self.assertTrue(any('K_HASHIM' in name for name in filenames))
            self.assertTrue(any('DELCORTE' in name for name in filenames))

if __name__ == '__main__':
    unittest.main()
