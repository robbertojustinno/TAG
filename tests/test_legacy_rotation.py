"""Credential reconciliation against an isolated DB; no deployment credentials."""
from pathlib import Path
import secrets
import sys
import tempfile
import unittest

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from admin_api import build_router
from migrate_multiempresa import make_engine, migrate
from models import Company, User, UserCompany
from passwords import hash_password, verify_password
from tenancy import Tenancy


class LegacyRotationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='tagcheck-rotation-')
        self.engine = make_engine('sqlite:///' + (Path(self.tmp.name) / 'test.db').as_posix())
        self.sessions = sessionmaker(bind=self.engine)
        self.username = 'legacy-test'
        self.email = 'legacy@example.invalid'
        self.password = secrets.token_urlsafe(24)
        self.key = secrets.token_hex(32)
        self.result = self.reconcile(self.password)
        self.auth = Tenancy(self.sessions, self.key, self.result['default_company_id'],
                            self.result['legacy_user_id'], self.username, self.password)
        app = FastAPI()
        app.include_router(build_router(self.auth))
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        self.engine.dispose()
        self.tmp.cleanup()

    def reconcile(self, password):
        return migrate(self.engine, self.username, password, self.email)

    def login(self, password):
        return self.client.post('/auth/login', json={'username': self.username, 'password': password})

    def snapshot(self):
        with self.sessions() as db:
            user = db.get(User, self.result['legacy_user_id'])
            links = [(m.id, m.user_id, m.company_id, m.role, m.active)
                     for m in db.scalars(select(UserCompany).order_by(UserCompany.id))]
            return (user.id, user.name, user.email, user.password_hash, user.active,
                    user.is_superadmin, user.created_at, links)

    def test_first_initialization_and_login(self):
        user = self.snapshot()
        self.assertTrue(user[3].startswith('$argon2id$'))
        self.assertTrue(verify_password(user[3], self.password))
        response = self.login(self.password)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['user_id'], user[0])

    def test_unchanged_initialization_is_idempotent(self):
        before = self.snapshot()
        token = self.login(self.password).json()['token']
        self.assertEqual(self.reconcile(self.password), self.result)
        self.assertEqual(self.snapshot(), before)
        with self.sessions() as db:
            self.assertEqual(len(list(db.scalars(select(User)))), 1)
            self.assertEqual(len(list(db.scalars(select(Company)))), 1)
        self.assertEqual(self.client.get('/auth/me', headers={'Authorization': 'Bearer ' + token}).status_code, 200)

    def test_rotation_replaces_only_credential_and_login(self):
        before = self.snapshot()
        new_password = secrets.token_urlsafe(24)
        self.reconcile(new_password)
        self.auth.password = new_password  # new process environment after restart
        after = self.snapshot()
        self.assertNotEqual(before[3], after[3])
        self.assertEqual(before[:3] + before[4:], after[:3] + after[4:])
        self.assertTrue(verify_password(after[3], new_password))
        self.assertFalse(verify_password(after[3], self.password))
        self.assertEqual(self.login(self.password).status_code, 401)
        self.assertEqual(self.login(new_password).status_code, 200)
        self.reconcile(new_password)
        self.assertEqual(self.snapshot(), after)

    def test_old_jwt_rejected_and_new_session_valid(self):
        old = self.login(self.password).json()['token']
        new_password = secrets.token_urlsafe(24)
        self.reconcile(new_password)
        self.auth.password = new_password
        self.assertEqual(self.client.get('/auth/me', headers={'Authorization': 'Bearer ' + old}).status_code, 401)
        new = self.login(new_password).json()['token']
        self.assertEqual(self.client.get('/auth/me', headers={'Authorization': 'Bearer ' + new}).status_code, 200)

    def test_rotation_revokes_pdf_and_selection_credentials(self):
        with self.sessions() as db:
            user = db.get(User, self.result['legacy_user_id'])
            link = db.scalar(select(UserCompany).where(UserCompany.user_id == user.id))
            pdf = self.auth.issue(user, link, purpose='pdf', ttl=120)
            selection = self.auth.issue(user, purpose='selection', ttl=300)
        self.reconcile(secrets.token_urlsafe(24))
        with self.assertRaises(HTTPException) as error:
            self.auth.from_token(pdf, 'pdf')
        self.assertEqual(error.exception.status_code, 401)
        response = self.client.post('/auth/select-company',
                                    headers={'Authorization': 'Bearer ' + selection},
                                    json={'company_id': self.result['default_company_id']})
        self.assertEqual(response.status_code, 401)

    def test_no_secrets_in_responses_or_decoded_jwt(self):
        login = self.login(self.password)
        token = login.json()['token']
        headers = {'Authorization': 'Bearer ' + token}
        payloads = [login.text, str(self.auth.decode(token, 'session')),
                    self.client.get('/auth/me', headers=headers).text,
                    self.client.get('/users', headers=headers).text,
                    self.login(secrets.token_urlsafe(24)).text]
        for payload in payloads:
            for secret in ('password_hash', self.password, self.key, self.snapshot()[3]):
                self.assertFalse(secret in payload, 'Credential material leaked')

    def test_rotation_preserves_disabled_user_and_memberships(self):
        with self.sessions() as db:
            user = db.get(User, self.result['legacy_user_id'])
            user.active = False
            user.is_superadmin = False
            link = db.scalar(select(UserCompany).where(UserCompany.user_id == user.id))
            link.active = False
            link.role = 'viewer'
            db.commit()
        before = self.snapshot()
        new_password = secrets.token_urlsafe(24)
        self.reconcile(new_password)
        after = self.snapshot()
        self.assertEqual(before[:3] + before[4:], after[:3] + after[4:])
        self.assertEqual(self.login(new_password).status_code, 403)

    def test_normal_user_password_change_revokes_session(self):
        with self.sessions() as db:
            user = User(name=self.username, email='normal@example.invalid',
                        password_hash=hash_password(self.password))
            db.add(user)
            db.flush()
            link = UserCompany(user_id=user.id, company_id=self.result['default_company_id'], role='viewer')
            db.add(link)
            db.commit()
            normal_id = user.id
            old_hash = user.password_hash
            token = self.auth.issue(user, link)
        # A matching display name must not redirect legacy reconciliation.
        self.reconcile(secrets.token_urlsafe(24))
        self.assertEqual(self.auth.from_token(token).user_id, normal_id)
        with self.sessions() as db:
            user = db.get(User, normal_id)
            self.assertEqual(user.password_hash, old_hash)
            user.password_hash = hash_password(secrets.token_urlsafe(24))
            db.commit()
        with self.assertRaises(HTTPException) as error:
            self.auth.from_token(token)
        self.assertEqual(error.exception.status_code, 401)


if __name__ == '__main__':
    unittest.main(verbosity=2)
