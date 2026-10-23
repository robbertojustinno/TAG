"""Production billing isolated from sandbox. Access remains managed by Super Admin."""
import hashlib, hmac, json, os, re
from datetime import date
from decimal import Decimal
from typing import Literal
from urllib.request import Request as URLRequest, urlopen
from urllib.error import HTTPError, URLError
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import Field
from sqlalchemy import select
if __package__:
    from .models import Company, BillingProduction, BillingProductionEvent
    from .admin_api import Input, commit
else:
    from models import Company, BillingProduction, BillingProductionEvent
    from admin_api import Input, commit

BASE='https://api.asaas.com/v3'
class BillingPlan(Input):
    monthly_value: Decimal = Field(gt=0, le=100000, max_digits=12, decimal_places=2)
    billing_type: Literal['UNDEFINED','BOLETO','PIX','CREDIT_CARD'] = 'UNDEFINED'
class CreateSubscription(Input):
    confirm_real: Literal[True]
    cpf_cnpj: str = Field(pattern=r'^(?:[0-9]{11}|[0-9]{14})$')
    next_due_date: date

class EditSubscription(BillingPlan):
    confirm_real: Literal[True]
    next_due_date: date
    description: str = Field(max_length=500)
    update_pending_payments: bool = False
    expected_snapshot: str = Field(pattern=r'^[a-f0-9]{64}$')

def subscription_view(sub, row):
    if sub.get('id') != row.subscription_id or sub.get('customer') != row.customer_id:
        raise HTTPException(409,'A assinatura não corresponde à empresa selecionada.')
    try:
        value=Decimal(str(sub['value']))
        if not value.is_finite() or value<=0:raise ValueError()
        next_due=date.fromisoformat(sub['nextDueDate']).isoformat()
        kind=sub['billingType']
        if kind not in ('UNDEFINED','BOLETO','PIX','CREDIT_CARD'):raise ValueError()
    except (ValueError,KeyError,TypeError,ArithmeticError):
        raise HTTPException(502,'Dados incompletos na assinatura do Asaas.') from None
    result={'subscription_id':sub['id'],'monthly_value':str(value),'billing_type':kind,
        'next_due_date':next_due,'description':sub.get('description') or '',
        'cycle':sub.get('cycle'),'status':sub.get('status')}
    result['snapshot']=hashlib.sha256(json.dumps(result,sort_keys=True).encode()).hexdigest()
    return result

def payment_state(status):
    return ('paid' if status in ('RECEIVED','CONFIRMED','RECEIVED_IN_CASH') else
        'refunded' if status in ('REFUNDED','REFUND_REQUESTED','CHARGEBACK_REQUESTED','CHARGEBACK_DISPUTE') else
        'overdue' if status=='OVERDUE' else 'awaiting_payment')

def credentials():
    if os.getenv('ASAAS_PRODUCTION_ENABLED','').lower() != 'true':
        raise HTTPException(503,'Cobranças reais ainda não habilitadas no servidor.')
    key=os.getenv('ASAAS_PRODUCTION_API_KEY','').strip()
    if not key:
        raise HTTPException(503,'Asaas de produção não conectado. Configure ASAAS_PRODUCTION_API_KEY no servidor.')
    return key

def provider(method,path,payload=None):
    req=URLRequest(BASE+path,method=method,data=json.dumps(payload).encode() if payload is not None else None,
        headers={'access_token':credentials(),'Content-Type':'application/json','User-Agent':'TagCheck/2.0'})
    try:
        with urlopen(req,timeout=30) as response:return json.load(response)
    except HTTPError:
        raise HTTPException(502,'Asaas recusou a operação. Confira os dados e o painel do Asaas antes de tentar novamente.') from None
    except (URLError,TimeoutError,ValueError):
        raise HTTPException(502,'Resultado do Asaas não confirmado. Use Conciliar antes de tentar novamente.') from None

def view(row):
    if row is None:return None
    return {'company_id':row.company_id,'monthly_value':row.monthly_value,'billing_type':row.billing_type,
        'customer_id':row.customer_id,'subscription_id':row.subscription_id,'state':row.state,
        'last_payment_status':row.last_payment_status,'environment':'production'}

def safe_id(value,prefix):
    if not isinstance(value,str) or not re.fullmatch(prefix+r'_[A-Za-z0-9]+',value):
        raise HTTPException(502,'Identificação inválida na resposta do Asaas.')
    return value

