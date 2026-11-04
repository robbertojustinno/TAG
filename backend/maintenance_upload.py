"""Tenant-scoped XLS/XLSX preview and atomic, non-destructive reconciliation."""
import hashlib
import json
import unicodedata
import zipfile
from datetime import date, datetime, timedelta, timezone
from io import BytesIO
import jwt
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select, update, func
from sqlalchemy.exc import IntegrityError
if __package__:
    from .models import Company, Equipment, utcnow
    from .maintenance_api import MaintenancePlan, MaintenanceExecution, PlanInput
else:
    from models import Company, Equipment, utcnow
    from maintenance_api import MaintenancePlan, MaintenanceExecution, PlanInput

MAX_BYTES=8*1024*1024
MAX_ROWS=2000
FIELDS={'codigo atividade':'code','codigo da atividade':'code','tag':'tag','equipamento':'equipment_name',
        'oficina':'workshop','oficina / setor':'workshop','local':'location','localizacao':'location',
        'tipo':'equipment_type','atividade resumida':'activity','responsavel':'responsible',
        'ultima execucao':'last_execution','intervalo (dias)':'interval_days','observacoes':'notes'}

def normalized(value):
    return ' '.join(''.join(c for c in unicodedata.normalize('NFKD',str(value or '')) if not unicodedata.combining(c)).lower().split())

def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,default=str).encode()).hexdigest()

def parse_workbook(raw,filename):
    extension=filename.lower().rsplit('.',1)[-1]
    try:
        if extension=='xls':
            import xlrd
            book=xlrd.open_workbook(file_contents=raw,on_demand=True)
            sheet=book.sheet_by_name('Cronograma') if 'Cronograma' in book.sheet_names() else book.sheet_by_index(0)
            if sheet.ncols>80: raise ValueError('Use até 80 colunas no Cronograma.')
            if sheet.nrows>MAX_ROWS+100: raise ValueError('Limite de 2.000 linhas excedido.')
            matrix=[sheet.row_values(i) for i in range(sheet.nrows)]
            serial_date=lambda v:xlrd.xldate_as_datetime(v,book.datemode).date()
        elif extension=='xlsx':
            from openpyxl import load_workbook
            with zipfile.ZipFile(BytesIO(raw)) as archive:
                if sum(i.file_size for i in archive.infolist())>40*1024*1024: raise ValueError('Conteúdo descompactado excede o limite.')
            book=load_workbook(BytesIO(raw),read_only=True,data_only=True,keep_links=False)
            sheet=book['Cronograma'] if 'Cronograma' in book.sheetnames else book.worksheets[0]
            matrix=[]
            for row in sheet.iter_rows(max_col=80,values_only=True):
                matrix.append(list(row))
                if len(matrix)>MAX_ROWS+100: raise ValueError('Limite de 2.000 linhas excedido.')
            from openpyxl.utils.datetime import from_excel
            serial_date=lambda v:from_excel(v,book.epoch).date()
            book.close()
        else: raise ValueError('Envie uma planilha .xls ou .xlsx.')
        header=None
        for i,row in enumerate(matrix[:30]):
            mapping={j:FIELDS[normalized(v)] for j,v in enumerate(row) if normalized(v) in FIELDS}
            if {'code','tag','equipment_name','activity','responsible','interval_days'}.issubset(mapping.values()):
                header=i;break
        if header is None: raise ValueError('Cabeçalhos do Cronograma não encontrados. Use o modelo do TagCheck.')
        rows=[];errors=[];codes=set();ignored=0
        for index,row in enumerate(matrix[header+1:],header+2):
            values={name:row[j] if j<len(row) else None for j,name in mapping.items()}
            if not str(values.get('tag') or '').strip() and not str(values.get('equipment_name') or '').strip():
                ignored+=1;continue
            try:
                for key in values:
                    if key not in ('last_execution','interval_days'): values[key]=str(values[key] or '').strip()
                values['tag']=values['tag'].upper();values['code']=values['code'].upper()
                if not values['tag'] or len(values['tag'])>200 or not values['equipment_name']: raise ValueError('TAG e equipamento são obrigatórios.')
                if values['code'] in codes: raise ValueError('Código de atividade repetido na planilha.')
                codes.add(values['code'])
                interval=values['interval_days']
                number=float(str(interval).replace(',','.'))
                if not number.is_integer(): raise ValueError('Intervalo deve ser um número inteiro de dias.')
                values['interval_days']=int(number)
                day=values.get('last_execution')
                if isinstance(day,datetime): day=day.date()
                elif isinstance(day,(int,float)): day=serial_date(day)
                elif day:
                    text=str(day).strip()
                    try: day=date.fromisoformat(text[:10])
                    except ValueError: day=datetime.strptime(text,'%d/%m/%Y').date()
                else: day=None
                values['last_execution']=day.isoformat() if day else None
                plan_values={k:v for k,v in values.items() if k not in ('tag','equipment_name')}
                PlanInput(equipment_id=1,equipment_label=values['equipment_name'],**plan_values)
                values['sheet_row']=index;rows.append(values)
            except (ValueError,TypeError,OverflowError):
                errors.append(f'Linha {index}: confira código único, TAG, equipamento, atividade, responsável, data e intervalo inteiro entre 1 e 36.500 dias.')
        if errors: raise HTTPException(422,{'message':'Planilha com erros. Nenhum dado foi gravado.','errors':errors[:50]})
        if not rows: raise ValueError('Nenhum instrumento preenchido foi encontrado.')
        if len(rows)>MAX_ROWS: raise ValueError('Limite de 2.000 atividades excedido.')
        return rows,ignored
    except HTTPException: raise
    except Exception as error:
        message=str(error) if isinstance(error,ValueError) else 'Arquivo inválido, protegido ou incompatível. Salve como .xls ou .xlsx e tente novamente.'
        raise HTTPException(422,message) from None

