"""Security regression tests using an isolated database and real image bytes."""
import json
import secrets
import unittest
from io import BytesIO
from PIL import Image
from sqlalchemy import select
from fastapi.testclient import TestClient
import test_stabilization as fixture
from passwords import hash_password
b = fixture.backend


def picture(fmt='PNG', color='red'):
    out = BytesIO()
    Image.new('RGB', (8, 8), color).save(out, format=fmt)
    return out.getvalue()


class CompanyAdminTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(b.app)
        cls.password = secrets.token_urlsafe(24)
        cls.hashed = hash_password(cls.password)
        token=cls.client.post('/auth/login',json={'username':fixture.ENV['ADMIN_USERNAME'],'password':fixture.ENV['ADMIN_PASSWORD']}).json()['token']
        cls.global_headers={'Authorization':'Bearer '+token}

    @classmethod
    def tearDownClass(cls):
        cls.client.close()

    def setUp(self):
        self.prefix=secrets.token_hex(6)
        self.headers={}; self.ids={}
        with b.SessionLocal() as db:
            a=b.Company(name='Alfa',slug='alfa-'+self.prefix,email_domains=json.dumps(['alfa.example']))
            z=b.Company(name='Beta',slug='beta-'+self.prefix)
            db.add_all([a,z]);db.flush();self.a,self.z=a.id,z.id
            for name,company,role in [('admin',a,'company_admin'),('other',z,'company_admin'),('target',a,'viewer'),('foreign',z,'viewer'),('supervisor',a,'supervisor'),('operator',a,'operator'),('viewer',a,'viewer')]:
                u=b.User(name=name,email=f'{name}-{self.prefix}@alfa.example',password_hash=self.hashed)
                db.add(u);db.flush();self.ids[name]=u.id
                m=b.UserCompany(user_id=u.id,company_id=company.id,role=role);db.add(m);db.flush()
                self.headers[name]={'Authorization':'Bearer '+b.auth.issue(u,m)}
            unit=b.Unit(company_id=z.id,name='Beta unit',slug='beta');db.add(unit);db.flush();self.unit=unit.id
            item=b.Equipment(company_id=z.id,tag=self.prefix.upper(),name='Beta item',photo='test');db.add(item);db.flush();self.item=item.id
            db.commit()

    def create(self, **extra):
        data={'name':'New','email':f'new-{self.prefix}@alfa.example','password':self.password,'role':'operator'}
        data.update(extra)
        return self.client.post('/company/users',headers=self.headers['admin'],json=data)

    def upload(self, headers=None, path='/company/logo', **kwargs):
        return self.client.post(path,headers=headers or self.headers['admin'],
            files=kwargs.pop('files',{'file':('logo.png',picture(),'image/png')}),**kwargs)

    def test_create_edit_disable_enable_and_reset(self):
        r=self.create();self.assertEqual(r.status_code,201,r.text);u=r.json();uid=u['id']
        self.assertNotIn('is_superadmin',u);self.assertNotIn('company_id',u)
        for data in [{'name':'Edited','role':'supervisor'},{'active':False},{'active':True}]:
            r=self.client.patch(f'/company/users/{uid}',headers=self.headers['admin'],json=data)
            self.assertEqual(r.status_code,200,r.text)
        password=secrets.token_urlsafe(24)
        r=self.client.post(f'/company/users/{uid}/reset-password',headers=self.headers['admin'],json={'password':password})
        self.assertEqual(r.status_code,200)
        self.assertEqual(self.client.post('/auth/login',json={'email':u['email'],'password':password}).status_code,200)
        self.assertEqual(self.client.post('/auth/login',json={'email':u['email'],'password':self.password}).status_code,401)

    def test_company_id_and_privilege_payloads_rejected(self):
        for payload in [{'company_id':self.z},{'is_superadmin':True},{'role':'company_admin'},{'role':'superadmin'}]:
            with self.subTest(payload=payload):
                self.assertEqual(self.create(**payload).status_code,422)
                self.assertEqual(self.client.patch(f'/company/users/{self.ids["target"]}',headers=self.headers['admin'],json=payload).status_code,422)
        self.assertEqual(self.client.post('/users',headers=self.global_headers,json={'name':'x','email':'x@alfa.example','password':self.password,'is_superadmin':True}).status_code,422)

    def test_all_global_routes_require_superadmin(self):
        for role in self.headers:
            for method,path,data in [('GET','/companies',None),('POST','/companies',{'name':'x','slug':'x'}),('PATCH',f'/companies/{self.z}',{'active':False}),('GET','/users',None),('POST','/users',{'name':'x','email':'x@alfa.example','password':self.password}),('PATCH',f'/users/{self.ids["foreign"]}',{'active':False}),('POST',f'/users/{self.ids["foreign"]}/reset-password',{'password':self.password}),('GET',f'/users/{self.ids["foreign"]}/companies',None),('POST',f'/users/{self.ids["foreign"]}/companies',{'company_id':self.a,'role':'company_admin'})]:
                with self.subTest(role=role,path=path):
                    self.assertEqual(self.client.request(method,path,headers=self.headers[role],json=data).status_code,403)
        self.assertEqual(self.client.get('/companies',headers=self.global_headers).status_code,200)

    def test_user_idor_both_directions(self):
        for admin,foreign in [('admin','foreign'),('other','target')]:
            headers=self.headers[admin]
            rows=self.client.get('/company/users',headers=headers).json()
            self.assertNotIn(self.ids[foreign],{x['id'] for x in rows})
            self.assertEqual(self.client.patch(f'/company/users/{self.ids[foreign]}',headers=headers,json={'active':False}).status_code,404)
            self.assertEqual(self.client.post(f'/company/users/{self.ids[foreign]}/reset-password',headers=headers,json={'password':self.password}).status_code,404)

    def test_session_hints_cannot_override_company(self):
        for path in ['/company','/company/users','/company/logo','/units','/equipment']:
            self.assertEqual(self.client.get(path+f'?company_id={self.z}',headers=self.headers['admin']).status_code,403)
            self.assertEqual(self.client.get(path,headers={**self.headers['admin'],'X-Company-ID':str(self.z)}).status_code,403)
        self.assertEqual(self.upload(path=f'/company/logo?company_id={self.z}').status_code,403)
        self.assertEqual(self.upload(data={'company_id':str(self.z)}).status_code,422)

    def test_equipment_unit_idor(self):
        h=self.headers['admin']
        self.assertEqual(self.client.get('/units',headers=h).json(),[])
        self.assertEqual(self.client.get('/equipment',headers=h).json(),[])
        self.assertEqual(self.client.patch(f'/units/{self.unit}',headers=h,json={'active':False}).status_code,404)
        self.assertEqual(self.client.put(f'/equipment/{self.item}',headers=h,data={'name':'Intrusion','tag':'INTRUSION'}).status_code,404)
        self.assertEqual(self.client.delete(f'/equipment/{self.item}',headers=h).status_code,404)

    def test_roles_cannot_access_company_administration(self):
        for role in ['supervisor','operator','viewer']:
            h=self.headers[role]
            for path in ['/company','/company/users']:
                self.assertEqual(self.client.get(path,headers=h).status_code,403)
            self.assertEqual(self.client.post('/company/users',headers=h,json={'name':'x','email':'x@alfa.example','password':self.password,'role':'viewer'}).status_code,403)
            self.assertEqual(self.client.patch(f'/company/users/{self.ids["target"]}',headers=h,json={'active':False}).status_code,403)
            self.assertEqual(self.client.post(f'/company/users/{self.ids["target"]}/reset-password',headers=h,json={'password':self.password}).status_code,403)
            self.assertEqual(self.upload(headers=h).status_code,403)
            self.assertEqual(self.client.delete('/company/logo',headers=h).status_code,403)

    def test_domain_policy_exact_match_and_exceptions(self):
        for email in ['x@other.example','x@sub.alfa.example','x@alfa.example.evil.com']:
            self.assertEqual(self.create(email=email).status_code,422)
        r=self.client.patch(f'/companies/{self.a}',headers=self.global_headers,json={'email_domains':['alfa.example','second.example'],'email_exceptions':['exception@other.example'],'admin_email':'contact@alfa.example'})
        self.assertEqual(r.status_code,200,r.text)
        for email in ['exception@other.example','member@second.example']:
            self.assertEqual(self.create(email=email).status_code,201)
        self.assertEqual(self.client.patch(f'/company/users/{self.ids["target"]}',headers=self.headers['admin'],json={'email':'no@other.example'}).status_code,422)

    def test_policy_does_not_block_existing_accounts(self):
        self.client.patch(f'/companies/{self.a}',headers=self.global_headers,json={'email_domains':['new.example']})
        self.assertEqual(self.client.get('/auth/me',headers=self.headers['viewer']).status_code,200)
        self.assertEqual(self.client.patch(f'/company/users/{self.ids["target"]}',headers=self.headers['admin'],json={'name':'Existing'}).status_code,200)

    def test_shared_identity_cannot_be_changed_across_companies(self):
        with b.SessionLocal() as db:
            db.add(b.UserCompany(user_id=self.ids['target'],company_id=self.z,role='viewer'));db.commit()
        path=f'/company/users/{self.ids["target"]}'
        for data in [{'name':'Intrusion'},{'email':'another@alfa.example'}]:
            self.assertEqual(self.client.patch(path,headers=self.headers['admin'],json=data).status_code,409)
        self.assertEqual(self.client.post(path+'/reset-password',headers=self.headers['admin'],json={'password':self.password}).status_code,409)
        self.assertEqual(self.client.patch(path,headers=self.headers['admin'],json={'active':False}).status_code,200)
        with b.SessionLocal() as db:
            self.assertTrue(db.scalar(select(b.UserCompany).where(b.UserCompany.user_id==self.ids['target'],b.UserCompany.company_id==self.z)).active)
            self.assertTrue(db.get(b.User,self.ids['target']).active)

    def test_administrator_cannot_modify_administrators(self):
        self.assertEqual(self.client.patch(f'/company/users/{self.ids["admin"]}',headers=self.headers['admin'],json={'role':'viewer'}).status_code,403)
        self.assertEqual(self.client.post(f'/company/users/{self.ids["admin"]}/reset-password',headers=self.headers['admin'],json={'password':self.password}).status_code,403)

    def test_logo_upload_read_replace_remove_isolated(self):
        r=self.upload();self.assertEqual(r.status_code,200,r.text);url=r.json()['logo_url']
        self.assertEqual(self.client.get('/auth/me',headers=self.headers['admin']).json()['logo_url'],url)
        self.assertIsNone(self.client.get('/auth/me',headers=self.headers['other']).json()['logo_url'])
        for role in ['admin','supervisor','operator','viewer']:
            image=self.client.get(url,headers=self.headers[role]);self.assertEqual(image.status_code,200)
            self.assertEqual(image.headers['content-type'],'image/png');self.assertEqual(Image.open(BytesIO(image.content)).getpixel((0,0)),(255,0,0,255))
        self.assertEqual(self.client.get(url,headers=self.headers['other']).status_code,404)
        self.assertEqual(self.client.get(url).status_code,401)
        new=self.upload(files={'file':('blue.webp',picture('WEBP','blue'),'image/webp')});self.assertEqual(new.status_code,200,new.text)
        self.assertNotEqual(url,new.json()['logo_url'])
        self.assertEqual(self.client.delete('/company/logo',headers=self.headers['admin']).status_code,200)
        self.assertEqual(self.client.get('/company/logo',headers=self.headers['admin']).status_code,404)

    def test_global_logo_any_company_and_cross_company_denial(self):
        for company in [self.a,self.z]:
            path=f'/companies/{company}/logo'
            self.assertEqual(self.upload(headers=self.global_headers,path=path).status_code,200)
            self.assertEqual(self.client.get(path,headers=self.global_headers).status_code,200)
            for method in ['GET','DELETE']:
                self.assertEqual(self.client.request(method,path,headers=self.headers['admin']).status_code,403)
            self.assertEqual(self.upload(path=path).status_code,403)
        self.client.delete('/company/logo',headers=self.headers['admin'])
        self.assertEqual(self.client.get('/company/logo',headers=self.headers['other']).status_code,200)
        self.assertEqual(self.client.delete(f'/companies/{self.z}/logo',headers=self.global_headers).status_code,200)

    def test_invalid_logo_files(self):
        cases=[('logo.svg',b'<svg/>','image/svg+xml'),('logo.png',picture(),'image/jpeg'),('logo.jpg',picture(),'image/jpeg'),('logo.png',b'not an image','image/png'),('logo.png',b'','image/png'),('logo.png',b'x'*(2*1024*1024+1),'image/png')]
        for file in cases:
            self.assertEqual(self.upload(files={'file':file}).status_code,422)
        self.assertEqual(self.client.post('/company/logo',headers=self.headers['admin']).status_code,422)
        for fmt,ext,mime in [('PNG','png','image/png'),('JPEG','jpg','image/jpeg'),('WEBP','webp','image/webp')]:
            self.assertEqual(self.upload(files={'file':('logo.'+ext,picture(fmt),mime)}).status_code,200)


if __name__=='__main__':
    unittest.main(verbosity=2)
