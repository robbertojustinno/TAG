"""Private, additive spreadsheet import supplied through server environment only.

No customer records belong in repository files or static frontend assets.
"""
import json
import logging
import os
from collections import Counter
from sqlalchemy import select
if __package__:
    from .models import Company, Equipment
    from .maintenance_api import MaintenancePlan, PlanInput
else:
    from models import Company, Equipment
    from maintenance_api import MaintenancePlan, PlanInput

def import_maintenance(sessions, payload):
    rows=payload['rows']
    if not isinstance(rows,list) or not 1 <= len(rows) <= 1000:
        raise ValueError('Invalid import size')
    tags={r['tag'].strip().upper() for r in rows}
    if '' in tags: raise ValueError('Missing TAG')
    with sessions.begin() as db:
        companies=list(db.scalars(select(Company).where(Company.active.is_(True))))
        requested=payload['company_name'].strip().casefold()
        candidates=[c for c in companies if c.name.strip().casefold()==requested or c.name.strip().casefold().startswith(requested+' ')]
        if len(candidates)!=1:
            matches=db.execute(select(Equipment.company_id,Equipment.tag).where(Equipment.tag.in_(tags))).all()
            counts=Counter(company for company,tag in set(matches))
            owners=[c for c in companies if counts[c.id]>=3]
            if len(owners)!=1:
                return {'status':'company_not_identified','available_companies':[{'id':c.id,'name':c.name} for c in companies]}
            candidates=owners
        company=candidates[0]
        # Serialize imports of this tenant, including concurrent service starts.
        db.execute(select(Company.id).where(Company.id==company.id).with_for_update()).scalar_one()
        created=skipped=assets_created=0
        for row in rows:
            tag=row['tag'].strip().upper()
            equipment=db.scalar(select(Equipment).where(Equipment.company_id==company.id,Equipment.tag==tag))
            if equipment is None:
                equipment=Equipment(company_id=company.id,tag=tag,name=row['equipment_name'],photo='',
                    sector=row.get('workshop',''),location=row.get('location',''),equipment_type=row.get('equipment_type',''),
                    status='Ativo',notes='Cadastro importado da planilha de manutenção preventiva; conferir dados complementares.')
                db.add(equipment);db.flush();assets_created+=1
            existing=db.scalar(select(MaintenancePlan).where(MaintenancePlan.company_id==company.id,MaintenancePlan.code==row['code']))
            if existing:
                if existing.equipment_id!=equipment.id: raise ValueError('Activity code belongs to another equipment')
                skipped+=1;continue
            values={k:v for k,v in row.items() if k not in ('tag','equipment_name')}
            values['equipment_id']=equipment.id
            values['equipment_label']=row['equipment_name']
            plan=PlanInput(**values)
            db.add(MaintenancePlan(company_id=company.id,equipment_id=equipment.id,code=plan.code,data=plan.model_dump_json()))
            created+=1
        return {'status':'completed','company_id':company.id,'company_name':company.name,'created':created,'existing':skipped,'assets_created':assets_created}

def import_maintenance_from_environment(sessions):
    raw=os.environ.get('TAGCHECK_MAINTENANCE_IMPORT_JSON','').strip()
    if not raw: return
    result=import_maintenance(sessions,json.loads(raw))
    logging.getLogger(__name__).warning('Maintenance spreadsheet import: %s',json.dumps(result,ensure_ascii=False))