def reconciliation(db,company_id,rows):
    assets={};plans={};errors=[]
    for e in db.scalars(select(Equipment).where(Equipment.company_id==company_id)):
        key=e.tag.strip().upper()
        if key in assets: errors.append('Há TAGs duplicadas no cadastro da empresa; regularize antes de importar.')
        assets[key]=e
    for p in db.scalars(select(MaintenancePlan).where(MaintenancePlan.company_id==company_id)):
        key=p.code.strip().upper()
        if key in plans: errors.append('Há códigos de plano duplicados na empresa; regularize antes de importar.')
        plans[key]=p
    with_history=set(db.scalars(select(MaintenanceExecution.plan_id).where(MaintenanceExecution.company_id==company_id)))
    items=[];state=[];new_tags=set();existing_tags=set()
    for row in rows:
        e=assets.get(row['tag']);p=plans.get(row['code'])
        values={k:v for k,v in row.items() if k not in ('tag','equipment_name','sheet_row')}
        values['equipment_label']=row['equipment_name']
        old=json.loads(p.data) if p else {}
        if p and (not e or p.equipment_id!=e.id): errors.append(f"Linha {row['sheet_row']}: código {row['code']} já pertence a outra TAG. Confira a planilha.")
        if p and p.id in with_history and 'last_execution' in values and old.get('last_execution')!=values.get('last_execution'):
            errors.append(f"Linha {row['sheet_row']}: a última execução possui histórico. Atualize-a por Registrar execução.")
        changes=[k for k,v in values.items() if old.get(k)!=v] if p else list(values)
        action='novo' if p is None else 'atualizar' if changes else 'sem alteração'
        if e: existing_tags.add(row['tag'])
        else: new_tags.add(row['tag'])
        state.append({'tag':row['tag'],'equipment_id':e.id if e else None,'plan_id':p.id if p else None,'revision':p.revision if p else None,'data':p.data if p else None,'has_history':bool(p and p.id in with_history)})
        items.append({'row':row['sheet_row'],'code':row['code'],'tag':row['tag'],'equipment_name':row['equipment_name'],'instrument':'existente' if e else 'novo','action':action,'changed_fields':changes,'values':values})
    return {'items':items,'errors':list(dict.fromkeys(errors)),'state_hash':digest(state),'summary':{'activities':len(items),'new_instruments':len(new_tags),'existing_instruments':len(existing_tags),'new_plans':sum(i['action']=='novo' for i in items),'updated_plans':sum(i['action']=='atualizar' for i in items),'unchanged_plans':sum(i['action']=='sem alteração' for i in items)}}

