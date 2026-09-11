"""Focused Unit endpoint checks, using only a temporary SQLite database."""
import secrets
import unittest
from fastapi.testclient import TestClient
import test_stabilization as fixture
from models import Unit
from passwords import hash_password

b = fixture.backend


class UnitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.password = secrets.token_urlsafe(24)
        cls.encoded = hash_password(cls.password)

    def setUp(self):
        self.client = TestClient(b.app)
        self.addCleanup(self.client.close)
        self.prefix = secrets.token_hex(5)
        self.companies, self.emails = {}, {}
        with b.SessionLocal() as db:
            for key in ('a', 'b'):
                company = b.Company(name=key, slug=self.prefix + '-' + key)
                db.add(company)
                db.flush()
                self.companies[key] = company.id
                user = b.User(name=key, email=f'{key}-{self.prefix}@example.invalid', password_hash=self.encoded)
                db.add(user)
                db.flush()
                db.add(b.UserCompany(user_id=user.id, company_id=company.id, role='company_admin'))
                self.emails[key] = user.email
            reader = b.User(name='reader', email=f'reader-{self.prefix}@example.invalid', password_hash=self.encoded)
            db.add(reader)
            db.flush()
            db.add(b.UserCompany(user_id=reader.id, company_id=self.companies['a'], role='viewer'))
            self.emails['reader'] = reader.email
            db.commit()
        self.headers = {}
        for key, email in self.emails.items():
            response = self.client.post('/auth/login', json={'email': email, 'password': self.password})
            self.assertEqual(response.status_code, 200)
            self.headers[key] = {'Authorization': 'Bearer ' + response.json()['token']}

    def create(self, company='a', slug='head-office'):
        response = self.client.post('/units', headers=self.headers[company], json={'name': 'Head Office', 'slug': slug})
        self.assertEqual(response.status_code, 201)
        return response.json()

    def test_create_unit(self):
        unit = self.create()
        self.assertEqual(unit['company_id'], self.companies['a'])
        self.assertTrue(unit['active'])
        self.assertTrue(unit['created_at'])
        with b.SessionLocal() as db:
            saved = db.get(Unit, unit['id'])
            self.assertEqual(saved.company.id, self.companies['a'])
            self.assertEqual([u.id for u in saved.company.units], [unit['id']])
        payload = {'name': 'Duplicate', 'slug': unit['slug']}
        self.assertEqual(self.client.post('/units', headers=self.headers['a'], json=payload).status_code, 409)
        self.assertEqual(self.client.post('/units', headers=self.headers['reader'], json=payload).status_code, 403)
        self.assertEqual(self.client.post('/units', json=payload).status_code, 401)
        self.assertEqual(self.client.post('/units', headers=self.headers['a'], json={'name': ' ', 'slug': 'blank'}).status_code, 422)
        # Existing global administration grants a membership, then selection sets
        # the session company. Being superadmin alone never supplies a company ID.
        login = self.client.post('/auth/login', json={'username': fixture.ENV['ADMIN_USERNAME'], 'password': fixture.ENV['ADMIN_PASSWORD']}).json()
        admin_headers = {'Authorization': 'Bearer ' + login['token']}
        granted = self.client.post(f'/users/{b.LEGACY_USER_ID}/companies', headers=admin_headers,
                                   json={'company_id': self.companies['b'], 'role': 'viewer'})
        self.assertEqual(granted.status_code, 200)
        with b.SessionLocal() as db:
            email = db.get(b.User, b.LEGACY_USER_ID).email
        selection = self.client.post('/auth/login', json={'email': email, 'password': fixture.ENV['ADMIN_PASSWORD']}).json()
        selected = self.client.post('/auth/select-company', headers={'Authorization': 'Bearer ' + selection['selection_token']},
                                    json={'company_id': self.companies['b']})
        self.assertEqual(selected.status_code, 200)
        token = {'Authorization': 'Bearer ' + selected.json()['token']}
        created = self.client.post('/units', headers=token, json=payload)
        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.json()['company_id'], self.companies['b'])
        self.assertEqual(self.client.post('/auth/select-company', headers=token, json={'company_id': self.companies['a']}).status_code, 403)

    def test_list_units(self):
        self.assertEqual(self.client.get('/units', headers=self.headers['a']).json(), [])
        first = self.create()
        second = self.create(slug='branch')
        rows = self.client.get('/units', headers=self.headers['reader'])
        self.assertEqual(rows.status_code, 200)
        self.assertEqual([row['id'] for row in rows.json()], [first['id'], second['id']])
        self.assertEqual(self.client.get('/units').status_code, 401)

    def test_company_isolation(self):
        items = {key: self.create(key) for key in ('a', 'b')}
        for own, other in [('a', 'b'), ('b', 'a')]:
            with self.subTest(company=own):
                headers = self.headers[own]
                self.assertEqual([u['id'] for u in self.client.get('/units', headers=headers).json()], [items[own]['id']])
                self.assertEqual(self.client.patch(f'/units/{items[other]["id"]}', headers=headers, json={'active': False}).status_code, 404)
                self.assertEqual(self.client.get('/units', headers=headers, params={'company_id': self.companies[other]}).status_code, 403)
                self.assertEqual(self.client.get('/units', headers={**headers, 'X-Company-ID': str(self.companies[other])}).status_code, 403)
                self.assertEqual(self.client.post('/units', headers=headers, json={'name': 'Forged', 'slug': 'forged', 'company_id': self.companies[other]}).status_code, 422)
                self.assertEqual(self.client.patch(f'/units/{items[own]["id"]}', headers=headers,
                                  json={'active': True, 'company_id': self.companies[other]}).status_code, 422)
        with b.SessionLocal() as db:
            for key in ('a', 'b'):
                self.assertTrue(db.get(Unit, items[key]['id']).active)

    def test_activate_deactivate_unit(self):
        unit = self.create()
        path = f'/units/{unit["id"]}'
        for active in (False, True):
            response = self.client.patch(path, headers=self.headers['a'], json={'active': active})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()['active'], active)
            self.assertEqual(self.client.get('/units', headers=self.headers['a']).json()[0]['active'], active)
        self.assertEqual(self.client.patch(path, headers=self.headers['reader'], json={'active': False}).status_code, 403)
        self.assertEqual(self.client.patch(path, json={'active': False}).status_code, 401)


if __name__ == '__main__':
    unittest.main(verbosity=2)
