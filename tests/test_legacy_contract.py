import unittest
from unittest.mock import patch
import test_stabilization as fixture
from fastapi.testclient import TestClient

b = fixture.backend

class LegacyContract(unittest.TestCase):
    def test_full_legacy_equipment_flow(self):
        with TestClient(b.app) as client:
            login = client.post('/auth/login', json={'username': fixture.ENV['ADMIN_USERNAME'], 'password': fixture.ENV['ADMIN_PASSWORD']})
            self.assertEqual(login.status_code, 200)
            self.assertEqual(login.json()['username'], fixture.ENV['ADMIN_USERNAME'])
            headers = {'Authorization': 'Bearer ' + login.json()['token']}
            with patch.object(b.cloudinary.uploader, 'upload', return_value={'secure_url': 'https://example.invalid/photo.png'}):
                created = client.post('/equipment', headers=headers, data={'tag':'LEGACY-ROUNDTRIP', 'name':'Original', 'sector':'Setor', 'notes':'Preservar'}, files={'photo':('test.png', b'test', 'image/png')})
            self.assertEqual(created.status_code, 200)
            item = created.json()
            self.assertEqual(item['notes'], 'Preservar')
            self.assertEqual(client.get('/equipment/tag/LEGACY-ROUNDTRIP').json()['id'], item['id'])
            self.assertTrue(any(row['id']==item['id'] for row in client.get('/equipment').json()))
            qr = client.get(f"/equipment/{item['id']}/qr-payload")
            self.assertEqual(qr.status_code, 200)
            self.assertIn('TAG: LEGACY-ROUNDTRIP', qr.json()['qr_payload'])
            pdf = client.get('/equipment/pdf')
            self.assertEqual(pdf.status_code, 200)
            self.assertTrue(pdf.content.startswith(b'%PDF-'))
            self.assertEqual(client.put(f"/equipment/{item['id']}", headers=headers, data={'tag':'LEGACY-ROUNDTRIP', 'name':'Atualizado'}).status_code, 200)
            self.assertEqual(client.get('/equipment/tag/LEGACY-ROUNDTRIP').json()['name'], 'Atualizado')
            self.assertEqual(client.delete(f"/equipment/{item['id']}").status_code, 401)
            self.assertEqual(client.delete(f"/equipment/{item['id']}", headers=headers).status_code, 200)
            self.assertEqual(client.get('/equipment/tag/LEGACY-ROUNDTRIP').status_code, 404)

if __name__ == '__main__':
    try:
        unittest.main(verbosity=2)
    finally:
        b.engine.dispose()
        fixture.TMP.cleanup()
