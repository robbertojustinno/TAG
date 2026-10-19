"""Authenticated, tenant-scoped tagging storage with atomic versioned writes."""
import json
import re
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
if __package__:
    from .models import TaggingHierarchy, utcnow
else:
    from models import TaggingHierarchy, utcnow

KINDS = ('workshops', 'subsections', 'equipments', 'instruments')
TYPES = {'R', 'TK', 'B', 'COMP', 'EQ'}
QUANTITIES = {'P', 'T', 'F', 'L'}
FUNCTIONS = {'I', 'T', 'C', 'IC', 'IA'}

def empty_state():
    return {'version': 2, **{k: [] for k in KINDS}}

class HierarchyWrite(BaseModel):
    model_config = ConfigDict(extra='forbid')
    revision: int = Field(ge=0)
    state: dict

def invalid(message):
    raise HTTPException(422, message)

def validate_state(raw):
    if set(raw) != {'version', *KINDS} or raw.get('version') != 2:
        invalid('Formato da hierarquia inválido.')
    result = empty_state()
    by_id = {}
    ids = set()
    tags = set()
    for kind in KINDS:
        rows = raw[kind]
        if not isinstance(rows, list) or len(rows) > 10000:
            invalid('Quantidade de registros inválida.')
        normalized = []
        for row in rows:
            if not isinstance(row, dict):
                invalid('Registro inválido.')
            rid = row.get('id')
            if not isinstance(rid, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', rid) or rid in ids:
                invalid('Identificador inválido ou repetido.')
            ids.add(rid)
            label = 'description' if kind == 'instruments' else 'name'
            name = row.get(label)
            if not isinstance(name, str) or not name.strip() or len(name) > 120:
                invalid('Informe uma descrição de até 120 caracteres.')
            item = {'id': rid, label: name.strip()}
            if kind in ('workshops', 'subsections'):
                code = row.get('code')
                if not isinstance(code, str) or not re.fullmatch(r'[A-Z0-9_\-]{1,20}', code):
                    invalid('Código inválido.')
                item['code'] = code
                if kind == 'workshops':
                    expected = code
                else:
                    parent = by_id['workshops'].get(str(row.get('workshopId')))
                    if parent is None:
                        invalid('Oficina vinculada não encontrada nesta hierarquia.')
                    item['workshopId'] = parent['id']
                    expected = parent['tag'] + '-' + code
            elif kind == 'equipments':
                sub = by_id['subsections'].get(str(row.get('subsectionId')))
                typ = row.get('type')
                if sub is None or not isinstance(typ, str) or typ not in TYPES:
                    invalid('Subseção ou tipo de equipamento inválido.')
                item.update(subsectionId=sub['id'], workshopId=sub['workshopId'], type=typ,
                            company='LOCAL', unit=sub['tag'], area=sub['code'])
                prefix = sub['tag'] + '-' + typ
                proposed = row.get('tag', '')
                if not isinstance(proposed, str) or not re.fullmatch(re.escape(prefix) + r'[0-9]{3,6}', proposed):
                    invalid('Tag do equipamento não corresponde à subseção e ao tipo.')
                expected = proposed
            else:
                eq = by_id['equipments'].get(str(row.get('equipmentId')))
                q, f, loop = row.get('quantity'), row.get('function'), row.get('loop')
                if eq is None or not isinstance(q, str) or not isinstance(f, str) or q not in QUANTITIES or f not in FUNCTIONS or not isinstance(loop, str) or not re.fullmatch(r'[0-9]{1,6}', loop) or int(loop) < 1:
                    invalid('Equipamento, grandeza, função ou malha inválidos.')
                loop = loop.zfill(3)
                item.update(equipmentId=eq['id'], quantity=q, function=f, loop=loop,
                            company='LOCAL', unit=eq['unit'], area=eq['area'], parent=eq['tag'])
                expected = eq['tag'] + '-' + q + f + loop
            if row.get('tag') != expected or len(expected) > 80:
                invalid('Tag não corresponde à hierarquia informada.')
            if expected in tags:
                invalid('Tag duplicada nesta empresa.')
            tags.add(expected)
            item['tag'] = expected
            normalized.append(item)
        result[kind] = normalized
        by_id[kind] = {x['id']: x for x in normalized}
    if len(json.dumps(result)) > 5_000_000:
        invalid('Hierarquia excede o limite de tamanho.')
    return result

def build_tagging_router(auth):
    router = APIRouter(prefix='/tagging', tags=['Tagueamento'])

    @router.get('')
    def read(context=Depends(auth.current)):
        with auth.sessions() as db:
            row = db.get(TaggingHierarchy, context.company_id)
            return {'company_id': context.company_id, 'revision': row.revision if row else 0,
                    'state': json.loads(row.document) if row else empty_state(),
                    'can_write': context.role in ('company_admin', 'supervisor', 'operator'),
                    'can_delete': context.role in ('company_admin', 'supervisor')}

    @router.put('')
    def write(payload: HierarchyWrite, context=Depends(auth.writer)):
        state = validate_state(payload.state)
        with auth.sessions() as db:
            row = db.get(TaggingHierarchy, context.company_id)
            revision = row.revision if row else 0
            if revision != payload.revision:
                raise HTTPException(409, 'Os dados foram alterados em outra sessão. Recarregue antes de continuar.')
            old = json.loads(row.document) if row else empty_state()
            for kind in KINDS:
                before = {r['id'] for r in old[kind]}
                after = {r['id'] for r in state[kind]}
                if before - after and context.role not in ('company_admin', 'supervisor'):
                    raise HTTPException(403, 'Seu perfil não permite excluir registros.')
                # Children cannot silently move during a parent deletion.
                parent = {'workshops': ('subsections', 'workshopId'), 'subsections': ('equipments', 'subsectionId'), 'equipments': ('instruments', 'equipmentId')}.get(kind)
                if parent:
                    for removed in before - after:
                        if any(r.get(parent[1]) == removed for r in state[parent[0]]):
                            raise HTTPException(409, 'Registro ainda possui vínculos.')
            document = json.dumps(state, ensure_ascii=False)
            try:
                if row is None:
                    db.add(TaggingHierarchy(company_id=context.company_id, revision=1, document=document))
                else:
                    changed = db.execute(update(TaggingHierarchy).where(
                        TaggingHierarchy.company_id == context.company_id,
                        TaggingHierarchy.revision == payload.revision).values(
                        revision=payload.revision + 1, document=document, updated_at=utcnow()))
                    if changed.rowcount != 1:
                        db.rollback()
                        raise HTTPException(409, 'Conflito de edição. Recarregue os dados.')
                db.commit()
            except IntegrityError:
                db.rollback()
                raise HTTPException(409, 'Conflito de edição. Recarregue os dados.') from None
            return {'company_id': context.company_id, 'revision': revision + 1, 'state': state}
    return router
