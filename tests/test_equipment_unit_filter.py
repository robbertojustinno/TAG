"""Focused unit-filter endpoint and Admin request contract checks."""
import secrets
from pathlib import Path
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
import test_stabilization as fixture
from models import Unit
from passwords import hash_password

b = fixture.backend


class EquipmentUnitFilterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.password = secrets.token_urlsafe(24)

    def setUp(self):
        self.client = TestClient(b.app)
        self.addCleanup(self.client.close)
        prefix = secrets.token_hex(5)
        with b.SessionLocal() as db:
            a = b.Company(name='Filter A', slug='filter-a-' + prefix)
            z = b.Company(name='Filter B', slug='filter-b-' + prefix)
            db.add_all([a, z]); db.flush()
            self.company_a, self.company_b = a.id, z.id
            units = [Unit(company_id=a.id, name='Unidade A1', slug='a1-' + prefix),
                     Unit(company_id=a.id, name='Unidade A2', slug='a2-' + prefix),
                     Unit(company_id=z.id, name='Unidade B1', slug='b1-' + prefix)]
            db.add_all(units); db.flush()
            self.unit_a1, self.unit_a2, self.unit_b1 = [u.id for u in units]
            user_a = b.User(name='Filter A', email='filter-a-' + prefix + '@example.invalid', password_hash=hash_password(self.password))
            user_b = b.User(name='Filter B', email='filter-b-' + prefix + '@example.invalid', password_hash=hash_password(self.password))
            db.add_all([user_a, user_b]); db.flush()
            db.add_all([b.UserCompany(user_id=user_a.id, company_id=a.id, role='company_admin'),
                        b.UserCompany(user_id=user_b.id, company_id=z.id, role='company_admin')])
            db.add_all([b.Equipment(company_id=a.id, unit_id=units[0].id, tag='FILTER-A1-' + prefix, name='A1', photo='test'),
                        b.Equipment(company_id=a.id, unit_id=units[1].id, tag='FILTER-A2-' + prefix, name='A2', photo='test'),
                        b.Equipment(company_id=a.id, tag='FILTER-NULL-' + prefix, name='A null', photo='test'),
                        b.Equipment(company_id=z.id, unit_id=units[2].id, tag='FILTER-B1-' + prefix, name='B1', photo='test')])
            db.commit()
            self.email_a, self.email_b = user_a.email, user_b.email
        self.headers_a = self.login(self.email_a)
        self.headers_b = self.login(self.email_b)

    def login(self, email):
        response = self.client.post('/auth/login', json={'email': email, 'password': self.password})
        self.assertEqual(response.status_code, 200)
        return {'Authorization': 'Bearer ' + response.json()['token']}

    def test_list_units_active_company(self):
        response = self.client.get('/units', headers=self.headers_a)
        self.assertEqual(response.status_code, 200)
        self.assertEqual({item['id'] for item in response.json()}, {self.unit_a1, self.unit_a2})
        self.assertNotIn(self.unit_b1, {item['id'] for item in response.json()})

    def test_filter_by_unit_and_all(self):
        response = self.client.get('/equipment', headers=self.headers_a, params={'unit_id': self.unit_a1})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)
        self.assertEqual(response.json()[0]['unit_id'], self.unit_a1)
        all_rows = self.client.get('/equipment', headers=self.headers_a)
        self.assertEqual(all_rows.status_code, 200)
        self.assertEqual({row['unit_id'] for row in all_rows.json()}, {self.unit_a1, self.unit_a2, None})

    def test_unitless_equipment_is_visible_in_all(self):
        rows = self.client.get('/equipment', headers=self.headers_a).json()
        unitless = next(row for row in rows if row['unit_id'] is None)
        self.assertIsNone(unitless['unit_name'])
        filtered = self.client.get('/equipment', headers=self.headers_a, params={'unit_id': self.unit_a1}).json()
        self.assertNotIn(unitless['id'], {row['id'] for row in filtered})

    def test_isolation_between_companies(self):
        self.assertEqual(self.client.get('/units', headers=self.headers_a, params={'company_id': self.company_b}).status_code, 403)
        self.assertEqual(self.client.get('/equipment', headers=self.headers_a, params={'unit_id': self.unit_b1}).status_code, 404)
        self.assertEqual(self.client.get('/units', headers=self.headers_b).json()[0]['id'], self.unit_b1)
        self.assertEqual(self.client.get('/equipment', headers=self.headers_b, params={'unit_id': self.unit_b1}).json()[0]['unit_id'], self.unit_b1)

    def test_admin_filter_request_contract(self):
        source = (Path(__file__).resolve().parents[1] / 'admin' / 'app.js').read_text(encoding='utf-8-sig')
        self.assertIn("'/units'", source)
        self.assertIn("unit_id=${encodeURIComponent(state.selectedUnitId)}", source)
        self.assertIn('Todas as unidades', source)


if __name__ == '__main__':
    unittest.main(verbosity=2)
