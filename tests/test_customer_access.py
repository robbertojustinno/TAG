import secrets, unittest
from datetime import timedelta
from fastapi.testclient import TestClient
from sqlalchemy import select, func
import test_stabilization as fixture
from models import PasswordRecovery
from customer_access import now
b=fixture.backend

class CustomerAccessTests(unittest.TestCase):
    def setUp(self):
        self.client=TestClient(b.app);self.addCleanup(self.client.close)
        login=self.client.post('/auth/login',json={'username':fixture.ENV['ADMIN_USERNAME'],'password':fixture.ENV['ADMIN_PASSWORD']}).json()
        self.headers={'Authorization':'Bearer '+login['token']}
        self.initial=secrets.token_urlsafe(20);self.email=secrets.token_hex(8)+'@example.invalid'
        self.payload={'company':{'name':'Cliente teste','slug':'customer-'+secrets.token_hex(6)},'administrator':{'name':'Admin cliente','email':self.email,'password':self.initial}}
    def setup_customer(self):
        response=self.client.post('/superadmin/onboard',headers=self.headers,json=self.payload)
        self.assertEqual(response.status_code,201,response.text);return response.json()
    def first_login(self):
        result=self.client.post('/auth/login',json={'email':self.email,'password':self.initial}).json()
        self.assertTrue(result['must_change_password'])
        password=secrets.token_urlsafe(20)
        response=self.client.post('/auth/change-password',headers={'Authorization':'Bearer '+result['token']},json={'current_password':self.initial,'new_password':password,'confirm_password':password})
        self.assertEqual(response.status_code,200,response.text)
        return {'Authorization':'Bearer '+response.json()['token']},password
    def request_link(self,email):
        response=self.client.post('/auth/forgot-password',json={'email':email})
        self.assertEqual(response.status_code,202,response.text)
        rows=self.client.get('/password-recovery/requests',headers=self.headers).json()
        row=next(r for r in rows if r['email']==email)
        return row['id']
    def issue(self,id,headers=None):
        return self.client.post(f'/password-recovery/requests/{id}/issue',headers=headers or self.headers,json={})
    def finish(self,token,password=None):
        password=password or secrets.token_urlsafe(20)
        return self.client.post('/auth/reset-password',json={'token':token,'new_password':password,'confirm_password':password})
    def test_atomic_setup_first_access_and_admin_scope(self):
        result=self.setup_customer();company_id=result['company']['id']
        with b.SessionLocal() as db:
            user=db.get(b.User,result['administrator']['id']);links=list(db.scalars(select(b.UserCompany).where(b.UserCompany.user_id==user.id)))
            self.assertFalse(user.is_superadmin);self.assertTrue(user.must_change_password);self.assertEqual([(l.company_id,l.role) for l in links],[(company_id,'company_admin')])
        headers,_=self.first_login()
        self.assertEqual(self.client.get('/auth/me',headers=headers).json()['company_id'],company_id)
        self.assertEqual(self.client.get('/companies',headers=headers).status_code,403)
        self.assertEqual(self.client.post('/superadmin/onboard',headers=headers,json=self.payload).status_code,403)
        self.assertEqual(self.client.post('/units',headers=headers,json={'name':'Matriz','slug':'matriz'}).status_code,201)
    def test_existing_company_without_admin(self):
        company=self.client.post('/companies',headers=self.headers,json=self.payload['company']).json()
        self.payload.pop('company');self.payload['company_id']=company['id'];self.setup_customer()
        self.payload['administrator']['email']=secrets.token_hex(6)+'@example.invalid'
        self.assertEqual(self.client.post('/superadmin/onboard',headers=self.headers,json=self.payload).status_code,409)
    def test_duplicate_email_rolls_back_new_company(self):
        self.setup_customer();self.payload['company']['slug']='rollback-'+secrets.token_hex(6)
        self.assertEqual(self.client.post('/superadmin/onboard',headers=self.headers,json=self.payload).status_code,409)
        with b.SessionLocal() as db:self.assertIsNone(db.scalar(select(b.Company).where(b.Company.slug==self.payload['company']['slug'])))
    def test_recovery_single_use_and_session_revocation(self):
        self.setup_customer();headers,_=self.first_login();id=self.request_link(self.email)
        token=self.issue(id).json()['token'];password=secrets.token_urlsafe(20)
        self.assertEqual(self.finish(token,password).status_code,200)
        self.assertEqual(self.finish(token).status_code,400)
        self.assertIn(self.client.get('/auth/me',headers=headers).status_code,(401,403))
        result=self.client.post('/auth/login',json={'email':self.email,'password':password}).json()
        self.assertFalse(result['must_change_password']);self.assertIn('token',result)
    def test_expiry_reissue_and_public_no_enumeration(self):
        self.setup_customer();known=self.client.post('/auth/forgot-password',json={'email':self.email})
        unknown=self.client.post('/auth/forgot-password',json={'email':secrets.token_hex(8)+'@example.invalid'})
        self.assertEqual(known.json(),unknown.json());id=self.request_link(self.email)
        old=self.issue(id).json()['token'];token=self.issue(id).json()['token']
        self.assertEqual(self.finish(old).status_code,400)
        with b.SessionLocal() as db:row=db.get(PasswordRecovery,id);row.expires_at=now()-timedelta(seconds=1);db.commit()
        self.assertEqual(self.finish(token).status_code,400)
    def test_recovery_tenant_and_role_isolation(self):
        customer=self.setup_customer();headers,_=self.first_login();id=self.request_link(self.email)
        self.assertEqual(self.issue(id,headers).status_code,404) # company admin requests require Superadmin
        self.assertEqual(self.client.get('/password-recovery/requests').status_code,401)
        self.assertEqual(self.client.get('/password-recovery/requests',headers=headers).json(),[])
        email=secrets.token_hex(8)+'@example.invalid'
        response=self.client.post('/company/users',headers=headers,json={'name':'Operador','email':email,'password':self.initial,'role':'operator'})
        self.assertEqual(response.status_code,201,response.text)
        id=self.request_link(email);self.assertEqual(self.issue(id,headers).status_code,200)
        # An administrator of a different company cannot issue a reset link.
        self.payload['company']['slug']='other-'+secrets.token_hex(6);self.payload['administrator']['email']=secrets.token_hex(8)+'@example.invalid'
        other=self.setup_customer()
        with b.SessionLocal() as db:
            user=db.get(b.User,other['administrator']['id']);user.must_change_password=False;db.commit();link=db.scalar(select(b.UserCompany).where(b.UserCompany.user_id==user.id));foreign={'Authorization':'Bearer '+b.auth.issue(user,link)}
        self.assertEqual(self.issue(id,foreign).status_code,404)
        self.assertNotIn(email,str(self.client.get('/password-recovery/requests',headers=foreign).json()))
    def test_rate_limit_and_validation(self):
        self.setup_customer()
        for _ in range(6):self.client.post('/auth/forgot-password',json={'email':self.email})
        with b.SessionLocal() as db:self.assertEqual(db.scalar(select(func.count()).select_from(PasswordRecovery).where(PasswordRecovery.user_id==db.scalar(select(b.User.id).where(b.User.email==self.email)))),3)
        response=self.client.post('/auth/reset-password',json={'token':'short','new_password':'secret','confirm_password':'secret'})
        self.assertEqual(response.status_code,422);self.assertNotIn('secret',response.text)

    def test_maintenance_account_requires_technical_recovery(self):
        id=self.request_link(b.ADMIN_EMAIL)
        response=self.issue(id)
        self.assertEqual(response.status_code,409)
        self.assertNotIn('token',response.json())
