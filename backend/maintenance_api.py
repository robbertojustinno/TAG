"""Preventive maintenance: authenticated tenant scope, revision checks and immutable history."""
import json
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, UniqueConstraint, select, update
from sqlalchemy.exc import IntegrityError
if __package__:
    from .models import Base, Equipment, utcnow
else:
    from models import Base, Equipment, utcnow

class MaintenancePlan(Base):
    __tablename__ = 'maintenance_plans'
    __table_args__ = (UniqueConstraint('company_id', 'code', name='uq_maintenance_company_code'),)
    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey('companies.id'), nullable=False, index=True)
    equipment_id = Column(Integer, ForeignKey('tagcheck_equipment.id', ondelete='RESTRICT'), nullable=False, index=True)
    code = Column(String(100), nullable=False)
    revision = Column(Integer, nullable=False, default=1)
    data = Column(Text, nullable=False)
    updated_by = Column(Integer, nullable=True)
    updated_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

class MaintenanceExecution(Base):
    __tablename__ = 'maintenance_executions'
    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey('companies.id'), nullable=False, index=True)
    plan_id = Column(Integer, ForeignKey('maintenance_plans.id'), nullable=False, index=True)
    data = Column(Text, nullable=False)
    created_by = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

class PlanInput(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    code: str = Field(min_length=1, max_length=100)
    equipment_id: int = Field(gt=0)
    workshop: str = Field(default='', max_length=200)
    location: str = Field(default='', max_length=200)
    equipment_type: str = Field(default='', max_length=200)
    activity: str = Field(min_length=1, max_length=2000)
    responsible: str = Field(min_length=1, max_length=200)
    last_execution: date | None = None
    first_due: date | None = None
    interval_days: int = Field(ge=1, le=36500)
    component: str = Field(default='', max_length=200)
    procedure: str = Field(default='', max_length=4000)
    acceptance: str = Field(default='', max_length=2000)
    duration_minutes: int | None = Field(default=None, ge=0, le=100000)
    resources: str = Field(default='', max_length=2000)
    qualification: str = Field(default='', max_length=1000)
    shutdown: str = Field(default='', max_length=500)
    protections: str = Field(default='', max_length=2000)
    reference: str = Field(default='', max_length=1000)
    notes: str = Field(default='', max_length=4000)
    active: bool = True

class PlanUpdate(PlanInput):
    revision: int = Field(ge=1)

class ExecutionInput(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    revision: int = Field(ge=1)
    work_order: str = Field(min_length=1, max_length=100)
    started_at: datetime
    finished_at: datetime
    executor: str = Field(min_length=1, max_length=200)
    result: str = Field(min_length=1, max_length=4000)
    conformity: Literal['Conforme', 'Não conforme', 'Não aplicável']
    anomaly: str = Field(default='', max_length=4000)
    materials: str = Field(default='', max_length=2000)
    corrective_order: str = Field(default='', max_length=100)
    release: Literal['Liberado', 'Liberado com restrição', 'Não liberado']
    released_by: str = Field(min_length=1, max_length=200)
    notes: str = Field(default='', max_length=4000)

    @model_validator(mode='after')
    def dates(self):
        if self.started_at.tzinfo is None or self.finished_at.tzinfo is None:
            raise ValueError('Informe horários com fuso.')
        if self.finished_at < self.started_at or self.finished_at > utcnow():
            raise ValueError('Término inválido ou no futuro.')
        return self

def migrate_maintenance(connection):
    Base.metadata.create_all(connection, tables=[MaintenancePlan.__table__, MaintenanceExecution.__table__])

def build_maintenance_router(auth):
    router = APIRouter(prefix='/maintenance', tags=['maintenance'])
    def permission(context, roles):
        if not context.is_superadmin and context.role not in roles:
            raise HTTPException(403, 'Perfil sem permissão para esta operação.')
    def find(db, id, ctx):
        row=db.scalar(select(MaintenancePlan).where(MaintenancePlan.id==id, MaintenancePlan.company_id==ctx.company_id))
        if row is None: raise HTTPException(404, 'Plano não encontrado.')
        return row
    def asset(db, id, ctx):
        row=db.scalar(select(Equipment).where(Equipment.id==id, Equipment.company_id==ctx.company_id))
        if row is None: raise HTTPException(404, 'Equipamento não encontrado nesta empresa.')
        return row
    def output(db, row, ctx):
        data=json.loads(row.data); eq=asset(db, data['equipment_id'], ctx)
        due=(date.fromisoformat(data['last_execution'])+timedelta(days=data['interval_days'])) if data.get('last_execution') else (date.fromisoformat(data['first_due']) if data.get('first_due') else None)
        remaining=(due-datetime.now(ZoneInfo('America/Sao_Paulo')).date()).days if due else None
        status='Inativo' if not data['active'] else 'Sem programação' if due is None else 'Atrasada' if remaining<0 else 'Vence hoje' if remaining==0 else 'Próximos 7 dias' if remaining<=7 else 'Programada'
        return dict(data,id=row.id,revision=row.revision,tag=eq.tag,equipment_name=eq.name,next_due=due,days_remaining=remaining,status=status,updated_at=row.updated_at)
    def save(db, row):
        try: db.commit()
        except IntegrityError:
            db.rollback(); raise HTTPException(409, 'Código de atividade já utilizado nesta empresa.') from None

    @router.get('/equipment')
    def equipment(ctx=Depends(auth.current)):
        with auth.sessions() as db:
            return [dict(id=e.id,tag=e.tag,name=e.name,workshop=e.sector or '',location=e.location or '',equipment_type=e.equipment_type or '') for e in db.scalars(select(Equipment).where(Equipment.company_id==ctx.company_id).order_by(Equipment.tag))]

    @router.get('/plans')
    def plans(ctx=Depends(auth.current)):
        with auth.sessions() as db:
            return [output(db,r,ctx) for r in db.scalars(select(MaintenancePlan).where(MaintenancePlan.company_id==ctx.company_id).order_by(MaintenancePlan.code))]

    @router.post('/plans', status_code=201)
    def create(payload: PlanInput, ctx=Depends(auth.current)):
        permission(ctx, ['company_admin','supervisor'])
        with auth.sessions() as db:
            asset(db,payload.equipment_id,ctx)
            row=MaintenancePlan(company_id=ctx.company_id,equipment_id=payload.equipment_id,code=payload.code,data=payload.model_dump_json(),updated_by=ctx.user_id)
            db.add(row);save(db,row);db.refresh(row);return output(db,row,ctx)

    @router.put('/plans/{id}')
    def edit(id: int, payload: PlanUpdate, ctx=Depends(auth.current)):
        permission(ctx, ['company_admin','supervisor'])
        with auth.sessions() as db:
            row=find(db,id,ctx);asset(db,payload.equipment_id,ctx)
            if json.loads(row.data).get('last_execution') != (payload.last_execution.isoformat() if payload.last_execution else None) and db.scalar(select(MaintenanceExecution.id).where(MaintenanceExecution.plan_id==id)):
                raise HTTPException(409,'Última execução possui histórico; registre uma nova execução para atualizá-la.')
            if row.equipment_id != payload.equipment_id:
                raise HTTPException(409,'Para outro equipamento, crie um novo plano e inative este.')
            result=db.execute(update(MaintenancePlan).where(MaintenancePlan.id==id,MaintenancePlan.company_id==ctx.company_id,MaintenancePlan.revision==payload.revision).values(code=payload.code,data=json.dumps(payload.model_dump(mode='json',exclude={'revision'}),ensure_ascii=False),revision=payload.revision+1,updated_by=ctx.user_id,updated_at=utcnow()))
            if not result.rowcount: raise HTTPException(409,'Plano alterado por outro usuário. Recarregue.')
            save(db,row);db.expire_all();return output(db,find(db,id,ctx),ctx)

    @router.get('/plans/{id}/executions')
    def history(id: int, ctx=Depends(auth.current)):
        with auth.sessions() as db:
            find(db,id,ctx)
            return [dict(json.loads(r.data),id=r.id,created_at=r.created_at,created_by=r.created_by) for r in db.scalars(select(MaintenanceExecution).where(MaintenanceExecution.company_id==ctx.company_id,MaintenanceExecution.plan_id==id).order_by(MaintenanceExecution.id.desc()))]

    @router.post('/plans/{id}/executions',status_code=201)
    def execute(id: int, payload: ExecutionInput, ctx=Depends(auth.current)):
        permission(ctx,['company_admin','supervisor','operator'])
        with auth.sessions() as db:
            row=find(db,id,ctx);data=json.loads(row.data)
            if not data['active']: raise HTTPException(409,'Plano inativo.')
            completed=payload.finished_at.astimezone(ZoneInfo('America/Sao_Paulo')).date()
            if data.get('last_execution') and completed<date.fromisoformat(data['last_execution']):
                raise HTTPException(409,'Execução anterior à última execução do plano.')
            snapshot=output(db,row,ctx);data['last_execution']=completed.isoformat()
            result=db.execute(update(MaintenancePlan).where(MaintenancePlan.id==id,MaintenancePlan.company_id==ctx.company_id,MaintenancePlan.revision==payload.revision).values(data=json.dumps(data,ensure_ascii=False),revision=payload.revision+1,updated_by=ctx.user_id,updated_at=utcnow()))
            if not result.rowcount: raise HTTPException(409,'Plano alterado. Recarregue antes de registrar novamente.')
            record=payload.model_dump(mode='json',exclude={'revision'});record['plan_snapshot']=json.loads(json.dumps(snapshot,default=str))
            history=MaintenanceExecution(company_id=ctx.company_id,plan_id=id,data=json.dumps(record,ensure_ascii=False),created_by=ctx.user_id)
            db.add(history);db.commit();return {'id':history.id,'plan':output(db,find(db,id,ctx),ctx)}
    return router
