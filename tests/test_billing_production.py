import os,secrets,unittest
from datetime import date
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy import select
import test_stabilization as fixture
from models import BillingProduction, BillingProductionEvent
b=fixture.backend

class ProductionBillingTests(unittest.TestCase):
 def setUp(self):
  self.env=patch.dict(os.environ,{'ASAAS_PRODUCTION_ENABLED':'true','ASAAS_PRODUCTION_WEBHOOK_TOKEN':'x'*40});self.env.start();self.addCleanup(self.env.stop)
  self.client=TestClient(b.app);self.addCleanup(self.client.close)
  login=self.client.post('/auth/login',json={'username':fixture.ENV['ADMIN_USERNAME'],'password':fixture.ENV['ADMIN_PASSWORD']}).json()
  self.headers={'Authorization':'Bearer '+login['token']}
  self.company=self.client.post('/companies',headers=self.headers,json={'name':'Teste financeiro','slug':'billing-'+secrets.token_hex(6)}).json()['id']
  self.path=f'/companies/{self.company}/billing/production'
 def plan(self):
  r=self.client.put(self.path,headers=self.headers,json={'monthly_value':'99.90','billing_type':'UNDEFINED'})
  self.assertEqual(r.status_code,200,r.text)
 def test_configuration_roles_and_missing_credentials(self):
  self.plan()
  self.assertEqual(self.client.get(self.path).status_code,401)
  with patch.dict(os.environ,{'ASAAS_PRODUCTION_API_KEY':''}):
   r=self.client.post(self.path+'/subscribe',headers=self.headers,json={'cpf_cnpj':'12345678901','next_due_date':date.today().isoformat(),'confirm_real':True})
   self.assertEqual(r.status_code,503)
  self.assertEqual(self.client.put(self.path,headers=self.headers,json={'monthly_value':'0'}).status_code,422)
  self.assertEqual(self.client.put(self.path,headers=self.headers,json={'monthly_value':'1.234'}).status_code,422)
  self.assertTrue(self.client.get('/superadmin/billing/production/status',headers=self.headers).json()['production_enabled'])
 def test_subscription_duplicate_protection_and_invoice(self):
  self.plan()
  def remote(method,path,payload=None):
   if path=='/customers':return {'id':'cus_test'}
   if path=='/subscriptions':
    self.assertEqual(payload['externalReference'],f'tagcheck-production-{self.company}');self.assertNotIn('TESTE',payload['description']);self.assertEqual(payload['billingType'],'UNDEFINED');self.assertEqual(payload['cycle'],'MONTHLY')
    return {'id':'sub_test'}
   if path=='/subscriptions/sub_test/payments':return {'data':[{'id':'pay_test','status':'PENDING','invoiceUrl':'https://sandbox.asaas.com/i/test'}]}
   self.fail(path)
  import billing_production_api as billing_api
  with patch.dict(os.environ,{'ASAAS_PRODUCTION_API_KEY':'test-secret'}),patch.object(billing_api,'provider',side_effect=remote):
   payload={'cpf_cnpj':'12345678901','next_due_date':date.today().isoformat(),'confirm_real':True}
   first=self.client.post(self.path+'/subscribe',headers=self.headers,json=payload)
   self.assertEqual(first.status_code,200,first.text)
   self.assertEqual(self.client.post(self.path+'/subscribe',headers=self.headers,json=payload).status_code,409)
   self.assertEqual(self.client.get(self.path+'/payments',headers=self.headers).json()[0]['id'],'pay_test')
 def test_webhook_authentication_duplicate_and_sandbox_isolation(self):
  self.plan();suffix=secrets.token_hex(6);sid='sub_'+suffix;cid='cus_'+suffix;pid='pay_'+suffix
  with b.SessionLocal() as db:
   row=db.get(BillingProduction,self.company);row.customer_id=cid;row.subscription_id=sid
   company=db.get(b.Company,self.company);company.trial_days=7;db.commit()
  secret=secrets.token_hex(32);eid='evt_'+suffix
  payload={'id':eid,'event':'PAYMENT_RECEIVED','payment':{'id':pid,'status':'RECEIVED','value':0,'subscription':'untrusted'}}
  import billing_production_api as billing_api
  with patch.dict(os.environ,{'ASAAS_PRODUCTION_WEBHOOK_TOKEN':secret}),patch.object(billing_api,'provider',return_value={'id':pid,'subscription':sid,'customer':cid,'status':'RECEIVED','value':99.90}) as remote:
   self.assertEqual(self.client.post('/webhooks/asaas/production',json=payload).status_code,401)
   headers={'asaas-access-token':secret}
   response=self.client.post('/webhooks/asaas/production',headers=headers,json=payload)
   self.assertEqual(response.status_code,200,response.text)
   self.assertTrue(self.client.post('/webhooks/asaas/production',headers=headers,json=payload).json()['duplicate'])
   self.assertEqual(remote.call_count,1)
  with b.SessionLocal() as db:
   self.assertEqual(db.get(BillingProduction,self.company).state,'paid')
   self.assertEqual(db.get(b.Company,self.company).trial_days,7)
   self.assertIsNone(db.get(b.Company,self.company).trial_started_at)
 def test_unknown_remote_outcome_cannot_be_retried(self):
  self.plan()
  import billing_production_api as billing_api
  from fastapi import HTTPException
  with patch.dict(os.environ,{'ASAAS_PRODUCTION_API_KEY':'test-secret'}),patch.object(billing_api,'provider',side_effect=HTTPException(502,'Timeout')):
   payload={'cpf_cnpj':'12345678901','next_due_date':date.today().isoformat(),'confirm_real':True}
   self.assertEqual(self.client.post(self.path+'/subscribe',headers=self.headers,json=payload).status_code,502)
   self.assertEqual(self.client.post(self.path+'/subscribe',headers=self.headers,json=payload).status_code,409)
  with patch.object(billing_api,'provider',return_value={'data':[]}):
   r=self.client.post(self.path+'/reconcile',headers=self.headers,json={})
   self.assertEqual(r.json()['state'],'needs_review')

 def test_production_requires_confirmation_and_enabled_flag(self):
  self.plan()
  payload={'cpf_cnpj':'12345678901','next_due_date':date.today().isoformat()}
  self.assertEqual(self.client.post(self.path+'/subscribe',headers=self.headers,json=payload).status_code,422)
  payload['confirm_real']=True
  with patch.dict(os.environ,{'ASAAS_PRODUCTION_ENABLED':'false','ASAAS_PRODUCTION_API_KEY':'test-key'}):
   self.assertEqual(self.client.post(self.path+'/subscribe',headers=self.headers,json=payload).status_code,503)
  with patch.dict(os.environ,{'ASAAS_PRODUCTION_WEBHOOK_TOKEN':'','ASAAS_PRODUCTION_API_KEY':'test-key'}):
   self.assertEqual(self.client.post(self.path+'/subscribe',headers=self.headers,json=payload).status_code,503)
 def test_sandbox_records_are_not_used_for_live_billing(self):
  from models import BillingSandbox
  with b.SessionLocal() as db:
   db.add(BillingSandbox(company_id=self.company,monthly_value=10,state='paid_simulated',subscription_id='sub_sandbox'+secrets.token_hex(6)))
   db.commit()
  self.assertIsNone(self.client.get(self.path,headers=self.headers).json())
 def test_unrelated_amigopet_event_is_ignored(self):
  import billing_production_api as billing_api
  secret='x'*40
  with patch.object(billing_api,'provider',return_value={'id':'pay_other','subscription':'sub_amigopet','customer':'cus_other','value':10,'status':'RECEIVED'}):
   response=self.client.post('/webhooks/asaas/production',headers={'asaas-access-token':secret},json={'id':'evt_other','event':'PAYMENT_RECEIVED','payment':{'id':'pay_other'}})
   self.assertTrue(response.json()['ignored'])

 def test_reconcile_preserves_received_payment(self):
  self.plan()
  import billing_production_api as billing_api
  suffix=secrets.token_hex(6)
  with b.SessionLocal() as db:
   row=db.get(BillingProduction,self.company);row.customer_id='cus_'+suffix;row.subscription_id='sub_'+suffix;row.state='paid';db.commit()
  with patch.object(billing_api,'provider',return_value={'data':[{'id':'sub_'+suffix,'customer':'cus_'+suffix,'value':'99.90'}]}):
   response=self.client.post(self.path+'/reconcile',headers=self.headers,json={})
   self.assertEqual(response.json()['state'],'paid')
 def test_transport_uses_only_live_base_and_server_secret(self):
  import billing_production_api as billing_api
  from io import BytesIO
  with patch.dict(os.environ,{'ASAAS_PRODUCTION_API_KEY':'test-only-key'}),patch.object(billing_api,'urlopen',return_value=BytesIO(b'{"data":[]}')) as remote:
   billing_api.provider('GET','/customers?externalReference=test')
   req=remote.call_args.args[0]
   self.assertEqual(req.full_url,'https://api.asaas.com/v3/customers?externalReference=test')
   self.assertEqual(req.get_header('Access_token'),'test-only-key')
