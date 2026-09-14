"""Focused admin login UI integration against a temporary multi-company backend."""
import os
from pathlib import Path
import re
import secrets
import socket
import threading
import time
import unittest

import test_stabilization as fixture
from fastapi.staticfiles import StaticFiles
from passwords import hash_password
from playwright.sync_api import expect, sync_playwright
import uvicorn

b = fixture.backend
ROOT = Path(__file__).resolve().parents[1]


class AdminLoginBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.password = secrets.token_urlsafe(24)
        with b.SessionLocal() as db:
            a = b.Company(name='Empresa A', slug='ui-a')
            z = b.Company(name='Empresa B', slug='ui-b')
            db.add_all([a, z])
            db.flush()
            cls.a, cls.z = a.id, z.id
            encoded = hash_password(cls.password)
            for email, companies in [('single@example.invalid', [a]), ('multi@example.invalid', [a, z])]:
                user = b.User(name='UI user', email=email, password_hash=encoded)
                db.add(user)
                db.flush()
                for company in companies:
                    db.add(b.UserCompany(user_id=user.id, company_id=company.id, role='company_admin'))
            for company, tag in [(a.id, 'UI-A'), (z.id, 'UI-B'), (b.DEFAULT_COMPANY_ID, 'UI-LEGACY')]:
                db.add(b.Equipment(company_id=company, tag=tag, name=tag, photo='test-only'))
            db.commit()
        b.app.mount('/ui-login', StaticFiles(directory=str(ROOT / 'admin'), html=True))
        cls.sock = socket.socket()
        cls.sock.bind(('127.0.0.1', 0))
        cls.sock.listen(128)
        cls.base = f'http://127.0.0.1:{cls.sock.getsockname()[1]}'
        cls.server = uvicorn.Server(uvicorn.Config(b.app, log_level='critical', access_log=False))
        cls.thread = threading.Thread(target=cls.server.run, kwargs={'sockets': [cls.sock]}, daemon=True)
        cls.thread.start()
        for _ in range(100):
            if cls.server.started:
                break
            time.sleep(.05)
        assert cls.server.started
        cls.playwright = sync_playwright().start()
        executable = os.environ.get('TAGCHECK_BROWSER_EXECUTABLE')
        if not executable:
            executable = next((path for path in [
                r'C:\Program Files\Google\Chrome\Application\chrome.exe',
                r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
            ] if Path(path).exists()), None)
        cls.browser = cls.playwright.chromium.launch(headless=True, executable_path=executable)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()
        cls.server.should_exit = True
        cls.thread.join(timeout=10)
        cls.sock.close()
        b.engine.dispose()

    def setUp(self):
        self.context = self.browser.new_context(service_workers='block')
        self.context.route('**/*', self.route)
        self.page = self.context.new_page()
        self.errors = []
        self.requests = []
        self.page.on('pageerror', lambda error: self.errors.append(str(error)))
        self.page.on('request', lambda request: self.requests.append(request))
        self.page.goto(self.base + '/ui-login/index.html')
        expect(self.page.locator('#loginForm')).to_be_visible()

    def tearDown(self):
        self.context.close()
        self.assertEqual(self.errors, [])

    def route(self, route):
        if not route.request.url.startswith(self.base + '/'):
            route.abort()
        elif route.request.url.split('?', 1)[0].endswith('/config.js'):
            source = (ROOT / 'admin/config.js').read_text(encoding='utf-8')
            source = re.sub(r"API_BASE_URL:\s*'[^']*'", f"API_BASE_URL: '{self.base}'", source)
            route.fulfill(status=200, content_type='application/javascript', body=source)
        else:
            route.continue_()

    def login(self, email='single@example.invalid', password=None):
        self.page.locator('#loginUserInput').fill(email)
        self.page.locator('#loginPassInput').fill(password or self.password)
        self.page.locator('#loginPassInput').press('Enter')

    def stored_token(self):
        return self.page.evaluate('sessionStorage.getItem(window.TAGCHECK_ADMIN_CONFIG.STORAGE_KEYS.authToken)')

    def select_company(self, company):
        self.page.locator('#companySelect').select_option(str(company))
        self.page.locator('#selectCompanyButton').click()

    def test_single_company_enters_directly(self):
        self.login()
        expect(self.page.locator('#activeCompany')).to_have_text('Empresa: Empresa A')
        expect(self.page.locator('#searchButton')).to_be_visible()
        expect(self.page.locator('#companyForm')).to_have_count(0)
        expect(self.page.locator('body')).to_contain_text('UI-A')
        expect(self.page.locator('body')).not_to_contain_text('UI-B')
        login_request = next(r for r in self.requests if r.url.endswith('/auth/login'))
        self.assertEqual(login_request.post_data_json['email'], 'single@example.invalid')
        self.assertNotIn('username', login_request.post_data_json)
        self.assertTrue(self.stored_token())

    def test_two_companies_wait_for_selection(self):
        self.login('multi@example.invalid')
        expect(self.page.locator('#companySelect option')).to_have_text(['Empresa A', 'Empresa B'])
        self.assertIsNone(self.stored_token())
        expect(self.page.locator('#searchButton')).to_have_count(0)
        self.assertFalse(any(r.url.endswith('/equipment') for r in self.requests))
        self.page.locator('#cancelCompanyButton').click()
        expect(self.page.locator('#loginForm')).to_be_visible()
        expect(self.page.locator('#loginPassInput')).to_have_value('')

    def test_select_company_uses_selection_endpoint(self):
        self.login('multi@example.invalid')
        self.select_company(self.z)
        expect(self.page.locator('#activeCompany')).to_have_text('Empresa: Empresa B')
        expect(self.page.locator('body')).to_contain_text('UI-B')
        expect(self.page.locator('body')).not_to_contain_text('UI-A')
        request = next(r for r in self.requests if r.url.endswith('/auth/select-company'))
        self.assertEqual(request.post_data_json, {'company_id': self.z})
        self.assertTrue(request.headers['authorization'].startswith('Bearer '))
        self.assertNotEqual(request.headers['authorization'][7:], self.stored_token())

    def test_unauthorized_company_shows_error_without_session(self):
        self.login('multi@example.invalid')
        expect(self.page.locator('#companySelect')).to_be_visible()
        self.page.locator('#companySelect option').first.evaluate(
            '(option, id) => { option.value = String(id); }', b.DEFAULT_COMPANY_ID)
        with self.page.expect_response(lambda r: r.url.endswith('/auth/select-company')) as response:
            self.page.locator('#selectCompanyButton').click()
        self.assertEqual(response.value.status, 403)
        expect(self.page.get_by_role('alert')).to_contain_text('Acesso à empresa não autorizado.')
        self.assertIsNone(self.stored_token())
        expect(self.page.locator('#searchButton')).to_have_count(0)
        self.select_company(self.a)
        expect(self.page.locator('#activeCompany')).to_have_text('Empresa: Empresa A')

    def test_session_survives_reload_only_in_its_tab(self):
        self.login('multi@example.invalid')
        self.select_company(self.z)
        expect(self.page.locator('#activeCompany')).to_have_text('Empresa: Empresa B')
        token = self.stored_token()
        self.page.reload()
        expect(self.page.locator('#activeCompany')).to_have_text('Empresa: Empresa B')
        expect(self.page.locator('body')).to_contain_text('UI-B')
        self.assertEqual(self.stored_token(), token)
        self.assertIsNone(self.page.evaluate('localStorage.getItem(window.TAGCHECK_ADMIN_CONFIG.STORAGE_KEYS.authToken)'))
        other = self.context.new_page()
        other.goto(self.base + '/ui-login/index.html')
        expect(other.locator('#loginForm')).to_be_visible()
        other.close()
        self.page.locator('#logoutButton').click()
        expect(self.page.locator('#loginForm')).to_be_visible()
        self.assertIsNone(self.stored_token())
        expect(self.page.locator('#activeCompany')).to_be_hidden()

    def test_legacy_admin_basic_regression(self):
        self.login(fixture.ENV['ADMIN_USERNAME'], fixture.ENV['ADMIN_PASSWORD'])
        expect(self.page.locator('#activeCompany')).to_have_text('Empresa: Empresa Padrão')
        expect(self.page.locator('body')).to_contain_text('UI-LEGACY')
        self.page.locator('#searchTagInput').fill('UI-LEGACY')
        with self.page.expect_response(lambda r: '/equipment/tag/UI-LEGACY' in r.url) as response:
            self.page.locator('#searchButton').click()
        self.assertEqual(response.value.status, 200)
        request = next(r for r in self.requests if r.url.endswith('/auth/login'))
        self.assertEqual(request.post_data_json['username'], fixture.ENV['ADMIN_USERNAME'])
        self.assertNotIn('email', request.post_data_json)
        self.page.locator('#logoutButton').click()
        expect(self.page.locator('#loginForm')).to_be_visible()


if __name__ == '__main__':
    unittest.main(verbosity=2)
