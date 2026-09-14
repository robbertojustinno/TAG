import secrets
import unittest
from fastapi.testclient import TestClient
from sqlalchemy import select
import test_stabilization as fixture
from passwords import hash_password

b = fixture.backend


class SuperadminManagementApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(b.app)
        result = cls.client.post('/auth/login', json={'username': fixture.ENV['ADMIN_USERNAME'], 'password': fixture.ENV['ADMIN_PASSWORD']})
        cls.headers = {'Authorization': 'Bearer ' + result.json()['token']}

    def setUp(self):
        self.password = secrets.token_urlsafe(18)
        with b.SessionLocal() as db:
            self.company = b.Company(name='Managed API', slug='managed-api-' + secrets.token_hex(4))
            db.add(self.company); db.flush()
            self.company_id = self.company.id
            self.user = b.User(name='Managed User', email='managed-api-' + secrets.token_hex(4) + '@example.invalid', password_hash=hash_password(self.password))
            db.add(self.user); db.flush()
            self.user_id, self.email = self.user.id, self.user.email
            db.add(b.UserCompany(user_id=self.user.id, company_id=self.company.id, role='viewer'))
            db.commit()

    @classmethod
    def tearDownClass(cls):
        cls.client.close()

    def test_company_update_and_safe_rules(self):
        response = self.client.patch('/companies/' + str(self.company_id), headers=self.headers,
                                     json={'name': '  Updated API  ', 'slug': 'updated-api-' + secrets.token_hex(3)})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['name'], 'Updated API')
        self.assertNotIn('password', response.text)
        duplicate = self.client.patch('/companies/' + str(b.DEFAULT_COMPANY_ID), headers=self.headers,
                                      json={'slug': response.json()['slug']})
        self.assertEqual(duplicate.status_code, 409)
        current = self.client.patch('/companies/' + str(b.DEFAULT_COMPANY_ID), headers=self.headers, json={'active': False})
        self.assertEqual(current.status_code, 409)
        extra = self.client.patch('/companies/' + str(self.company_id), headers=self.headers, json={'name': 'x', 'unknown': 1})
        self.assertEqual(extra.status_code, 422)

    def test_user_update_email_and_self_protection(self):
        old = self.client.post('/auth/login', json={'email': self.email, 'password': self.password})
        self.assertEqual(old.status_code, 200)
        old_headers = {'Authorization': 'Bearer ' + old.json()['token']}
        new_email = 'updated-' + secrets.token_hex(4) + '@example.invalid'
        updated = self.client.patch('/users/' + str(self.user_id), headers=self.headers,
                                    json={'name': ' Updated User ', 'email': '  ' + new_email.upper() + '  '})
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json()['name'], 'Updated User')
        self.assertEqual(updated.json()['email'], new_email)
        self.assertEqual(self.client.get('/auth/me', headers=old_headers).status_code, 401)
        duplicate = self.client.patch('/users/' + str(b.LEGACY_USER_ID), headers=self.headers,
                                      json={'email': new_email})
        self.assertEqual(duplicate.status_code, 409)
        self.assertEqual(self.client.patch('/users/' + str(b.LEGACY_USER_ID), headers=self.headers, json={'active': False}).status_code, 409)
        self.assertEqual(self.client.patch('/users/' + str(self.user_id), headers=self.headers, json={'unknown': 1}).status_code, 422)

    def test_reset_password_invalidates_old_session(self):
        old = self.client.post('/auth/login', json={'email': self.email, 'password': self.password})
        self.assertEqual(old.status_code, 200)
        old_headers = {'Authorization': 'Bearer ' + old.json()['token']}
        new_password = secrets.token_urlsafe(18)
        result = self.client.post('/users/' + str(self.user_id) + '/reset-password', headers=self.headers,
                                  json={'password': new_password})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json(), {'ok': True})
        self.assertEqual(self.client.get('/auth/me', headers=old_headers).status_code, 401)
        self.assertEqual(self.client.post('/auth/login', json={'email': self.email, 'password': self.password}).status_code, 401)
        self.assertEqual(self.client.post('/auth/login', json={'email': self.email, 'password': new_password}).status_code, 200)
        self.assertEqual(self.client.post('/users/' + str(self.user_id) + '/reset-password', headers=old_headers,
                                          json={'password': new_password}).status_code, 401)
        self.assertEqual(self.client.post('/users/' + str(self.user_id) + '/reset-password', headers=self.headers,
                                          json={'password': 'short'}).status_code, 422)

    def test_non_superadmin_cannot_manage(self):
        login = self.client.post('/auth/login', json={'email': self.email, 'password': self.password})
        headers = {'Authorization': 'Bearer ' + login.json()['token']}
        self.assertEqual(self.client.patch('/companies/' + str(self.company_id), headers=headers, json={'name': 'x'}).status_code, 403)
        self.assertEqual(self.client.patch('/users/' + str(self.user_id), headers=headers, json={'name': 'x'}).status_code, 403)
        self.assertEqual(self.client.post('/users/' + str(self.user_id) + '/reset-password', headers=headers,
                                          json={'password': secrets.token_urlsafe(18)}).status_code, 403)


if __name__ == '__main__':
    unittest.main(verbosity=2)
