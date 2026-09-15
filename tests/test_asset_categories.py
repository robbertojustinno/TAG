import secrets
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy import select
import test_stabilization as fixture
from passwords import hash_password

b = fixture.backend

class AssetCategoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(b.app)
        cls.password = secrets.token_urlsafe(24)

    @classmethod
    def tearDownClass(cls):
        cls.client.close()
        b.engine.dispose()

    def setUp(self):
        suffix = secrets.token_hex(5)
        with b.SessionLocal() as db:
            self.company = b.Company(name='Category A', slug='category-a-' + suffix)
            self.other = b.Company(name='Category B', slug='category-b-' + suffix)
            db.add_all([self.company, self.other]); db.flush(); self.company_id=self.company.id; self.other_id=self.other.id
            user = b.User(name='Category admin', email='category-admin-' + suffix + '@example.invalid', password_hash=hash_password(self.password), must_change_password=False)
            viewer = b.User(name='Category viewer', email='category-viewer-' + suffix + '@example.invalid', password_hash=hash_password(self.password), must_change_password=False)
            db.add_all([user, viewer]); db.flush()
            db.add_all([b.UserCompany(user_id=user.id, company_id=self.company.id, role='company_admin'), b.UserCompany(user_id=viewer.id, company_id=self.company.id, role='viewer')])
            db.commit()
            self.admin_headers = {'Authorization': 'Bearer ' + b.auth.issue(user, db.scalar(select(b.UserCompany).where(b.UserCompany.user_id == user.id)))}
            self.viewer_headers = {'Authorization': 'Bearer ' + b.auth.issue(viewer, db.scalar(select(b.UserCompany).where(b.UserCompany.user_id == viewer.id)))}

    def create(self, name, parent_id=None, headers=None):
        payload = {'name': name}
        if parent_id is not None: payload['parent_id'] = parent_id
        response = self.client.post('/asset-categories', headers=headers or self.admin_headers, json=payload)
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def test_create_three_levels_tree_edit_move_and_counts(self):
        root = self.create('Equipamentos')
        pumps = self.create('Bombas', root['id'])
        motors = self.create('Motores', root['id'])
        pressure = self.create('PressÃ£o', pumps['id'])
        tree = self.client.get('/asset-categories/tree', headers=self.viewer_headers)
        self.assertEqual(tree.status_code, 200)
        self.assertEqual(tree.json()[0]['children'][0]['children'][0]['name'], 'PressÃ£o')
        self.assertEqual(self.client.patch(f'/asset-categories/{pressure["id"]}', headers=self.admin_headers, json={'name': 'PressÃ£o alta', 'parent_id': motors['id']}).status_code, 200)
        self.assertEqual(self.client.get('/asset-categories', headers=self.viewer_headers).status_code, 200)
        cycle = self.client.patch(f'/asset-categories/{root["id"]}', headers=self.admin_headers, json={'parent_id': pressure['id']})
        self.assertEqual(cycle.status_code, 409)

    def test_duplicate_delete_rules_and_role_permissions(self):
        root = self.create('Equipamentos')
        self.assertEqual(self.client.post('/asset-categories', headers=self.admin_headers, json={'name': 'Equipamentos'}).status_code, 409)
        child = self.create('Bombas', root['id'])
        self.assertEqual(self.client.delete(f'/asset-categories/{root["id"]}', headers=self.admin_headers).status_code, 409)
        self.assertEqual(self.client.post('/asset-categories', headers=self.viewer_headers, json={'name': 'Nope'}).status_code, 403)
        self.assertEqual(self.client.delete(f'/asset-categories/{child["id"]}', headers=self.admin_headers).status_code, 200)
        self.assertEqual(self.client.delete(f'/asset-categories/{root["id"]}', headers=self.admin_headers).status_code, 200)

    def test_isolation_idor_and_equipment_category_filters(self):
        root = self.create('Equipamentos')
        child = self.create('Bombas', root['id'])
        with b.SessionLocal() as db:
            foreign = b.AssetCategory(company_id=self.other_id, name='Privada', slug='privada')
            db.add(foreign); db.commit(); foreign_id = foreign.id
        visible = self.client.get('/asset-categories', headers=self.viewer_headers)
        self.assertEqual(visible.status_code, 200)
        self.assertNotIn(foreign_id, {row['id'] for row in visible.json()})
        self.assertEqual(self.client.patch(f'/asset-categories/{foreign_id}', headers=self.admin_headers, json={'name': 'Hack'}).status_code, 404)
        self.assertEqual(self.client.delete(f'/asset-categories/{foreign_id}', headers=self.admin_headers).status_code, 404)
        with patch.object(b.cloudinary.uploader, 'upload', return_value={'secure_url': 'https://example.invalid/category.png'}):
            response = self.client.post('/equipment', headers=self.admin_headers, data={'tag': 'CAT-001', 'name': 'Pump', 'category_id': child['id']}, files={'photo': ('p.png', b'png', 'image/png')})
        self.assertEqual(response.status_code, 200, response.text)
        item_id = response.json()['id']
        self.assertEqual(response.json()['category_id'], child['id'])
        self.assertEqual(len(self.client.get('/equipment', headers=self.viewer_headers, params={'category_id': root['id'], 'include_children': 'true'}).json()), 1)
        self.assertEqual(len(self.client.get('/equipment', headers=self.viewer_headers, params={'category_id': child['id']}).json()), 1)
        self.assertEqual(self.client.get('/equipment/tag/CAT-001', headers=self.viewer_headers, params={'category_id': root['id'], 'include_children': 'true'}).status_code, 200)
        self.assertEqual(self.client.get('/equipment/tag/CAT-001', headers=self.viewer_headers, params={'category_id': foreign_id}).status_code, 404)
        self.assertEqual(self.client.get('/equipment', headers=self.viewer_headers, params={'category_id': foreign_id}).status_code, 404)
        update = self.client.put(f'/equipment/{item_id}', headers=self.admin_headers, data={'tag': 'CAT-001', 'name': 'Pump', 'category_id': foreign_id})
        self.assertEqual(update.status_code, 404)

    def test_uncategorized_legacy_equipment_and_existing_routes(self):
        with b.SessionLocal() as db:
            item = b.Equipment(company_id=self.company_id, tag='OLD-CAT', name='Old', photo='https://example.invalid/old.png')
            db.add(item); db.commit(); item_id = item.id
        response = self.client.get('/equipment', headers=self.viewer_headers)
        self.assertEqual(response.status_code, 200)
        row = next(item for item in response.json() if item['id'] == item_id)
        self.assertIsNone(row['category_id'])
        self.assertEqual(self.client.get(f'/equipment/{item_id}/qr-payload', headers=self.viewer_headers).status_code, 200)
        self.assertEqual(self.client.get('/equipment/pdf', headers=self.viewer_headers).status_code, 200)

if __name__ == '__main__':
    unittest.main()



