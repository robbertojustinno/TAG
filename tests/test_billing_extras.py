import secrets,uuid
from unittest.mock import patch
from fastapi import HTTPException
from test_billing_invoices import InvoiceTests
import billing_production_api as billing
from models import BillingProduction

class ExtraTests(InvoiceTests):
 def setUp(self):
  super().setUp()
  self.payload.update(purpose='extra',observations='Instalação de sensores',request_id=str(uuid.uuid4()))
  self.invoice['externalReference']=f'tagcheck-extra-{self.company}-{self.payload["request_id"]}'
 def test_extra_description_and_duplicate_prevention(self):
  def remote(method,path,payload=None):
   if method=='POST':
    self.assertEqual(payload['description'],'TagCheck — serviço extra (fora da mensalidade): Instalação de sensores')
    self.invoice['description']=payload['description']
   return self.provider(method,path,payload)
  with patch.object(billing,'provider',side_effect=remote) as calls:
   for request_id in (self.payload['request_id'],str(uuid.uuid4())):
    r=self.client.post(self.path+'/payments/new',headers=self.headers,json={**self.payload,'request_id':request_id})
    self.assertEqual(r.status_code,200,r.text)
   self.assertEqual(sum(c.args[0]=='POST' for c in calls.call_args_list),1)
   items=self.client.get(self.path+'/payments',headers=self.headers).json()
   self.assertIn('fora da mensalidade',items[0]['description'])
 def test_extra_requires_description(self):
  with patch.object(billing,'provider') as remote:
   r=self.client.post(self.path+'/payments/new',headers=self.headers,json={**self.payload,'observations':'  '})
   self.assertEqual(r.status_code,422);remote.assert_not_called()
 def test_extra_timeout_recovery(self):
  with patch.object(billing,'provider',side_effect=HTTPException(502,'Timeout')):
   self.assertEqual(self.client.post(self.path+'/payments/new',headers=self.headers,json=self.payload).status_code,502)
  with patch.object(billing,'provider',side_effect=self.provider) as calls:
   r=self.client.post(self.path+'/payments/extra/reconcile/'+self.payload['request_id'],headers=self.headers)
   self.assertEqual(r.status_code,200,r.text)
   self.assertFalse(any(c.args[0]=='POST' for c in calls.call_args_list))
 def test_extra_payment_keeps_monthly_unpaid(self):
  with patch.object(billing,'provider',side_effect=self.provider):
   self.assertEqual(self.client.post(self.path+'/payments/new',headers=self.headers,json=self.payload).status_code,200)
  self.invoice['status']='RECEIVED'
  with patch.object(billing,'provider',return_value=self.invoice):
   r=self.client.post('/webhooks/asaas/production',headers={'asaas-access-token':'s'*40},json={'id':'evt_'+secrets.token_hex(6),'payment':{'id':self.pid}})
   self.assertEqual(r.status_code,200,r.text)
  with __import__('test_stabilization').backend.SessionLocal() as db:
   self.assertEqual(db.get(BillingProduction,self.company).state,'awaiting_payment')
# Inherited replacement tests use the original fixture/payload instead.
for name in list(InvoiceTests.__dict__):
 if name.startswith('test_'):setattr(ExtraTests,name,None)
del InvoiceTests