def build_maintenance_upload_router(auth):
    router=APIRouter(prefix='/maintenance/import',tags=['maintenance'])
    def editor(ctx=Depends(auth.current)):
        if not ctx.is_superadmin and ctx.role not in ('company_admin','supervisor'): raise HTTPException(403,'Somente administrador ou supervisor pode importar planilhas.')
        return ctx
    async def read(file):
        raw=await file.read(MAX_BYTES+1)
        if len(raw)>MAX_BYTES: raise HTTPException(413,'Planilha excede 8 MB.')
        return parse_workbook(raw,file.filename or '')
    @router.post('/preview')
    async def preview(file:UploadFile=File(...),ctx=Depends(editor)):
        rows,ignored=await read(file)
        with auth.sessions() as db: report=reconciliation(db,ctx.company_id,rows)
        token=None
        if not report['errors']:
            token=jwt.encode({'aud':'tagcheck:maintenance-import','company_id':ctx.company_id,'user_id':ctx.user_id,'rows_hash':digest(rows),'state_hash':report['state_hash'],'exp':datetime.now(timezone.utc)+timedelta(minutes=10)},auth.key,algorithm='HS256')
        return {'summary':report['summary'],'items':[{k:v for k,v in i.items() if k!='values'} for i in report['items']],'errors':report['errors'],'ignored_rows':ignored,'preview_token':token}
    @router.post('/apply')
    async def apply(file:UploadFile=File(...),preview_token:str=Form(...),ctx=Depends(editor)):
        rows,ignored=await read(file)
        try:
            claims=jwt.decode(preview_token,auth.key,algorithms=['HS256'],audience='tagcheck:maintenance-import',options={'require':['exp','company_id','user_id','rows_hash','state_hash']})
            if claims['company_id']!=ctx.company_id or claims['user_id']!=ctx.user_id or claims['rows_hash']!=digest(rows): raise ValueError()
        except (jwt.PyJWTError,ValueError): raise HTTPException(409,'Prévia expirada ou diferente do arquivo/empresa. Confira a planilha novamente.') from None
        try:
            with auth.sessions.begin() as db:
                db.execute(select(Company.id).where(Company.id==ctx.company_id).with_for_update()).scalar_one()
                report=reconciliation(db,ctx.company_id,rows)
                if report['errors'] or claims['state_hash']!=report['state_hash']: raise HTTPException(409,'Cadastros ou planos mudaram desde a prévia. Confira a planilha novamente.')
                assets={e.tag.strip().upper():e for e in db.scalars(select(Equipment).where(Equipment.company_id==ctx.company_id))}
                plans={p.code.strip().upper():p for p in db.scalars(select(MaintenancePlan).where(MaintenancePlan.company_id==ctx.company_id))}
                for row,item in zip(rows,report['items']):
                    e=assets.get(row['tag'])
                    if e is None:
                        e=Equipment(company_id=ctx.company_id,tag=row['tag'],name=row['equipment_name'],photo='',sector=row.get('workshop',''),location=row.get('location',''),equipment_type=row.get('equipment_type',''),status='Ativo',notes='Importado do Cronograma de manutenção preventiva.')
                        db.add(e);db.flush();assets[row['tag']]=e
                    p=plans.get(row['code']);values=item['values']
                    if p is None:
                        plan=PlanInput(equipment_id=e.id,**values)
                        db.add(MaintenancePlan(company_id=ctx.company_id,equipment_id=e.id,code=plan.code,data=plan.model_dump_json(),updated_by=ctx.user_id))
                    elif item['action']=='atualizar':
                        merged={**json.loads(p.data),**values};validated=PlanInput(**merged)
                        result=db.execute(update(MaintenancePlan).where(MaintenancePlan.id==p.id,MaintenancePlan.company_id==ctx.company_id,MaintenancePlan.revision==p.revision).values(data=validated.model_dump_json(),revision=p.revision+1,updated_by=ctx.user_id,updated_at=utcnow()))
                        if result.rowcount!=1: raise HTTPException(409,'Plano alterado durante a importação. Confira novamente.')
                summary=report['summary']
            return {'ok':True,'summary':summary,'ignored_rows':ignored}
        except IntegrityError: raise HTTPException(409,'Um cadastro foi alterado durante a importação. Confira novamente; nenhuma alteração desta carga foi gravada.') from None
    return router
