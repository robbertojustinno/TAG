"""Write audit records in the same transaction as tracked ORM changes."""

from contextvars import ContextVar
from datetime import datetime, timezone
from types import SimpleNamespace
import json

from fastapi import APIRouter, Depends, Query
from sqlalchemy import Column, DateTime, Integer, String, Text, event, inspect, select

if __package__:
    from .models import Base
else:
    from models import Base


audit_request = ContextVar("audit_request", default=None)
TRACKED = {
    'companies', 'units', 'users', 'user_companies', 'asset_categories',
    'tagcheck_equipment', 'tagging_hierarchies', 'maintenance_plans',
    'maintenance_executions', 'billing_production', 'billing_production_invoices',
    'billing_production_extra_invoices', 'billing_sandbox',
}
REDACTED = ('password', 'token', 'secret', 'credential', 'payload', 'photo', 'logo',
            'pix', 'barcode', 'bank_slip', 'invoice_url')


class AuditEvent(Base):
    __tablename__ = 'audit_events'

    id = Column(Integer, primary_key=True)
    occurred_at = Column(DateTime(timezone=True), nullable=False, index=True)
    actor_id = Column(Integer, index=True)
    actor_email = Column(String(254))
    company_id = Column(Integer, index=True)
    entity = Column(String(80), nullable=False, index=True)
    entity_id = Column(String(120))
    action = Column(String(12), nullable=False)
    changes = Column(Text, nullable=False)


def record_actor(context):
    request = audit_request.get()
    if request is not None:
        request['actor'] = context


def record_identity(user, company_id=None):
    record_actor(SimpleNamespace(
        user_id=user.id, email=user.email, is_superadmin=user.is_superadmin,
        company_id=company_id,
    ))


def audit_changes(session, flush_context):
    request = audit_request.get()
    if request is None:
        return
    actor = request.get('actor')
    records = []
    for action, entities in (('create', session.new), ('update', session.dirty),
                             ('delete', session.deleted)):
        for entity in entities:
            state = inspect(entity)
            table = state.mapper.local_table.name
            if table not in TRACKED:
                continue
            changes = {}
            for field in state.mapper.column_attrs:
                key = field.key
                attr = state.attrs[key]
                if action == 'update' and not attr.history.has_changes():
                    continue
                if any(pattern in key for pattern in REDACTED):
                    changes[key] = {'redacted': True}
                    continue
                before = attr.history.deleted
                value = attr.value
                changes[key] = {
                    'before': (before[0] if before else None) if action == 'update' else
                              (value if action == 'delete' else None),
                    'after': None if action == 'delete' else value,
                }
            if not changes:
                continue
            company_id = getattr(entity, 'company_id', None)
            if table == 'companies':
                company_id = entity.id
            if company_id is None and actor is not None and not actor.is_superadmin:
                company_id = actor.company_id
            records.append({
                'occurred_at': datetime.now(timezone.utc),
                'actor_id': actor.user_id if actor else None,
                'actor_email': actor.email if actor else None,
                'company_id': company_id,
                'entity': table,
                'entity_id': ':'.join(str(getattr(entity, column.key)) for column in state.mapper.primary_key),
                'action': action,
                'changes': json.dumps(changes, default=str, ensure_ascii=False),
            })
    if records:
        session.connection().execute(AuditEvent.__table__.insert(), records)


def record_update(db, actor, entity, entity_id, before, after):
    changes = {
        key: {'before': before.get(key), 'after': value}
        for key, value in after.items() if before.get(key) != value
    }
    if changes:
        db.connection().execute(AuditEvent.__table__.insert().values(
            occurred_at=datetime.now(timezone.utc), actor_id=actor.user_id,
            actor_email=actor.email, company_id=actor.company_id, entity=entity,
            entity_id=str(entity_id), action='update',
            changes=json.dumps(changes, default=str, ensure_ascii=False),
        ))


def install_audit(sessions):
    event.listen(sessions, 'after_flush', audit_changes)


def build_audit_router(auth):
    router = APIRouter()

    @router.get('/superadmin/audit')
    def audit_log(
        target_company_id: int | None = None, actor_id: int | None = None,
        entity: str | None = None, action: str | None = None,
        start: datetime | None = None, end: datetime | None = None,
        before_id: int | None = None, limit: int = Query(50, ge=1, le=100),
        _=Depends(auth.superadmin),
    ):
        statement = select(AuditEvent)
        for column, value in ((AuditEvent.company_id, target_company_id), (AuditEvent.actor_id, actor_id),
                              (AuditEvent.entity, entity), (AuditEvent.action, action)):
            if value is not None:
                statement = statement.where(column == value)
        if start is not None:
            statement = statement.where(AuditEvent.occurred_at >= start)
        if end is not None:
            statement = statement.where(AuditEvent.occurred_at <= end)
        if before_id is not None:
            statement = statement.where(AuditEvent.id < before_id)
        with auth.sessions() as db:
            rows = db.scalars(statement.order_by(AuditEvent.id.desc()).limit(limit)).all()
            return [{
                'id': row.id, 'occurred_at': row.occurred_at.replace(tzinfo=timezone.utc)
                if row.occurred_at.tzinfo is None else row.occurred_at,
                'actor_id': row.actor_id, 'actor_email': row.actor_email,
                'company_id': row.company_id, 'entity': row.entity, 'entity_id': row.entity_id,
                'action': row.action, 'changes': json.loads(row.changes),
            } for row in rows]

    return router
