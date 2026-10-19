import secrets
from datetime import timedelta
from sqlalchemy import select
from test_customer_access import CustomerAccessTests, b
from trials import now

class TrialTests(CustomerAccessTests):
    def test_deadline_existing_session_and_conversion(self):
        self.payload['trial_days']=10
        result=self.setup_customer(); cid=result['company']['id']
        self.assertEqual(result['company']['trial_status'],'pending')
        headers,password=self.first_login()
        with b.SessionLocal() as db:
            company=db.get(b.Company,cid)
            start=company.trial_started_at
            self.assertIsNotNone(start)
            self.assertEqual((company.trial_expires_at-start).days,10)
            company.trial_expires_at=now()-timedelta(seconds=1);db.commit()
        self.assertEqual(self.client.get('/units',headers=headers).status_code,200)
        self.assertEqual(self.client.post('/units',headers=headers,json={'name':'Bloqueada','slug':'blocked'}).status_code,403)
        self.assertEqual(self.client.post(f'/companies/{cid}/trial',headers=headers,json={'action':'activate'}).status_code,403)
        login=self.client.post('/auth/login',json={'email':self.email,'password':password})
        self.assertEqual(login.status_code,200)
        self.assertEqual(self.client.post('/units',headers={'Authorization':'Bearer '+login.json()['token']},json={'name':'Bloqueada','slug':'blocked'}).status_code,403)
        extended=self.client.post(f'/companies/{cid}/trial',headers=self.headers,json={'action':'extend','days':7})
        self.assertEqual(extended.status_code,200,extended.text)
        self.assertEqual(extended.json()['trial_status'],'active')
        self.assertEqual(self.client.post('/units',headers=headers,json={'name':'Matriz','slug':'trial-unit'}).status_code,201)
        converted=self.client.post(f'/companies/{cid}/trial',headers=self.headers,json={'action':'activate'})
        self.assertEqual(converted.json()['trial_status'],'customer')
        with b.SessionLocal() as db:
            self.assertEqual(db.get(b.Company,cid).trial_started_at,start)
    def test_pending_extension_validation_and_no_reset(self):
        self.payload['trial_days']=7
        result=self.setup_customer();cid=result['company']['id']
        response=self.client.post(f'/companies/{cid}/trial',headers=self.headers,json={'action':'extend','days':3})
        self.assertEqual(response.json()['trial_days'],10)
        self.assertIsNone(response.json()['trial_started_at'])
        headers,password=self.first_login()
        with b.SessionLocal() as db: start=db.get(b.Company,cid).trial_started_at
        self.client.post('/auth/login',json={'email':self.email,'password':password})
        with b.SessionLocal() as db:self.assertEqual(db.get(b.Company,cid).trial_started_at,start)
        self.assertEqual(self.client.post(f'/companies/{cid}/trial',headers=self.headers,json={'action':'extend','days':0}).status_code,422)
        self.payload['trial_days']=30
        self.assertEqual(self.client.post('/superadmin/onboard',headers=self.headers,json=self.payload).status_code,422)
