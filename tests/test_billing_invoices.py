import os,secrets,unittest
from datetime import date,timedelta
from decimal import Decimal
from unittest.mock import patch
from fastapi import HTTPException
from fastapi.testclient import TestClient
import test_stabilization as fixture
from models import BillingProduction,BillingProductionInvoice
import billing_production_api as billing
b=fixture.backend
class InvoiceTests(unittest.TestCase):
 def setUp(self):
  self.client=TestClient(b.app);self.addCleanup(self.client.close)
  token=self.client.post('/auth/login',json={'username':fixture.ENV['ADMIN_USERNAME'],'password':fixture.ENV['ADMIN_PASSWORD']}).json()['token'];self.headers={'Authorization':'Bearer '+token}
  self.company=self.client.post('/companies',headers=self.headers,json={'name':'Reposição','slug':'invoice-'+secrets.token_hex(6)}).json()['id']
  suffix=secrets.token_hex(6);self.sid='sub_'+suffix;self.cid='cus_'+suffix;self.pid='pay_'+suffix
  self.path=f'/companies/{self.company}/billing/production';self.due=(date.today()+timedelta(days=10)).isoformat();self.period=self.due[:7]
  self.reference=f'tagcheck-reissue-{self.company}-{self.period}'
  self.payload={'confirm_real':True,'value':'100.00','due_date':self.due}
  with b.SessionLocal() as db:db.add(BillingProduction(company_id=self.company,monthly_value=100,billing_type='BOLETO',customer_id=self.cid,subscription_id=self.sid,state='awaiting_payment'));db.commit()
  env=patch.dict(os.environ,{'ASAAS_PRODUCTION_ENABLED':'true','ASAAS_PRODUCTION_API_KEY':'test','ASAAS_PRODUCTION_WEBHOOK_TOKEN':'s'*40});env.start();self.addCleanup(env.stop)
  self.invoice={'id':self.pid,'customer':self.cid,'externalReference':self.reference,'value':100,'dueDate':self.due,'billingType':'BOLETO','status':'PENDING','invoiceUrl':'https://www.asaas.com/i/test','deleted':False}
 def provider(self,method,path,payload=None):
  if path=='/subscriptions/'+self.sid:return {'id':self.sid,'customer':self.cid,'value':100,'nextDueDate':(date.today()+timedelta(days=70)).isoformat(),'billingType':'BOLETO','cycle':'MONTHLY','status':'ACTIVE'}
  if path.startswith('/subscriptions/'+self.sid+'/payments'):return {'data':[]}
  if method=='POST' and path=='/payments':
   self.assertEqual(payload['customer'],self.cid);self.assertEqual(payload['billingType'],'BOLETO');self.assertNotIn('subscription',payload)
   return dict(self.invoice)
  if path=='/payments/'+self.pid:return dict(self.invoice)
  if path.startswith('/payments?externalReference='):return {'data':[dict(self.invoice)]}
  self.fail((method,path))
 def test_new_invoice_durable_single_emission_and_listing(self):
  with patch.object(billing,'provider',side_effect=self.provider) as remote:
   r=self.client.post(self.path+'/payments/new',headers=self.headers,json=self.payload);self.assertEqual(r.status_code,200,r.text)
   self.assertEqual(self.client.post(self.path+'/payments/new',headers=self.headers,json=self.payload).status_code,409)
   listed=self.client.get(self.path+'/payments',headers=self.headers);self.assertEqual(listed.json()[0]['id'],self.pid)
   self.assertEqual(len([c for c in remote.call_args_list if c.args[0]=='POST']),1)
 def test_existing_subscription_invoice_blocks_duplicate_month(self):
  def remote(method,path,payload=None):
   if '/payments?' in path:return {'data':[{'id':'pay_old','dueDate':self.due,'deleted':False,'status':'PENDING'}]}
   return self.provider(method,path,payload)
  with patch.object(billing,'provider',side_effect=remote) as calls:
   self.assertEqual(self.client.post(self.path+'/payments/new',headers=self.headers,json=self.payload).status_code,409)
   self.assertFalse(any(c.args[0]=='POST' for c in calls.call_args_list))
 def test_unknown_outcome_reconciles_without_another_creation(self):
  def remote(method,path,payload=None):
   if method=='POST':raise HTTPException(502,'Timeout')
   return self.provider(method,path,payload)
  with patch.object(billing,'provider',side_effect=remote):self.assertEqual(self.client.post(self.path+'/payments/new',headers=self.headers,json=self.payload).status_code,502)
  with patch.object(billing,'provider',side_effect=self.provider):
   self.assertEqual(self.client.post(self.path+'/payments/new',headers=self.headers,json=self.payload).status_code,409)
   r=self.client.post(self.path+'/payments/reconcile/'+self.period,headers=self.headers,json={});self.assertEqual(r.status_code,200,r.text)
  with b.SessionLocal() as db:self.assertEqual(db.get(BillingProductionInvoice,(self.company,self.period)).payment_id,self.pid)
 def test_restore_validates_ownership_and_only_calls_restore_once(self):
  self.invoice['subscription']=self.sid;self.invoice['deleted']=True
  def remote(method,path,payload=None):
   if path.endswith('/restore'):self.invoice['deleted']=False;return dict(self.invoice)
   return self.provider(method,path,payload)
  with patch.object(billing,'provider',side_effect=remote) as calls:
   payload={'confirm_real':True,'payment_id':self.pid}
   for _ in range(2):self.assertEqual(self.client.post(self.path+'/payments/restore',headers=self.headers,json=payload).status_code,200)
   self.assertEqual(len([c for c in calls.call_args_list if c.args[0]=='POST']),1)
  self.invoice['customer']='cus_other'
  with patch.object(billing,'provider',side_effect=remote) as calls:
   self.assertEqual(self.client.post(self.path+'/payments/restore',headers=self.headers,json=payload).status_code,409)
   self.assertFalse(any(c.args[0]=='POST' for c in calls.call_args_list))
 def test_replacement_payment_webhook_updates_correct_company(self):
  with b.SessionLocal() as db:db.add(BillingProductionInvoice(company_id=self.company,period=self.period,reference=self.reference,payment_id=self.pid,state='created'));db.commit()
  self.invoice['status']='RECEIVED'
  with patch.object(billing,'provider',return_value=dict(self.invoice)):
   r=self.client.post('/webhooks/asaas/production',headers={'asaas-access-token':'s'*40},json={'id':'evt_'+secrets.token_hex(6),'payment':{'id':self.pid}});self.assertEqual(r.status_code,200,r.text)
  with b.SessionLocal() as db:self.assertEqual(db.get(BillingProduction,self.company).state,'paid')
 def test_auth_confirmation_and_date(self):
  with patch.object(billing,'provider') as remote:
   self.assertEqual(self.client.post(self.path+'/payments/new',json=self.payload).status_code,401)
   for changes in ({'confirm_real':False},{'value':0},{'due_date':(date.today()-timedelta(days=1)).isoformat()}):
    self.assertEqual(self.client.post(self.path+'/payments/new',headers=self.headers,json={**self.payload,**changes}).status_code,422)
   remote.assert_not_called()
