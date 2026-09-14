"""First-access policy against an isolated database and real password hashing."""
import secrets
import unittest
from fastapi.testclient import TestClient
from sqlalchemy import select
import test_stabilization as fixture
from passwords import DEMO_EMAILS, hash_password

b = fixture.backend


class FirstAccessTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(b.app)
        self.password = secrets.token_urlsafe(24)
        self.new_password = secrets.token_urlsafe(24)
        self.global_headers = self.headers(self.client.post('/auth/login', json={
            'username': fixture.ENV['ADMIN_USERNAME'], 'password': fixture.ENV['ADMIN_PASSWORD']}).json())
        with b.SessionLocal() as db:
            company = b.Company(name='First access', slug='first-' + secrets.token_hex(6))
            other = b.Company(name='Other', slug='other-' + secrets.token_hex(6))
            db.add_all([company, other]); db.flush()
            self.company, self.other = company.id, other.id
            admin = b.User(name='Local admin', email=secrets.token_hex(6) + '@example.invalid',
                           password_hash=hash_password(self.password))
            db.add(admin); db.flush()
            link = b.UserCompany(user_id=admin.id, company_id=company.id, role='company_admin')
            db.add(link); db.flush()
            self.local_headers = {'Authorization': 'Bearer ' + b.auth.issue(admin, link)}
            db.commit()
        self.user = self.create_user()

    def tearDown(self):
        self.client.close()

    @staticmethod
    def headers(result):
        return {'Authorization': 'Bearer ' + result['token']}

    def create_user(self, global_admin=False):
        data = {'name': 'New real user', 'email': secrets.token_hex(6) + '@example.invalid', 'password': self.password}
        if not global_admin:
            data['role'] = 'operator'
        response = self.client.post('/users' if global_admin else '/company/users', json=data,
                                    headers=self.global_headers if global_admin else self.local_headers)
        self.assertEqual(response.status_code, 201, response.text)
        user = response.json()
        if global_admin:
            response = self.client.post(f'/users/{user["id"]}/companies', headers=self.global_headers,
                                        json={'company_id': self.company, 'role': 'viewer'})
            self.assertEqual(response.status_code, 200, response.text)
        return user

    def login(self, password=None, user=None):
        return self.client.post('/auth/login', json={'email': (user or self.user)['email'],
                                                      'password': password or self.password})

    def change(self, headers=None, **overrides):
        data = {'current_password': self.password, 'new_password': self.new_password,
                'confirm_password': self.new_password}
        data.update(overrides)
        return self.client.post('/auth/change-password', headers=headers or self.headers(self.login().json()), json=data)

    def test_company_created_user_requires_change(self):
        with b.SessionLocal() as db:
            self.assertTrue(db.get(b.User, self.user['id']).must_change_password)
        self.assertTrue(self.login().json()['must_change_password'])

    def test_superadmin_created_user_requires_change(self):
        user = self.create_user(global_admin=True)
        self.assertTrue(user['must_change_password'])
        self.assertTrue(self.login(user=user).json()['must_change_password'])

    def test_restricted_token_cannot_access_normal_endpoints(self):
        result = self.login().json()
        headers = self.headers(result)
        self.assertEqual(b.auth.decode(result['token'], 'password_change')['purpose'], 'password_change')
        self.assertTrue(self.client.get('/auth/me', headers=headers).json()['must_change_password'])
        for path in ['/equipment', '/equipment/pdf', '/units', '/company', '/company/users', '/companies', '/users', '/company/logo']:
            with self.subTest(path=path):
                self.assertIn(self.client.get(path, headers=headers).status_code, (401, 403))
        self.assertIn(self.client.post('/auth/select-company', headers=headers,
                                      json={'company_id': self.company}).status_code, (401, 403))
        self.assertIn(self.client.post('/equipment/pdf-access', headers=headers).status_code, (401, 403))

    def test_database_flag_blocks_even_previously_issued_session_and_selection(self):
        with b.SessionLocal() as db:
            user = db.get(b.User, self.user['id'])
            link = db.scalar(select(b.UserCompany).where(b.UserCompany.user_id == user.id))
            session = {'Authorization': 'Bearer ' + b.auth.issue(user, link)}
            selection = {'Authorization': 'Bearer ' + b.auth.issue(user, purpose='selection')}
        self.assertEqual(self.client.get('/equipment', headers=session).status_code, 403)
        self.assertEqual(self.client.post('/auth/select-company', headers=selection,
                                         json={'company_id': self.company}).status_code, 403)

    def test_wrong_current_password(self):
        self.assertEqual(self.change(current_password='incorrect').status_code, 401)

    def test_short_password(self):
        response = self.change(new_password='too-short', confirm_password='too-short')
        self.assertEqual(response.status_code, 422)
        self.assertNotIn('too-short', response.text)
        self.assertNotIn(self.password, response.text)

    def test_confirmation_mismatch(self):
        self.assertEqual(self.change(confirm_password='different-password').status_code, 422)

    def test_same_password(self):
        self.assertEqual(self.change(new_password=self.password, confirm_password=self.password).status_code, 422)

    def test_change_rotates_credentials_and_all_old_tokens(self):
        old = self.headers(self.login().json())
        second = self.headers(self.login().json())
        response = self.change(headers=old)
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        self.assertFalse(result['must_change_password'])
        self.assertEqual(result['company_id'], self.company)
        self.assertEqual(result['role'], 'operator')
        self.assertNotIn('password_hash', response.text)
        self.assertNotIn(self.new_password, response.text)
        self.assertEqual(response.headers['cache-control'], 'no-store')
        for headers in [old, second]:
            self.assertEqual(self.client.get('/auth/me', headers=headers).status_code, 401)
            self.assertEqual(self.change(headers=headers).status_code, 401)
        self.assertEqual(self.login().status_code, 401)
        self.assertFalse(self.login(self.new_password).json()['must_change_password'])
        self.assertEqual(self.client.get('/equipment', headers=self.headers(result)).status_code, 200)
        with b.SessionLocal() as db:
            self.assertFalse(db.get(b.User, self.user['id']).must_change_password)

    def test_multiple_companies_only_selected_after_change(self):
        with b.SessionLocal() as db:
            db.add(b.UserCompany(user_id=self.user['id'], company_id=self.other, role='viewer')); db.commit()
        self.assertNotIn('companies', self.login().json())
        result = self.change().json()
        self.assertTrue(result['requires_company_selection'])
        self.assertEqual({c['id'] for c in result['companies']}, {self.company, self.other})
        headers = {'Authorization': 'Bearer ' + result['selection_token']}
        selected = self.client.post('/auth/select-company', headers=headers, json={'company_id': self.other}).json()
        self.assertEqual(selected['role'], 'viewer')
        self.assertEqual(selected['company_id'], self.other)
        self.assertEqual(self.client.post('/auth/select-company', headers=headers,
                                         json={'company_id': b.DEFAULT_COMPANY_ID}).status_code, 403)

    def test_own_password_change_revokes_session_selection_and_pdf(self):
        with b.SessionLocal() as db:
            user = db.get(b.User, self.user['id'])
            user.must_change_password = False
            link = db.scalar(select(b.UserCompany).where(b.UserCompany.user_id == user.id))
            session = {'Authorization': 'Bearer ' + b.auth.issue(user, link)}
            selection = {'Authorization': 'Bearer ' + b.auth.issue(user, purpose='selection')}
            pdf = b.auth.issue(user, link, purpose='pdf')
            db.commit()
        response = self.change(headers=session)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.client.get('/auth/me', headers=session).status_code, 401)
        self.assertEqual(self.client.post('/auth/select-company', headers=selection,
                                         json={'company_id': self.company}).status_code, 401)
        self.assertEqual(self.client.post('/equipment/pdf', data={'pdf_token': pdf}).status_code, 401)

    def test_resets_require_change_and_revoke_sessions(self):
        for headers, prefix in [(self.local_headers, '/company/users'), (self.global_headers, '/users')]:
            with self.subTest(prefix=prefix):
                session = self.headers(self.change().json())
                reset = self.client.post(f'{prefix}/{self.user["id"]}/reset-password', headers=headers,
                                         json={'password': self.password})
                self.assertEqual(reset.status_code, 200)
                self.assertEqual(self.client.get('/auth/me', headers=session).status_code, 401)
                self.assertTrue(self.login().json()['must_change_password'])

    def test_demo_existing_accounts_keep_password_and_reset_exception(self):
        for email in DEMO_EMAILS:
            with self.subTest(email=email), b.SessionLocal() as db:
                user = b.User(name='Demo', email=email, password_hash=hash_password(self.password))
                db.add(user); db.flush()
                uid, original = user.id, user.password_hash
                db.add(b.UserCompany(user_id=uid, company_id=self.company, role='viewer')); db.commit()
                demo = {'id': uid, 'email': email}
                self.assertFalse(self.login(user=demo).json()['must_change_password'])
                self.assertEqual(db.get(b.User, uid).password_hash, original)
                for headers, prefix in [(self.local_headers, '/company/users'), (self.global_headers, '/users')]:
                    response = self.client.post(f'{prefix}/{uid}/reset-password', headers=headers,
                                                json={'password': self.password})
                    self.assertEqual(response.status_code, 200)
                    self.assertFalse(self.login(user=demo).json()['must_change_password'])

    def test_no_auth_or_injected_identity(self):
        self.assertEqual(self.client.post('/auth/change-password', json={
            'current_password': self.password, 'new_password': self.new_password,
            'confirm_password': self.new_password}).status_code, 401)
        self.assertEqual(self.change(user_id=b.LEGACY_USER_ID).status_code, 422)
        self.assertEqual(self.change(company_id=self.other).status_code, 422)

    def test_inactive_user_cannot_change(self):
        headers = self.headers(self.login().json())
        with b.SessionLocal() as db:
            db.get(b.User, self.user['id']).active = False; db.commit()
        self.assertEqual(self.change(headers=headers).status_code, 403)


if __name__ == '__main__':
    unittest.main()
