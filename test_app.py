import unittest
import json
from app import app, DEFAULT_USER_EMAIL, STRONG_PASSWORD

class AppTestCase(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    def test_login_flow(self):
        # 1. Accessing index unauthenticated redirects to /login
        response = self.app.get('/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login', response.location)

        # 2. Login with valid credentials
        login_res = self.app.post('/api/login', data=json.dumps({
            'email': DEFAULT_USER_EMAIL,
            'password': STRONG_PASSWORD
        }), content_type='application/json')
        self.assertEqual(login_res.status_code, 200)
        self.assertTrue(json.loads(login_res.data)['success'])

        # 3. Access index authenticated
        index_res = self.app.get('/')
        self.assertEqual(index_res.status_code, 200)
        self.assertIn(b'LETTER OF COMPLIANCE GENERATOR', index_res.data)

    def test_preview_pdf(self):
        # Log in first
        self.app.post('/api/login', data=json.dumps({
            'email': DEFAULT_USER_EMAIL,
            'password': STRONG_PASSWORD
        }), content_type='application/json')

        payload = {
            'metadata': {
                'date': '28/09/2026',
                'to_client': 'Test Client',
                'po_number': 'PO-12345',
                'msg_ref': 'MSG-REF-001',
                'signatory_name': 'Vijay Dsouza',
                'signatory_title': '( QA / QC Dept )',
                'action_type': 'fabricated'
            },
            'items': [
                {
                    'sl_no': '1',
                    'description': 'Test Valve SS316',
                    'po_qty': '10',
                    'uom': 'EA',
                    'heat_number': 'HT-100',
                    'remarks': 'MADE FROM PLATE THK. 25MM'
                }
            ]
        }
        response = self.app.post('/api/preview-pdf', data=json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertIn('page_images', data)

    def test_backups_flow(self):
        # Log in first
        self.app.post('/api/login', data=json.dumps({
            'email': DEFAULT_USER_EMAIL,
            'password': STRONG_PASSWORD
        }), content_type='application/json')

        # 1. Check backup status
        status_res = self.app.get('/api/backups/status')
        self.assertEqual(status_res.status_code, 200)
        self.assertTrue(json.loads(status_res.data)['success'])

        # 2. Save backup
        payload = {
            'metadata': {
                'date': '05/10/2026',
                'to_client': 'Cloud Backup Test Client',
                'po_number': 'U-PO-CLOUD-999',
                'msg_ref': 'MSG-REF-CLOUD',
                'signatory_name': 'Vijay Dsouza',
                'signatory_title': '( QA / QC Dept )',
                'action_type': 'fabricated / machined'
            },
            'items': [
                {
                    'sl_no': '1',
                    'description': 'Cloud Backup Spec Flange',
                    'po_qty': '5',
                    'uom': 'PCS',
                    'heat_number': 'HT-CLOUD-01',
                    'remarks': 'MADE FROM FORGING'
                }
            ]
        }
        save_res = self.app.post('/api/backups/save', data=json.dumps(payload), content_type='application/json')
        self.assertEqual(save_res.status_code, 200)
        save_data = json.loads(save_res.data)
        self.assertTrue(save_data['success'])
        backup_id = save_data['backup_id']

        # 3. Search backup
        search_res = self.app.get('/api/backups/search?query=CLOUD-999')
        self.assertEqual(search_res.status_code, 200)
        search_data = json.loads(search_res.data)
        self.assertTrue(search_data['success'])
        self.assertGreaterEqual(search_data['count'], 1)

        # 4. Restore backup
        restore_res = self.app.get(f'/api/backups/restore/{backup_id}')
        self.assertEqual(restore_res.status_code, 200)
        restore_data = json.loads(restore_res.data)
        self.assertTrue(restore_data['success'])
        self.assertEqual(restore_data['data']['po_number'], 'U-PO-CLOUD-999')

        # 5. Delete backup
        del_res = self.app.delete(f'/api/backups/delete/{backup_id}')
        self.assertEqual(del_res.status_code, 200)
        self.assertTrue(json.loads(del_res.data)['success'])

if __name__ == '__main__':
    unittest.main()