def build_production_billing_router(auth):
    router=APIRouter()
    @router.get('/superadmin/billing/production/status')
    def connection(_=Depends(auth.superadmin)):
        return {'environment':'production','api_configured':bool(os.getenv('ASAAS_PRODUCTION_API_KEY')),
            'webhook_configured':len(os.getenv('ASAAS_PRODUCTION_WEBHOOK_TOKEN',''))>=32,'production_enabled':os.getenv('ASAAS_PRODUCTION_ENABLED','').lower()=='true'}

    @router.get('/companies/{company_id}/billing/production')
    def read(company_id:int,_=Depends(auth.superadmin)):
        with auth.sessions() as db:
            if not db.get(Company,company_id):raise HTTPException(404,'Empresa não encontrada.')
            return view(db.get(BillingProduction,company_id))

    @router.put('/companies/{company_id}/billing/production')
    def configure(company_id:int,payload:BillingPlan,_=Depends(auth.superadmin)):
        with auth.sessions() as db:
            company=db.scalar(select(Company).where(Company.id==company_id).with_for_update())
            if not company:raise HTTPException(404,'Empresa não encontrada.')
            row=db.get(BillingProduction,company_id)
            if row and row.state!='draft':raise HTTPException(409,'Uma operação já foi iniciada. Concilie a assinatura antes de alterar o plano.')
            if not row:row=BillingProduction(company_id=company_id);db.add(row)
            row.monthly_value=payload.monthly_value;row.billing_type=payload.billing_type
            commit(db);return view(row)

    @router.post('/companies/{company_id}/billing/production/subscribe')
    def subscribe(company_id:int,payload:CreateSubscription,_=Depends(auth.superadmin)):
        credentials()
        if len(os.getenv('ASAAS_PRODUCTION_WEBHOOK_TOKEN',''))<32:
            raise HTTPException(503,'Configure o webhook de produção antes de gerar cobranças reais.')
        if payload.next_due_date<date.today():raise HTTPException(422,'Escolha vencimento a partir de hoje.')
        # Serialize and persist intent before remote writes. Uncertain results are
        # reconciled, never blindly retried; this prevents double subscriptions.
        with auth.sessions() as db:
            company=db.scalar(select(Company).where(Company.id==company_id).with_for_update())
            if not company:raise HTTPException(404,'Empresa não encontrada.')
            row=db.get(BillingProduction,company_id)
            if not row:raise HTTPException(409,'Salve primeiro o valor e a forma de pagamento.')
            if row.state!='draft':raise HTTPException(409,'Operação já iniciada. Use Conciliar assinatura.')
            row.state='creating';commit(db)
            if not row.customer_id:
                result=provider('POST','/customers',{'name':company.name,'cpfCnpj':payload.cpf_cnpj,
                    'externalReference':f'tagcheck-production-{company_id}','notificationDisabled':True})
                row.customer_id=safe_id(result.get('id'),'cus');commit(db)
            result=provider('POST','/subscriptions',{'customer':row.customer_id,'billingType':row.billing_type,
                'value':float(row.monthly_value),'nextDueDate':payload.next_due_date.isoformat(),'cycle':'MONTHLY',
                'description':'TagCheck — assinatura mensal',
                'externalReference':f'tagcheck-production-{company_id}'})
            row.subscription_id=safe_id(result.get('id'),'sub');row.state='awaiting_payment';commit(db)
            return view(row)

    @router.get('/companies/{company_id}/billing/production/subscription')
    def subscription(company_id:int,_=Depends(auth.superadmin)):
        with auth.sessions() as db:
            row=db.get(BillingProduction,company_id)
            if not row or not row.subscription_id:raise HTTPException(404,'Assinatura não encontrada.')
            return subscription_view(provider('GET',f'/subscriptions/{safe_id(row.subscription_id,"sub")}'),row)

    @router.put('/companies/{company_id}/billing/production/subscription')
    def edit_subscription(company_id:int,payload:EditSubscription,_=Depends(auth.superadmin)):
        credentials()
        if payload.next_due_date<date.today():raise HTTPException(422,'Escolha vencimento a partir de hoje.')
        with auth.sessions() as db:
            row=db.scalar(select(BillingProduction).where(BillingProduction.company_id==company_id).with_for_update())
            if not row or not row.subscription_id:raise HTTPException(404,'Assinatura não encontrada.')
            if row.state in ('creating','updating','needs_review'):
                raise HTTPException(409,'Há uma operação pendente. Use Conciliar assinatura antes de editar.')
            path=f'/subscriptions/{safe_id(row.subscription_id,"sub")}'
            current=subscription_view(provider('GET',path),row)
            if current['snapshot']!=payload.expected_snapshot:
                raise HTTPException(409,'A assinatura mudou no Asaas. Reabra a edição para conferir os dados atuais.')
            if current['cycle']!='MONTHLY' or current['status']!='ACTIVE':
                raise HTTPException(409,'A edição requer assinatura mensal ativa. Confira a assinatura no Asaas.')
            # Hold the row lock through the remote edit. Persist an uncertain outcome
            # before returning an error; subsequent edits require reconciliation.
            row.state='updating';db.flush()
            try:
                provider('PUT',path,{'value':float(payload.monthly_value),'billingType':payload.billing_type,
                    'nextDueDate':payload.next_due_date.isoformat(),'description':payload.description,
                    'updatePendingPayments':payload.update_pending_payments})
                actual=subscription_view(provider('GET',path),row)
                if (Decimal(actual['monthly_value'])!=payload.monthly_value or actual['billing_type']!=payload.billing_type
                        or actual['next_due_date']!=payload.next_due_date.isoformat() or actual['description']!=payload.description):
                    raise HTTPException(502,'A alteração não foi confirmada integralmente. Use Conciliar assinatura.')
            except HTTPException:
                commit(db)
                raise
            row.monthly_value=Decimal(actual['monthly_value']);row.billing_type=actual['billing_type']
            row.state=payment_state(row.last_payment_status);commit(db)
            return view(row)

    @router.post('/companies/{company_id}/billing/production/reconcile')
    def reconcile(company_id:int,_=Depends(auth.superadmin)):
        with auth.sessions() as db:
            db.scalar(select(Company).where(Company.id==company_id).with_for_update())
            row=db.scalar(select(BillingProduction).where(BillingProduction.company_id==company_id).with_for_update())
            if not row:raise HTTPException(404,'Plano não encontrado.')
            if row.subscription_id:
                sub=subscription_view(provider('GET',f'/subscriptions/{safe_id(row.subscription_id,"sub")}'),row)
                row.monthly_value=Decimal(sub['monthly_value']);row.billing_type=sub['billing_type']
                row.state=payment_state(row.last_payment_status);commit(db)
                return view(row)
            ref=f'tagcheck-production-{company_id}'
            if not row.customer_id:
                customers=provider('GET','/customers?externalReference='+ref).get('data',[])
                if len(customers)>1:raise HTTPException(409,'Há clientes duplicados no Asaas. Confira o painel.')
                if customers:row.customer_id=safe_id(customers[0].get('id'),'cus')
            subs=provider('GET','/subscriptions?externalReference='+ref).get('data',[])
            if len(subs)>1:raise HTTPException(409,'Há assinaturas duplicadas no Asaas. Confira o painel.')
            if subs:
                sub=subs[0]
                if sub.get('customer')!=row.customer_id or Decimal(str(sub.get('value'))) != row.monthly_value:
                    raise HTTPException(409,'Assinatura encontrada diverge do plano salvo.')
                row.subscription_id=safe_id(sub.get('id'),'sub')
                if row.state not in ('paid','refunded','overdue'):row.state='awaiting_payment'
            else:row.state='draft' if row.state=='draft' else 'needs_review'
            commit(db);return view(row)

    @router.get('/companies/{company_id}/billing/production/payments')
    def payments(company_id:int,_=Depends(auth.superadmin)):
        with auth.sessions() as db:
            row=db.get(BillingProduction,company_id)
            if not row or not row.subscription_id:return []
            data=provider('GET',f'/subscriptions/{row.subscription_id}/payments').get('data',[])
            return [{'id':p.get('id'),'status':p.get('status'),'value':p.get('value'),
                     'due_date':p.get('dueDate'),'invoice_url':p.get('invoiceUrl')} for p in data]

    @router.post('/webhooks/asaas/production')
    async def webhook(request:Request):
        secret=os.getenv('ASAAS_PRODUCTION_WEBHOOK_TOKEN','')
        if len(secret)<32:raise HTTPException(503,'Webhook de produção não configurado.')
        if not hmac.compare_digest(request.headers.get('asaas-access-token',''),secret):raise HTTPException(401,'Webhook não autorizado.')
        raw=await request.body()
        if len(raw)>65536:raise HTTPException(413,'Evento muito grande.')
        try:
            event=json.loads(raw);eid=event['id'];payment=event['payment'];pid=payment['id']
            if not isinstance(eid,str) or not 1<=len(eid)<=200:raise ValueError()
            safe_id(pid,'pay')
        except (ValueError,KeyError,TypeError):raise HTTPException(422,'Evento de cobrança inválido.') from None
        with auth.sessions() as db:
            if db.get(BillingProductionEvent,eid):return {'ok':True,'duplicate':True}
            # Do not trust amounts, tenant identifiers or status in callbacks.
            actual=provider('GET',f'/payments/{pid}')
            row=db.scalar(select(BillingProduction).where(BillingProduction.subscription_id==actual.get('subscription')).with_for_update()) if actual.get('subscription') else None
            if not row:return {'ok':True,'ignored':True}
            if row.state=='updating':raise HTTPException(409,'Alteração da assinatura pendente de conciliação.')
            # Earlier invoices can have the price from before a subscription edit.
            # The authenticated provider lookup, stored subscription and customer establish ownership.
            if actual.get('customer')!=row.customer_id:
                raise HTTPException(409,'Cobrança divergente do plano de produção.')
            if actual.get('id')!=pid:raise HTTPException(409,'Identificação da cobrança divergente.')
            status=actual.get('status','UNKNOWN')
            row.last_payment_status=status
            row.state=payment_state(status)
            db.add(BillingProductionEvent(id=eid,company_id=row.company_id,payment_id=pid,status=status))
            commit(db)
            # Payment state is recorded; activation remains an explicit Super Admin action.
            return {'ok':True,'environment':'production'}
    return router
