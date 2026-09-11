"""Only superadmin UI operations, with the existing isolated browser fixture."""
import secrets
import unittest
from playwright.sync_api import expect
from sqlalchemy import select
from test_admin_login_browser import AdminLoginBrowserTests as BrowserFixture, b, fixture


class SuperadminBrowserTests(unittest.TestCase):
    # Reuse infrastructure without inheriting/running the login suite's tests.
    setUpClass = classmethod(BrowserFixture.setUpClass.__func__)
    tearDownClass = classmethod(BrowserFixture.tearDownClass.__func__)
    setUp = BrowserFixture.setUp
    tearDown = BrowserFixture.tearDown
    route = BrowserFixture.route
    login = BrowserFixture.login
    stored_token = BrowserFixture.stored_token

    def open_panel(self):
        self.login(fixture.ENV['ADMIN_USERNAME'], fixture.ENV['ADMIN_PASSWORD'])
        expect(self.page.locator('#superadminButton')).to_be_visible()
        self.page.locator('#superadminButton').click()
        expect(self.page.locator('#companyCreateForm')).to_be_visible()
        expect(self.page.locator('#saveMembership')).to_be_enabled()

    def create_company(self):
        slug = 'panel-' + secrets.token_hex(5)
        form = self.page.locator('#companyCreateForm')
        form.locator('[name=name]').fill(slug)
        form.locator('[name=slug]').fill(slug)
        with self.page.expect_response(lambda r: r.url.endswith('/companies') and r.request.method == 'POST') as response:
            form.get_by_role('button').click()
        self.assertEqual(response.value.status, 201)
        item = response.value.json()
        expect(self.page.locator(f'[data-company-id="{item["id"]}"]')).to_contain_text(slug)
        return item

    def create_user(self):
        name = 'user-' + secrets.token_hex(5)
        form = self.page.locator('#userCreateForm')
        form.locator('[name=name]').fill(name)
        form.locator('[name=email]').fill(name + '@example.invalid')
        form.locator('[name=password]').fill(self.password)
        with self.page.expect_response(lambda r: r.url.endswith('/users') and r.request.method == 'POST') as response:
            form.get_by_role('button').click()
        self.assertEqual(response.value.status, 201)
        user = response.value.json()
        expect(self.page.locator(f'[data-user-id="{user["id"]}"]')).to_contain_text(name)
        expect(form.locator('[name=password]')).to_have_value('')
        self.assertNotIn('password_hash', user)
        self.assertNotIn('password', user)
        return user

    def choose_link(self, user_id, company_id):
        self.page.locator('#memberUser').select_option(str(user_id))
        expect(self.page.locator('#saveMembership')).to_be_enabled()
        self.page.locator('#memberCompany').select_option(str(company_id))

    def save_link(self, role, active=True):
        self.page.locator('#memberRole').select_option(role)
        self.page.locator('#memberActive').set_checked(active)
        with self.page.expect_response(lambda r: '/users/' in r.url and r.url.endswith('/companies') and r.request.method == 'POST') as response:
            self.page.locator('#saveMembership').click()
        self.assertEqual(response.value.status, 200)
        expect(self.page.locator('#saveMembership')).to_be_enabled()
        expect(self.page.locator('#membershipStatus')).to_have_text('Vínculo ativo' if active else 'Vínculo inativo')
        return response.value.json()

    def test_superadmin_accesses_panel(self):
        self.open_panel()
        expect(self.page.locator('#companyRows')).to_contain_text('Empresa Padrão')
        expect(self.page.locator('#userRows')).to_contain_text('single@example.invalid')
        self.page.locator('#backToAdmin').click()
        expect(self.page.locator('#superadminPanel')).to_have_count(0)
        expect(self.page.locator('#searchButton')).to_be_visible()

    def test_normal_user_cannot_view_or_use_panel(self):
        self.login()
        expect(self.page.locator('#searchButton')).to_be_visible()
        expect(self.page.locator('#superadminButton')).to_be_hidden()
        self.page.locator('#superadminButton').evaluate('(button) => button.click()')
        expect(self.page.locator('#superadminPanel')).to_have_count(0)
        headers = {'Authorization': 'Bearer ' + self.stored_token()}
        for path in ['/companies', '/users']:
            self.assertEqual(self.context.request.get(self.base + path, headers=headers).status, 403)
        self.assertFalse(any(r.url.endswith('/companies') or r.url.endswith('/users') for r in self.requests))

    def test_create_company(self):
        self.open_panel()
        company = self.create_company()
        with b.SessionLocal() as db:
            item = db.get(b.Company, company['id'])
            self.assertEqual(item.name, company['name'])
            self.assertTrue(item.active)

    def test_deactivate_and_activate_company(self):
        self.open_panel()
        company = self.create_company()
        row = self.page.locator(f'[data-company-id="{company["id"]}"]')
        for label, state, active in [('Desativar', 'Inativa', False), ('Ativar', 'Ativa', True)]:
            row.get_by_role('button', name=label, exact=True).click()
            expect(row.locator('td').nth(2)).to_have_text(state)
            with b.SessionLocal() as db:
                self.assertEqual(db.get(b.Company, company['id']).active, active)

    def test_create_user(self):
        self.open_panel()
        user = self.create_user()
        with b.SessionLocal() as db:
            item = db.get(b.User, user['id'])
            self.assertEqual(item.email, user['email'])
            self.assertFalse(item.is_superadmin)

    def test_link_user_and_toggle_membership(self):
        self.open_panel()
        company = self.create_company()
        user = self.create_user()
        self.choose_link(user['id'], company['id'])
        first = self.save_link('operator')
        second = self.save_link('operator', False)
        self.assertEqual(first['id'], second['id'])
        self.page.locator('#backToAdmin').click()
        self.page.locator('#superadminButton').click()
        expect(self.page.locator('#saveMembership')).to_be_enabled()
        self.choose_link(user['id'], company['id'])
        expect(self.page.locator('#membershipStatus')).to_have_text('Vínculo inativo')
        expect(self.page.locator('#memberRole')).to_have_value('operator')
        self.assertEqual(self.save_link('operator')['id'], first['id'])

    def test_define_all_supported_roles(self):
        self.open_panel()
        company = self.create_company()
        user = self.create_user()
        self.choose_link(user['id'], company['id'])
        for role in ['company_admin', 'supervisor', 'operator', 'viewer']:
            self.assertEqual(self.save_link(role)['role'], role)
            with b.SessionLocal() as db:
                link = db.scalar(select(b.UserCompany).where(b.UserCompany.user_id == user['id'], b.UserCompany.company_id == company['id']))
                self.assertEqual(link.role, role)

    def test_unauthorized_membership_rejected(self):
        self.login()
        expect(self.page.locator('#searchButton')).to_be_visible()
        headers = {'Authorization': 'Bearer ' + self.stored_token()}
        with b.SessionLocal() as db:
            user = db.scalar(select(b.User).where(b.User.email == 'single@example.invalid'))
            user_id = user.id
        url = self.base + f'/users/{user_id}/companies'
        self.assertEqual(self.context.request.get(url, headers=headers).status, 403)
        self.assertEqual(self.context.request.post(url, headers=headers,
                         data={'company_id': self.z, 'role': 'company_admin', 'active': True}).status, 403)
        with b.SessionLocal() as db:
            self.assertIsNone(db.scalar(select(b.UserCompany).where(b.UserCompany.user_id == user_id, b.UserCompany.company_id == self.z)))


del BrowserFixture  # Do not collect the imported login test class.

if __name__ == '__main__':
    unittest.main(verbosity=2)
