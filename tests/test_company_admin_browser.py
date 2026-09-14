"""Browser coverage for independent administration and real logo uploads."""
import secrets
import unittest
from io import BytesIO
from PIL import Image
from playwright.sync_api import expect
from test_admin_login_browser import AdminLoginBrowserTests as Fixture, b

class CompanyAdminBrowserTests(unittest.TestCase):
    setUpClass=classmethod(Fixture.setUpClass.__func__)
    tearDownClass=classmethod(Fixture.tearDownClass.__func__)
    setUp=Fixture.setUp
    tearDown=Fixture.tearDown
    route=Fixture.route
    login=Fixture.login
    stored_token=Fixture.stored_token

    def open_panel(self):
        self.login()
        expect(self.page.locator('#companyAdminButton')).to_be_visible()
        expect(self.page.locator('#companyForm')).to_have_count(0)
        expect(self.page.locator('#superadminButton')).to_be_hidden()
        self.page.locator('#companyAdminButton').click()
        expect(self.page.locator('#companyUserForm')).to_be_visible()
        expect(self.page.locator('#companyIdentity form')).to_be_visible()

    def test_independent_identity_and_user_lifecycle(self):
        self.open_panel()
        body=self.page.locator('body')
        for forbidden in ['Empresa B','Empresa Padrão','Empresa Demo','Super Admin','company_id','Multiempresa','Tenant']:
            self.assertNotIn(forbidden,body.inner_text())
        expect(self.page.locator('#companyUserRows')).to_contain_text('Administrador')
        form=self.page.locator('#companyUserForm')
        expect(form.locator('[name=role] option')).to_have_text(['Supervisor','Operador','Somente leitura'])
        email='browser-'+secrets.token_hex(5)+'@example.invalid'
        form.locator('[name=name]').fill('User browser')
        form.locator('[name=email]').fill(email)
        form.locator('[name=password]').fill(self.password)
        form.locator('[name=role]').select_option('operator')
        with self.page.expect_response(lambda r:r.url.endswith('/company/users') and r.request.method=='POST') as response:
            form.get_by_role('button',name='Salvar usuário').click()
        self.assertEqual(response.value.status,201)
        uid=response.value.json()['id'];row=self.page.locator(f'[data-user-id="{uid}"]')
        expect(row).to_contain_text(email)
        row.get_by_role('button',name='Editar',exact=True).click()
        form.locator('[name=name]').fill('Edited browser')
        form.locator('[name=role]').select_option('viewer')
        form.get_by_role('button',name='Salvar usuário').click()
        expect(row).to_contain_text('Edited browser')
        row.get_by_role('button',name='Desativar',exact=True).click()
        expect(row).to_contain_text('Inativo')
        row.get_by_role('button',name='Ativar',exact=True).click()
        expect(row).to_contain_text('Ativo')
        row.get_by_role('button',name='Redefinir senha',exact=True).click()
        reset=self.page.locator('#companyPasswordForm');password=secrets.token_urlsafe(24)
        reset.locator('[name=password]').fill(password)
        reset.locator('[name=confirmation]').fill(password)
        reset.get_by_role('button').click()
        expect(reset).to_be_hidden()
        self.assertEqual(self.context.request.post(self.base+'/auth/login',data={'email':email,'password':password}).status,200)
        self.assertFalse(any(r.url.endswith('/companies') or r.url.endswith('/users') and '/company/users' not in r.url for r in self.requests))

    def test_logo_preview_save_header_reload_remove(self):
        self.open_panel()
        editor=self.page.locator('#companyIdentity')
        out=BytesIO();Image.new('RGB',(10,10),'green').save(out,format='PNG')
        editor.locator('[name=file]').set_input_files({'name':'logo.png','mimeType':'image/png','buffer':out.getvalue()})
        expect(editor.locator('[role=status]')).to_contain_text('Prévia')
        expect(self.page.locator('.brand-logo')).to_have_attribute('src','./public/logo.png')
        editor.get_by_role('button',name='Salvar logo').click()
        expect(editor.locator('[role=status]')).to_contain_text('Logo atualizada')
        self.assertTrue(self.page.locator('.brand-logo').get_attribute('src').startswith('blob:'))
        with b.SessionLocal() as db:
            self.assertIsNone(db.get(b.Company,self.z).logo_url)
        self.page.reload()
        expect(self.page.locator('#companyAdminButton')).to_be_visible()
        self.page.wait_for_function("document.querySelector('.brand-logo').src.startsWith('blob:')")
        self.page.locator('#companyAdminButton').click()
        editor.get_by_role('button',name='Remover logo').click()
        expect(editor.locator('[role=status]')).to_contain_text('Logo removida')
        expect(self.page.locator('.brand-logo')).to_have_attribute('src','./public/logo.png')

    def test_lower_roles_cannot_open_administration(self):
        from passwords import hash_password
        for role in ['supervisor','operator','viewer']:
            email=role+'-'+secrets.token_hex(4)+'@example.invalid'
            with b.SessionLocal() as db:
                u=b.User(name=role,email=email,password_hash=hash_password(self.password));db.add(u);db.flush()
                db.add(b.UserCompany(user_id=u.id,company_id=self.a,role=role));db.commit()
            self.login(email)
            expect(self.page.locator('#searchButton')).to_be_visible()
            expect(self.page.locator('#companyAdminButton')).to_be_hidden()
            self.page.locator('#companyAdminButton').evaluate('(b)=>b.click()')
            expect(self.page.locator('#companyAdminPanel')).to_have_count(0)
            self.page.locator('#logoutButton').click()
            expect(self.page.locator('#loginForm')).to_be_visible()

del Fixture

if __name__=='__main__':
    unittest.main(verbosity=2)
