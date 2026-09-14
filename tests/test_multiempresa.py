import unittest
import secrets
from unittest.mock import patch
import test_stabilization as fixture
from fastapi.testclient import TestClient
from sqlalchemy import select
from passwords import hash_password

b = fixture.backend

class MultiempresaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.password = secrets.token_urlsafe(24)
        cls.encoded = hash_password(cls.password)
        cls.client = TestClient(b.app)

    @classmethod
    def tearDownClass(cls):
        cls.client.close()
        b.engine.dispose()

    def setUp(self):
        self.prefix = secrets.token_hex(6)
        with b.SessionLocal() as db:
            a = b.Company(name='Empresa A', slug='a-'+self.prefix)
            z = b.Company(name='Empresa B', slug='b-'+self.prefix)
            db.add_all([a,z]); db.flush()
            self.a, self.z = a.id, z.id
            self.users = {}
            for name in ('a','b','both','viewer','none'):
                user = b.User(name=name, email=f'{name}-{self.prefix}@example.invalid', password_hash=self.encoded)
                db.add(user); db.flush(); self.users[name]=(user.id,user.email)
            for name,company,role in [('a',a.id,'operator'),('b',z.id,'company_admin'),('both',a.id,'viewer'),('both',z.id,'viewer'),('viewer',a.id,'viewer')]:
                db.add(b.UserCompany(user_id=self.users[name][0], company_id=company, role=role))
            self.items={}
            for name,company in [('a',a.id),('b',z.id),('default',b.DEFAULT_COMPANY_ID)]:
                item=b.Equipment(company_id=company,tag=f'{self.prefix}-{name}',name=name,photo='https://example.invalid/photo.png')
                db.add(item); db.flush(); self.items[name]=(item.id,item.tag)
            db.commit()

    def login(self,name):
        return self.client.post('/auth/login',json={'email':self.users[name][1],'password':self.password})

    def headers(self,name):
        r=self.login(name); self.assertEqual(r.status_code,200)
        return {'Authorization':'Bearer '+r.json()['token']}

    def admin(self):
        r=self.client.post('/auth/login',json={'username':fixture.ENV['ADMIN_USERNAME'],'password':fixture.ENV['ADMIN_PASSWORD']})
        self.assertEqual(r.status_code,200)
        return {'Authorization':'Bearer '+r.json()['token']}

    def test_shared_tag_creation_updates_and_isolation(self):
        shared_tag = self.prefix + '-shared'
        created = {}
        with patch.object(b.cloudinary.uploader, 'upload', return_value={'secure_url': 'https://example.invalid/test.png'}):
            for company in ('a', 'b'):
                headers = self.headers(company)
                response = self.client.post('/equipment', headers=headers,
                    data={'tag': shared_tag, 'name': company},
                    files={'photo': ('t.png', b'test', 'image/png')})
                self.assertEqual(response.status_code, 200, response.text)
                created[company] = response.json()['id']
                duplicate = self.client.post('/equipment', headers=headers,
                    data={'tag': shared_tag, 'name': 'duplicate'},
                    files={'photo': ('t.png', b'test', 'image/png')})
                self.assertEqual(duplicate.status_code, 400)
        for own, other in [('a', 'b'), ('b', 'a')]:
            headers = self.headers(own)
            fetched = self.client.get('/equipment/tag/' + shared_tag, headers=headers)
            self.assertEqual(fetched.json()['id'], created[own])
            rows = self.client.get('/equipment', headers=headers).json()
            self.assertIn(created[own], {row['id'] for row in rows})
            self.assertNotIn(created[other], {row['id'] for row in rows})
            self.assertEqual(self.client.put(f'/equipment/{created[other]}', headers=headers,
                data={'tag': shared_tag, 'name': 'forbidden'}).status_code, 404)
            self.assertEqual(self.client.put(f'/equipment/{self.items[own][0]}', headers=headers,
                data={'tag': shared_tag, 'name': 'duplicate'}).status_code, 400)
            # Updating to a TAG used only by the other company remains allowed.
            response = self.client.put(f'/equipment/{created[own]}', headers=headers,
                data={'tag': self.items[other][1], 'name': own})
            self.assertEqual(response.status_code, 200, response.text)

    def test_bidirectional_isolation_all_reads(self):
        for own,other in [('a','b'),('b','a')]:
            headers=self.headers(own)
            rows=self.client.get('/equipment',headers=headers).json()
            self.assertEqual([x['id'] for x in rows],[self.items[own][0]])
            self.assertEqual(self.client.get('/equipment/tag/'+self.items[other][1],headers=headers).status_code,404)
            self.assertEqual(self.client.get(f'/equipment/{self.items[other][0]}/qr-payload',headers=headers).status_code,404)

    def test_public_only_default_company(self):
        rows=self.client.get('/equipment').json()
        ids={x['id'] for x in rows}
        self.assertIn(self.items['default'][0],ids)
        self.assertNotIn(self.items['a'][0],ids)
        self.assertNotIn(self.items['b'][0],ids)
        for name in ('a','b'):
            self.assertEqual(self.client.get('/equipment/tag/'+self.items[name][1]).status_code,404)
            self.assertEqual(self.client.get(f'/equipment/{self.items[name][0]}/qr-payload').status_code,404)

    def test_single_company_login_claims(self):
        result=self.login('a').json()
        self.assertFalse(result['requires_company_selection'])
        self.assertEqual(result['company_id'],self.a)
        claims=b.auth.decode(result['token'],'session')
        for field in ('user_id','email','company_id','role','is_superadmin','exp'):
            self.assertIn(field,claims)
        self.assertNotIn('password_hash',claims)
        self.assertNotIn(fixture.ENV['ADMIN_TOKEN'],str(claims))
        me=self.client.get('/auth/me',headers={'Authorization':'Bearer '+result['token']})
        self.assertEqual(me.json()['company_id'],self.a)

    def test_multiple_company_selection(self):
        result=self.login('both').json()
        self.assertTrue(result['requires_company_selection'])
        self.assertNotIn('token',result)
        self.assertEqual({c['id'] for c in result['companies']},{self.a,self.z})
        headers={'Authorization':'Bearer '+result['selection_token']}
        self.assertEqual(self.client.get('/equipment',headers=headers).status_code,401)
        selected=self.client.post('/auth/select-company',headers=headers,json={'company_id':self.z})
        self.assertEqual(selected.status_code,200)
        self.assertEqual(selected.json()['company_id'],self.z)
        self.assertEqual(self.client.get('/equipment',headers={'Authorization':'Bearer '+selected.json()['token']}).json()[0]['id'],self.items['b'][0])

    def test_unauthorized_company_selection(self):
        self.assertEqual(self.client.post('/auth/select-company',headers=self.headers('a'),json={'company_id':self.z}).status_code,403)
        token=self.login('both').json()['selection_token']
        self.assertEqual(self.client.post('/auth/select-company',headers={'Authorization':'Bearer '+token},json={'company_id':b.DEFAULT_COMPANY_ID}).status_code,403)

    def test_zero_companies_denied(self):
        self.assertEqual(self.login('none').status_code,403)

    def test_inactive_company_revokes_session(self):
        headers=self.headers('a')
        with b.SessionLocal() as db:
            db.get(b.Company,self.a).active=False; db.commit()
        self.assertEqual(self.login('a').status_code,403)
        self.assertEqual(self.client.get('/equipment',headers=headers).status_code,403)

    def test_inactive_user_revokes_session(self):
        headers=self.headers('a')
        with b.SessionLocal() as db:
            db.get(b.User,self.users['a'][0]).active=False; db.commit()
        self.assertEqual(self.login('a').status_code,403)
        self.assertEqual(self.client.get('/equipment',headers=headers).status_code,403)

    def test_revoked_membership_and_changed_role(self):
        headers=self.headers('a')
        with b.SessionLocal() as db:
            link=db.scalar(select(b.UserCompany).where(b.UserCompany.user_id==self.users['a'][0]))
            link.role='viewer'; db.commit()
        self.assertEqual(self.client.get('/equipment',headers=headers).status_code,403)
        headers=self.headers('a')
        with b.SessionLocal() as db:
            link=db.scalar(select(b.UserCompany).where(b.UserCompany.user_id==self.users['a'][0]))
            link.active=False; db.commit()
        self.assertEqual(self.client.get('/equipment',headers=headers).status_code,403)

    def test_role_crud_matrix(self):
        for role in ('company_admin', 'supervisor', 'operator', 'viewer'):
            with self.subTest(role=role):
                with b.SessionLocal() as db:
                    link = db.scalar(select(b.UserCompany).where(b.UserCompany.user_id == self.users['a'][0]))
                    link.role = role
                    db.commit()
                headers = self.headers('a')
                self.assertEqual(self.client.get('/equipment', headers=headers).status_code, 200)
                with patch.object(b.cloudinary.uploader, 'upload', return_value={'secure_url': 'https://example.invalid/test.png'}):
                    created = self.client.post('/equipment', headers=headers,
                        data={'tag': self.prefix + '-' + role, 'name': role},
                        files={'photo': ('test.png', b'test', 'image/png')})
                self.assertEqual(created.status_code, 403 if role == 'viewer' else 200)
                item_id = self.items['a'][0] if role == 'viewer' else created.json()['id']
                updated = self.client.put(f'/equipment/{item_id}', headers=headers,
                    data={'tag': self.prefix + '-updated-' + role, 'name': 'Updated'})
                self.assertEqual(updated.status_code, 403 if role == 'viewer' else 200)
                deleted = self.client.delete(f'/equipment/{item_id}', headers=headers)
                self.assertEqual(deleted.status_code, 403 if role in ('operator', 'viewer') else 200)

    def test_roles_restrict_operations(self):
        headers=self.headers('viewer')
        self.assertEqual(self.client.put(f'/equipment/{self.items["a"][0]}',headers=headers,data={'tag':self.items['a'][1],'name':'forbidden'}).status_code,403)
        self.assertEqual(self.client.delete(f'/equipment/{self.items["a"][0]}',headers=headers).status_code,403)
        self.assertEqual(self.client.delete(f'/equipment/{self.items["a"][0]}',headers=self.headers('a')).status_code,403)
        self.assertEqual(self.client.get('/companies',headers=self.headers('b')).status_code,403)

    def test_cross_company_updates_and_deletes(self):
        for own,other in [('a','b'),('b','a')]:
            headers=self.headers(own)
            self.assertEqual(self.client.put(f'/equipment/{self.items[other][0]}',headers=headers,data={'tag':self.items[other][1],'name':'hacked'}).status_code,404)
            self.assertIn(self.client.delete(f'/equipment/{self.items[other][0]}',headers=headers).status_code,(403,404))
        with b.SessionLocal() as db:
            self.assertEqual(db.get(b.Equipment,self.items['a'][0]).name,'a')
            self.assertEqual(db.get(b.Equipment,self.items['b'][0]).name,'b')

    def test_company_id_manipulation(self):
        headers=self.headers('a')
        self.assertEqual(self.client.get('/equipment',headers=headers,params={'company_id':self.z}).status_code,403)
        self.assertEqual(self.client.get('/equipment',headers={**headers,'X-Company-ID':str(self.z)}).status_code,403)
        self.assertEqual(self.client.get('/equipment',params={'company_id':self.z}).status_code,401)
        with patch.object(b.cloudinary.uploader,'upload',return_value={'secure_url':'https://example.invalid/test.png'}):
            r=self.client.post('/equipment',headers=headers,data={'company_id':self.z,'tag':self.prefix+'-new','name':'new'},files={'photo':('t.png',b'test','image/png')})
        self.assertEqual(r.status_code,200)
        with b.SessionLocal() as db:
            self.assertEqual(db.get(b.Equipment,r.json()['id']).company_id,self.a)

    def test_anonymous_protected_operations(self):
        self.assertEqual(self.client.post('/equipment',data={'tag':'x','name':'x','company_id':self.a},files={'photo':('t.png',b'x','image/png')}).status_code,401)
        self.assertEqual(self.client.put(f'/equipment/{self.items["a"][0]}',data={'tag':'x','name':'x'}).status_code,401)
        self.assertEqual(self.client.delete(f'/equipment/{self.items["a"][0]}').status_code,401)
        self.assertEqual(self.client.post('/equipment/pdf-access').status_code,401)
        self.assertEqual(self.client.get('/equipment',headers={'Authorization':'Bearer invalid'}).status_code,401)

    def test_wrong_password_expired_and_tampered(self):
        self.assertEqual(self.client.post('/auth/login',json={'email':self.users['a'][1],'password':'incorrect'}).status_code,401)
        headers=self.headers('a')
        self.assertEqual(self.client.get('/equipment',headers={'Authorization':headers['Authorization']+'x'}).status_code,401)
        with patch.object(b.time,'time',return_value=b.time.time()+9*3600):
            self.assertEqual(self.client.get('/equipment',headers=headers).status_code,401)

    def test_superadmin_management_and_safe_responses(self):
        headers=self.admin()
        self.assertEqual(self.client.get('/companies',headers=headers).status_code,200)
        company=self.client.post('/companies',headers=headers,json={'name':'Managed','slug':'managed-'+self.prefix})
        self.assertEqual(company.status_code,201)
        user=self.client.post('/users',headers=headers,json={'name':'Managed','email':'managed-'+self.prefix+'@example.invalid','password':self.password})
        self.assertEqual(user.status_code,201)
        self.assertNotIn('password',user.text)
        self.assertNotIn(self.password,user.text)
        link=self.client.post(f'/users/{user.json()["id"]}/companies',headers=headers,json={'company_id':company.json()['id'],'role':'supervisor'})
        self.assertEqual(link.status_code,200)
        self.assertEqual(link.json()['role'],'supervisor')
        self.assertEqual(self.client.patch(f'/companies/{company.json()["id"]}',headers=headers,json={'active':False}).status_code,200)
        self.assertEqual(self.client.patch(f'/users/{user.json()["id"]}',headers=headers,json={'active':False}).status_code,200)
        users=self.client.get('/users',headers=headers)
        self.assertNotIn('password_hash',users.text)
        self.assertNotIn(fixture.ENV['ADMIN_TOKEN'],users.text)
        short_password=secrets.token_hex(3)
        invalid=self.client.post('/users',headers=headers,json={'name':'x','email':'bad','password':short_password})
        self.assertEqual(invalid.status_code,422)
        self.assertNotIn(short_password,invalid.text)
        self.assertTrue(all('input' not in error for error in invalid.json()['detail']))
        self.assertEqual(self.client.post(f'/users/{user.json()["id"]}/companies',headers=headers,json={'company_id':self.a,'role':'root'}).status_code,422)

    def test_pdf_token_is_scoped_and_has_separate_purpose(self):
        headers=self.headers('a')
        ticket=self.client.post('/equipment/pdf-access',headers=headers)
        self.assertEqual(ticket.status_code,200)
        token=ticket.json()['token']
        self.assertLessEqual(ticket.json()['expires_in'],120)
        with patch.object(b.canvas.Canvas,'drawCentredString',autospec=True) as draw:
            pdf=self.client.post('/equipment/pdf',data={'pdf_token':token})
        self.assertEqual(pdf.status_code,200)
        self.assertTrue(pdf.content.startswith(b'%PDF-'))
        labels=[call.args[-1] for call in draw.call_args_list]
        self.assertIn(self.items['a'][1],labels)
        self.assertNotIn(self.items['b'][1],labels)
        self.assertNotIn(self.items['default'][1],labels)
        self.assertEqual(pdf.headers['cache-control'],'no-store')
        self.assertEqual(self.client.post('/equipment/pdf',params={'company_id':self.z},data={'pdf_token':token}).status_code,403)
        self.assertEqual(self.client.get('/equipment',headers={'Authorization':'Bearer '+token}).status_code,401)
        self.assertEqual(self.client.post('/equipment/pdf',data={'pdf_token':headers['Authorization'][7:]}).status_code,401)
        self.assertEqual(self.client.post('/equipment/pdf',data={'pdf_token':token+'x'}).status_code,401)
        with patch.object(b.time,'time',return_value=b.time.time()+121):
            self.assertEqual(self.client.post('/equipment/pdf',data={'pdf_token':token}).status_code,401)

    def test_public_pdf_and_disabled_default_company(self):
        with patch.object(b.canvas.Canvas,'drawCentredString',autospec=True) as draw:
            pdf=self.client.get('/equipment/pdf')
        self.assertEqual(pdf.status_code,200)
        labels=[call.args[-1] for call in draw.call_args_list]
        self.assertIn(self.items['default'][1],labels)
        self.assertNotIn(self.items['a'][1],labels)
        self.assertNotIn(self.items['b'][1],labels)
        try:
            with b.SessionLocal() as db:
                db.get(b.Company,b.DEFAULT_COMPANY_ID).active=False; db.commit()
            self.assertEqual(self.client.get('/equipment').status_code,403)
        finally:
            with b.SessionLocal() as db:
                db.get(b.Company,b.DEFAULT_COMPANY_ID).active=True; db.commit()

    def test_pre_migration_session_compatibility(self):
        import hmac, hashlib
        payload=f'{int(b.time.time())+300}.{secrets.token_hex(32)}'
        sig=hmac.new(fixture.ENV['ADMIN_TOKEN'].encode(),(fixture.ENV['ADMIN_USERNAME']+'\0'+fixture.ENV['ADMIN_PASSWORD']+'\0'+payload).encode(),hashlib.sha256).hexdigest()
        headers={'Authorization':'Bearer '+payload+'.'+sig}
        self.assertEqual(self.client.get('/auth/me',headers=headers).json()['company_id'],b.DEFAULT_COMPANY_ID)
        self.assertEqual(self.client.get('/companies',headers=headers).status_code,403)

if __name__=='__main__':
    try:
        unittest.main(verbosity=2)
    finally:
        b.engine.dispose(); fixture.TMP.cleanup()
