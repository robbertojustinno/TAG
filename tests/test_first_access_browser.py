"""First-access Admin and Viewer flows against the isolated real backend."""
import re
import secrets
import unittest
from fastapi.staticfiles import StaticFiles
from playwright.sync_api import expect
import test_admin_login_browser as fixture

b, ROOT = fixture.b, fixture.ROOT


class FirstAccessBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture.AdminLoginBrowserTests.setUpClass.__func__(cls)
        b.app.mount('/ui-viewer', StaticFiles(directory=str(ROOT / 'viewer'), html=True))

    tearDownClass = classmethod(fixture.AdminLoginBrowserTests.tearDownClass.__func__)
    setUp = fixture.AdminLoginBrowserTests.setUp
    tearDown = fixture.AdminLoginBrowserTests.tearDown
    login = fixture.AdminLoginBrowserTests.login

    def route(self, route):
        if not route.request.url.startswith(self.base + '/'):
            route.abort()
        elif route.request.url.split('?', 1)[0].endswith('/config.js'):
            folder = 'viewer' if '/ui-viewer/' in route.request.url else 'admin'
            source = (ROOT / folder / 'config.js').read_text(encoding='utf-8')
            source = re.sub(r"API_BASE_URL:\s*'[^']*'", f"API_BASE_URL: '{self.base}'", source)
            route.fulfill(status=200, content_type='application/javascript', body=source)
        else:
            route.continue_()

    def user(self, multi=False, demo=False):
        email = 'demo@tagcheck.local' if demo else secrets.token_hex(6) + '@example.invalid'
        with b.SessionLocal() as db:
            user = b.User(name='First access', email=email, password_hash=fixture.hash_password(self.password),
                          must_change_password=not demo)
            db.add(user); db.flush()
            db.add(b.UserCompany(user_id=user.id, company_id=self.a, role='company_admin'))
            if multi:
                db.add(b.UserCompany(user_id=user.id, company_id=self.z, role='viewer'))
            db.commit()
        return email

    def assert_locked(self):
        expect(self.page.get_by_role('heading', name='Defina sua nova senha')).to_be_visible()
        expect(self.page.locator('.topbar-actions')).to_be_hidden()
        expect(self.page.locator('#searchButton')).to_have_count(0)
        expect(self.page.locator('#companyAdminPanel')).to_have_count(0)
        expect(self.page.locator('#goSearch')).to_have_count(0)
        self.assertFalse(self.page.evaluate('state.authToken'))

    def submit_password(self, current=None):
        form = self.page.locator('#changePasswordForm')
        form.locator('[name=current_password]').fill(current or self.password)
        form.locator('[name=new_password]').fill(self.new_password)
        form.locator('[name=confirm_password]').fill(self.new_password)
        form.get_by_role('button', name='Alterar senha').click()

    def test_admin_first_access_reload_error_success_and_next_login(self):
        email = self.user()
        self.new_password = secrets.token_urlsafe(24)
        self.login(email)
        self.assert_locked()
        self.page.reload()
        self.assert_locked()
        self.submit_password('incorrect-password')
        expect(self.page.locator('#passwordFeedback')).to_contain_text('Senha atual incorreta')
        self.assert_locked()
        self.submit_password()
        expect(self.page.locator('#searchButton')).to_be_visible()
        expect(self.page.locator('#companyAdminButton')).to_be_visible()
        self.assertEqual(self.page.evaluate('state.role'), 'company_admin')
        self.page.locator('#logoutButton').click()
        self.login(email, self.new_password)
        expect(self.page.locator('#searchButton')).to_be_visible()
        expect(self.page.locator('#changePasswordForm')).to_have_count(0)

    def test_company_selection_after_change(self):
        self.new_password = secrets.token_urlsafe(24)
        self.login(self.user(multi=True))
        self.assert_locked()
        expect(self.page.locator('#companySelect')).to_have_count(0)
        self.submit_password()
        expect(self.page.locator('#companySelect')).to_be_visible()
        self.page.locator('#companySelect').select_option(str(self.z))
        self.page.locator('#selectCompanyButton').click()
        expect(self.page.locator('#searchButton')).to_be_visible()
        self.assertEqual(self.page.evaluate('state.role'), 'viewer')
        expect(self.page.locator('#activeCompany')).to_have_text('Empresa: Empresa B')

    def test_viewer_first_access_preserves_qr_destination(self):
        email = self.user()
        self.new_password = secrets.token_urlsafe(24)
        self.page.goto(self.base + '/ui-viewer/index.html')
        self.page.locator('#authButton').click()
        self.page.locator('#viewerEmail').fill(email)
        self.page.locator('#viewerPassword').fill(self.password)
        self.page.locator('#viewerLoginSubmit').click()
        self.assert_locked()
        expect(self.page.locator('#backButton')).to_be_hidden()
        self.page.goto(self.base + '/ui-viewer/index.html?tag=UI-A')
        self.assert_locked()
        self.submit_password('incorrect-password')
        expect(self.page.locator('#passwordFeedback')).to_contain_text('Senha atual incorreta')
        self.assert_locked()
        self.submit_password()
        expect(self.page.locator('#activeCompany')).to_have_text('Empresa: Empresa A')
        expect(self.page.locator('#changePasswordForm')).to_have_count(0)
        expect(self.page.locator('body')).to_contain_text('UI-A')
        self.assertTrue(self.page.evaluate('state.authToken.length > 0'))

    def test_existing_demo_enters_without_password_prompt(self):
        self.login(self.user(demo=True))
        expect(self.page.locator('#searchButton')).to_be_visible()
        expect(self.page.locator('#changePasswordForm')).to_have_count(0)


if __name__ == '__main__':
    unittest.main()
