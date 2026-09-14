"""Focused real-browser roles and optional Viewer sessions; temporary SQLite only."""
import re
import unittest
from fastapi.staticfiles import StaticFiles
from playwright.sync_api import expect
import test_admin_login_browser as fixture

b = fixture.b
ROOT = fixture.ROOT


class RolesViewerBrowserTests(fixture.AdminLoginBrowserTests):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        with b.SessionLocal() as db:
            for role in ('company_admin', 'supervisor', 'operator', 'viewer'):
                user = b.User(name=role, email=role+'@example.invalid', password_hash=fixture.hash_password(cls.password))
                db.add(user); db.flush()
                db.add(b.UserCompany(user_id=user.id, company_id=cls.a, role=role))
            for company, name in [(cls.a, 'Shared A'), (cls.z, 'Shared B'), (b.DEFAULT_COMPANY_ID, 'Shared Public')]:
                db.add(b.Equipment(company_id=company, tag='SHARED-UI', name=name, photo='test-only'))
            db.commit()
        b.app.mount('/ui-viewer', StaticFiles(directory=str(ROOT / 'viewer'), html=True))

    def route(self, route):
        if not route.request.url.startswith(self.base + '/'):
            route.abort()
        elif route.request.url.endswith('/config.js'):
            folder = 'viewer' if '/ui-viewer/' in route.request.url else 'admin'
            source = (ROOT / folder / 'config.js').read_text(encoding='utf-8')
            source = re.sub(r"API_BASE_URL:\s*'[^']*'", f"API_BASE_URL: '{self.base}'", source)
            route.fulfill(status=200, content_type='application/javascript', body=source)
        else:
            route.continue_()

    def viewer_login(self, email='single@example.invalid', company=None):
        self.page.locator('#authButton').click()
        self.page.locator('#viewerEmail').fill(email)
        self.page.locator('#viewerPassword').fill(self.password)
        self.page.locator('#viewerLoginSubmit').click()
        if company is not None:
            expect(self.page.locator('#viewerCompany')).to_be_visible()
            self.assertIsNone(self.page.evaluate('sessionStorage.getItem(CONFIG.STORAGE_KEYS.authToken)'))
            self.page.locator('#viewerCompany').select_option(str(company))
            self.page.locator('#viewerLoginSubmit').click()
        expect(self.page.locator('#authButton')).to_have_text('Sair')
        expect(self.page.locator('#viewerLoginForm')).to_have_count(0)
        if not self.page.locator('#goSearch').count():
            self.page.locator('#backButton').click()
        expect(self.page.locator('#goSearch')).to_be_visible()

    def viewer_search(self, tag):
        self.page.locator('#goSearch').click()
        self.page.locator('#tagInput').fill(tag)
        self.page.locator('#searchButton').click()

    def test_viewer_logo_follows_session_and_clears_on_logout(self):
        from io import BytesIO
        from PIL import Image
        out=BytesIO();Image.new('RGB',(8,8),'blue').save(out,format='PNG')
        with b.SessionLocal() as db:
            company=db.get(b.Company,self.a)
            company.logo_url='/company/logo?v=browser-test'
            company.logo_data=out.getvalue();company.logo_mime='image/png';db.commit()
        try:
            self.page.goto(self.base+'/ui-viewer/index.html')
            self.viewer_login()
            self.page.wait_for_function("document.querySelector('.brand-logo').src.startsWith('blob:')")
            expect(self.page.locator('#activeCompany')).to_have_text('Empresa: Empresa A')
            self.page.locator('#authButton').click()
            expect(self.page.locator('.brand-logo')).to_have_attribute('src','./public/logo.png')
            self.viewer_login('multi@example.invalid',self.z)
            expect(self.page.locator('#activeCompany')).to_have_text('Empresa: Empresa B')
            expect(self.page.locator('.brand-logo')).to_have_attribute('src','./public/logo.png')
        finally:
            with b.SessionLocal() as db:
                company=db.get(b.Company,self.a)
                company.logo_url=company.logo_data=company.logo_mime=None;db.commit()

    def test_admin_role_controls(self):
        for role in ('company_admin', 'supervisor', 'operator', 'viewer'):
            with self.subTest(role=role):
                self.login(role+'@example.invalid')
                expect(self.page.locator('#searchButton')).to_be_visible()
                self.assertEqual(self.page.evaluate('state.role'), role)
                expect(self.page.locator('#createButton')).to_have_count(0 if role == 'viewer' else 1)
                expect(self.page.locator('[onclick^="startEditItem"]')).to_have_count(0 if role == 'viewer' else 2)
                expect(self.page.locator('[onclick^="askDeleteItem"]')).to_have_count(2 if role in ('company_admin', 'supervisor') else 0)
                expect(self.page.locator('#unitManagement')).to_have_count(1 if role == 'company_admin' else 0)
                expect(self.page.locator('#pdfButton')).to_be_visible()
                self.page.locator('#logoutButton').click()

    def test_api_success_overrides_failed_health(self):
        calls = []
        def unavailable(route):
            calls.append(1)
            route.fulfill(status=503, body='starting')
        self.context.route('**/health', unavailable)
        self.page.reload()
        expect(self.page.locator('#loginForm')).to_be_visible()
        self.assertEqual(len(calls), 3)
        self.login()
        expect(self.page.locator('#apiStatusBadge')).to_have_text('API online')
        for path in ('/auth/me', '/units', '/equipment'):
            self.page.evaluate('state.apiReachable = false')
            self.page.evaluate('(path) => fetchWithTimeout(CONFIG.API_BASE_URL + path, {headers: getAuthHeaders()})', path)
            self.assertTrue(self.page.evaluate('state.apiReachable'))

    def test_health_retries_until_success(self):
        calls = []
        def waking(route):
            calls.append(1)
            route.fulfill(status=200 if len(calls) == 3 else 503, content_type='application/json', body='{}')
        self.context.route('**/health', waking)
        self.page.reload()
        expect(self.page.locator('#loginForm')).to_be_visible()
        self.assertEqual(len(calls), 3)
        self.assertTrue(self.page.evaluate('state.apiReachable'))

    def test_company_admin_manages_units(self):
        self.login()
        self.page.locator('#unitName').fill('Unidade UI')
        self.page.locator('#unitSlug').fill('unidade-ui')
        self.page.locator('#unitCreateForm button').click()
        toggle = self.page.locator('#unitManagement [data-unit-toggle]').last
        expect(toggle).to_have_text('Desativar')
        toggle.click()
        expect(toggle).to_have_text('Ativar')

    def test_health_failure_cannot_overwrite_concurrent_success(self):
        self.login()
        expect(self.page.locator('#searchButton')).to_be_visible()
        self.context.route('**/health', lambda route: route.fulfill(status=503, body='starting'))
        self.page.evaluate('''async () => {
            const ping = pingApi();
            await readIdentity();
            await ping;
        }''')
        self.assertTrue(self.page.evaluate('state.apiReachable'))

    def test_viewer_public_and_authenticated_same_tag(self):
        self.page.goto(self.base+'/ui-viewer/index.html?tag=SHARED-UI')
        expect(self.page.locator('#app')).to_contain_text('Shared Public')
        self.viewer_login()
        expect(self.page.locator('#activeCompany')).to_have_text('Empresa: Empresa A')
        self.viewer_search('SHARED-UI')
        expect(self.page.locator('#app')).to_contain_text('Shared A')
        expect(self.page.locator('#app')).not_to_contain_text('Shared Public')
        token = self.page.evaluate('state.authToken')
        self.assertEqual(self.page.evaluate('sessionStorage.getItem(CONFIG.STORAGE_KEYS.authToken)'), token)
        local = self.page.evaluate('JSON.stringify(localStorage)')
        self.assertNotIn(token, local)
        self.assertNotIn('Shared A', local)
        self.assertNotIn(token, self.page.url)
        request = [r for r in self.requests if '/equipment/tag/SHARED-UI' in r.url][-1]
        self.assertEqual(request.headers['authorization'], 'Bearer '+token)
        self.page.reload()
        expect(self.page.locator('#app')).to_contain_text('Shared A')
        other = self.context.new_page()
        other.goto(self.base+'/ui-viewer/index.html?tag=SHARED-UI')
        expect(other.locator('#app')).to_contain_text('Shared Public')
        expect(other.locator('#authButton')).to_have_text('Entrar')
        other.close()
        self.page.locator('#authButton').click()
        expect(self.page.locator('#authButton')).to_have_text('Entrar')
        self.viewer_search('SHARED-UI')
        expect(self.page.locator('#app')).to_contain_text('Shared Public')
        self.assertIsNone(self.page.evaluate('sessionStorage.getItem(CONFIG.STORAGE_KEYS.authToken)'))

    def test_viewer_discards_response_after_logout(self):
        self.page.goto(self.base+'/ui-viewer/index.html')
        expect(self.page.locator('#goSearch')).to_be_visible()
        self.viewer_login()
        self.page.evaluate('''() => {
            const lookup = searchByTag;
            window.lookupSettled = false;
            searchByTag = (...args) => lookup(...args).finally(() => { window.lookupSettled = true; });
        }''')
        pending = []
        self.context.route('**/equipment/tag/*', lambda route: pending.append(route))
        self.viewer_search('SHARED-UI')
        # A browser-side fetch promise remains pending until the held route completes.
        self.page.locator('#authButton').click()
        self.assertTrue(pending)
        pending[0].fulfill(status=200, content_type='application/json',
                           body='{"id":999,"tag":"SHARED-UI","name":"Private delayed"}')
        self.page.wait_for_function('window.lookupSettled === true')
        expect(self.page.locator('#authButton')).to_have_text('Entrar')
        expect(self.page.locator('#app')).not_to_contain_text('Private delayed')
        self.assertNotIn('Private delayed', self.page.evaluate('JSON.stringify(localStorage)'))

    def test_viewer_selection_scope_and_foreign_id(self):
        self.page.goto(self.base+'/ui-viewer/index.html')
        expect(self.page.locator('#goSearch')).to_be_visible()
        self.viewer_login('multi@example.invalid', self.z)
        expect(self.page.locator('#activeCompany')).to_have_text('Empresa: Empresa B')
        self.viewer_search('SHARED-UI')
        expect(self.page.locator('#app')).to_contain_text('Shared B')
        for hint in ('query', 'header'):
            status = self.page.evaluate('''async ({company, hint}) => {
                const response = await fetch(CONFIG.API_BASE_URL + '/equipment' + (hint === 'query' ? '?company_id='+company : ''), {
                  headers: {Authorization: 'Bearer '+state.authToken, ...(hint === 'header' ? {'X-Company-ID': String(company)} : {})}
                }); return response.status;
            }''', {'company': self.a, 'hint': hint})
            self.assertEqual(status, 403)
        with b.SessionLocal() as db:
            foreign = db.query(b.Equipment).filter_by(company_id=self.a, tag='UI-A').one().id
        rejected = self.page.evaluate('(id) => searchById(id).then(() => false, () => true)', str(foreign))
        self.assertTrue(rejected)
        rejected = self.page.evaluate("() => resolveQrContent('TAG=UI-A|NOME=Foreign').then(() => false, () => true)")
        self.assertTrue(rejected)

    def test_viewer_public_hybrid_fallback_preserved(self):
        self.page.goto(self.base+'/ui-viewer/index.html')
        expect(self.page.locator('#goSearch')).to_be_visible()
        self.context.route('**/equipment/tag/*', lambda route: route.abort())
        result = self.page.evaluate("() => resolveQrContent('TAG=OFFLINE-UI|NOME=Legacy offline')")
        self.assertEqual(result['item']['tag'], 'OFFLINE-UI')
        self.assertEqual(result['item']['source'], 'hybrid-offline')

    def test_viewer_revoked_session_does_not_use_public_cache(self):
        self.page.goto(self.base+'/ui-viewer/index.html?tag=SHARED-UI')
        expect(self.page.locator('#app')).to_contain_text('Shared Public')
        self.viewer_login()
        self.context.route('**/equipment/tag/*', lambda route: route.fulfill(status=401, body='{}'))
        self.viewer_search('SHARED-UI')
        expect(self.page.locator('#viewerLoginForm')).to_be_visible()
        expect(self.page.locator('#app')).not_to_contain_text('Shared Public')
        self.assertIsNone(self.page.evaluate('sessionStorage.getItem(CONFIG.STORAGE_KEYS.authToken)'))


if __name__ == '__main__':
    unittest.main(verbosity=2)
