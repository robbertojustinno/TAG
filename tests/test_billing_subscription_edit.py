import os,secrets,unittest
from datetime import date,timedelta
from decimal import Decimal
from unittest.mock import patch
from fastapi import HTTPException
import test_stabilization as fixture
from fastapi.testclient import TestClient
from models import BillingProduction
import billing_production_api as billing
b=fixture.backend
class SubscriptionEditTests(unittest.TestCase):
 def setUp(self):
  self.client=TestClient(b.app);self.addCleanup(self.client.close)
  token=self.client.post('/auth/login',json={'username':fixture.ENV['ADMIN_USERNAME'],'password':fixture.ENV['ADMIN_PASSWORD']}).json()['token']
  self.headers={'Authorization':'Bearer '+token}
  self.company=self.client.post('/companies',headers=self.headers,json={'name':'Cliente edição','slug':'edit-'+secrets.token_hex(6)}).json()['id']
  suffix=secrets.token_hex(6);self.sid='sub_'+suffix;self.cid='cus_'+suffix
  self.path=f'/companies/{self.company}/billing/production'
  with b.SessionLocal() as db:
   db.add(BillingProduction(company_id=self.company,monthly_value=10,billing_type='BOLETO',customer_id=self.cid,subscription_id=self.sid,state='awaiting_payment'));db.commit()
  self.remote={'id':self.sid,'customer':self.cid,'value':10,'billingType':'BOLETO','nextDueDate':(date.today()+timedelta(days=30)).isoformat(),'description':'TagCheck — assinatura mensal','cycle':'MONTHLY','status':'ACTIVE'}
  self.payload={'confirm_real':True,'monthly_value':'100.00','billing_type':'PIX','next_due_date':(date.today()+timedelta(days=40)).isoformat(),'description':'TagCheck — plano profissional','update_pending_payments':False,'expected_snapshot':billing.subscription_view(self.remote,type('Row',(),{'customer_id':self.cid,'subscription_id':self.sid})())['snapshot']}
  env=patch.dict(os.environ,{'ASAAS_PRODUCTION_ENABLED':'true','ASAAS_PRODUCTION_API_KEY':'test-only'});env.start();self.addCleanup(env.stop)
 def provider(self,method,path,payload=None):
  self.assertEqual(path,'/subscriptions/'+self.sid)
  if method=='PUT':
   self.assertNotIn('customer',payload);self.assertNotIn('externalReference',payload)
   self.remote.update(payload)
  return dict(self.remote)
 def test_get_reads_current_provider_without_writes(self):
  self.remote['value']=80
  with patch.object(billing,'provider',side_effect=self.provider) as remote:
   r=self.client.get(self.path+'/subscription',headers=self.headers)
   self.assertEqual(r.json()['monthly_value'],'80');self.assertEqual(remote.call_count,1)
   self.assertEqual(remote.call_args.args[0],'GET')
 def test_edit_future_only_and_pending_option(self):
  for pending in (False,True):
   self.payload['expected_snapshot']=billing.subscription_view(self.remote,type('Row',(),{'customer_id':self.cid,'subscription_id':self.sid})())['snapshot']
   self.payload['update_pending_payments']=pending
   with patch.object(billing,'provider',side_effect=self.provider) as remote:
    r=self.client.put(self.path+'/subscription',headers=self.headers,json=self.payload)
    self.assertEqual(r.status_code,200,r.text)
    put=[c for c in remote.call_args_list if c.args[0]=='PUT'];self.assertEqual(len(put),1)
    self.assertEqual(put[0].args[2]['updatePendingPayments'],pending)
   with b.SessionLocal() as db:
    row=db.get(BillingProduction,self.company);self.assertEqual(row.monthly_value,Decimal('100.00'));self.assertEqual(row.billing_type,'PIX')
 def test_stale_editor_and_wrong_tenant_cannot_write(self):
  for field,value in [('value',55),('customer','cus_someoneelse')]:
   changed=dict(self.remote);changed[field]=value
   with patch.object(billing,'provider',return_value=changed) as remote:
    r=self.client.put(self.path+'/subscription',headers=self.headers,json=self.payload)
    self.assertEqual(r.status_code,409,r.text);self.assertEqual(remote.call_count,1)
 def test_auth_and_input_validation(self):
  with patch.object(billing,'provider') as remote:
   self.assertEqual(self.client.put(self.path+'/subscription',json=self.payload).status_code,401)
   for field,value in [('confirm_real',False),('monthly_value','0'),('description','x'*501),('next_due_date',(date.today()-timedelta(days=1)).isoformat())]:
    invalid=dict(self.payload);invalid[field]=value
    self.assertEqual(self.client.put(self.path+'/subscription',headers=self.headers,json=invalid).status_code,422)
   remote.assert_not_called()
 def test_uncertain_edit_blocks_retry_until_reconciled(self):
  with patch.object(billing,'provider',side_effect=[dict(self.remote),HTTPException(502,'Timeout')]):
   r=self.client.put(self.path+'/subscription',headers=self.headers,json=self.payload);self.assertEqual(r.status_code,502)
  with patch.object(billing,'provider') as remote:
   self.assertEqual(self.client.put(self.path+'/subscription',headers=self.headers,json=self.payload).status_code,409);remote.assert_not_called()
  self.remote.update(value=100,billingType='PIX')
  with patch.object(billing,'provider',return_value=dict(self.remote)):
   r=self.client.post(self.path+'/reconcile',headers=self.headers,json={});self.assertEqual(r.status_code,200,r.text)
   self.assertEqual(Decimal(str(r.json()['monthly_value'])),Decimal('100'))
 def test_old_invoice_is_accepted_after_price_changes(self):
  with b.SessionLocal() as db:
   db.get(BillingProduction,self.company).monthly_value=100;db.commit()
  actual={'id':'pay_'+secrets.token_hex(6),'subscription':self.sid,'customer':self.cid,'value':10,'status':'RECEIVED'}
  secret='s'*40
  with patch.dict(os.environ,{'ASAAS_PRODUCTION_WEBHOOK_TOKEN':secret}),patch.object(billing,'provider',return_value=actual):
   r=self.client.post('/webhooks/asaas/production',headers={'asaas-access-token':secret},json={'id':'evt_'+secrets.token_hex(6),'payment':{'id':actual['id']}})
   self.assertEqual(r.status_code,200,r.text)
  with b.SessionLocal() as db:self.assertEqual(db.get(BillingProduction,self.company).state,'paid')
