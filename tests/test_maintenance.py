import secrets
import unittest
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from models import Base, Company, Equipment
from maintenance_api import build_maintenance_router, migrate_maintenance
from tenancy import CompanyContext

class MaintenanceTests(unittest.TestCase):
    def setUp(self):
        self.engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.sessions=sessionmaker(self.engine)
        with self.sessions() as db:
            db.add_all([Company(id=1,name='A',slug='a'),Company(id=2,name='B',slug='b')]);db.flush()
            db.add_all([Equipment(id=1,company_id=1,tag='TT-1',name='Temperatura',photo=''),Equipment(id=2,company_id=2,tag='TT-2',name='Outro',photo='')]);db.commit()
        class Auth:
            sessions=self.sessions
            def current(self): return CompanyContext(1,'test@example.invalid',1,'company_admin')
        self.auth=Auth(); app=FastAPI();app.include_router(build_maintenance_router(self.auth));self.app=app;self.client=TestClient(app)
        self.payload=dict(code='PREV-001',equipment_id=1,activity='Aferição',responsible='Instrumentação',interval_days=7,last_execution='2026-01-01')
    def tearDown(self): self.client.close();self.engine.dispose()
    def role(self,role,company=1):
        self.app.dependency_overrides[self.auth.current]=lambda:CompanyContext(1,'test@example.invalid',company,role)
    def create(self):
        r=self.client.post('/maintenance/plans',json=self.payload);self.assertEqual(r.status_code,201,r.text);return r.json()
    def test_scope_and_roles(self):
        p=self.create();self.role('viewer',2)
        self.assertEqual(self.client.get('/maintenance/plans').json(),[])
        self.assertEqual(self.client.get(f'/maintenance/plans/{p["id"]}/executions').status_code,404)
        self.role('viewer');self.assertEqual(self.client.post('/maintenance/plans',json=self.payload).status_code,403)
        self.role('operator');self.assertEqual(self.client.put(f'/maintenance/plans/{p["id"]}',json={**self.payload,'revision':1}).status_code,403)
        self.role('company_admin');self.assertEqual(self.client.post('/maintenance/plans',json={**self.payload,'equipment_id':2}).status_code,404)
    def test_execution_history_and_revision(self):
        p=self.create();now=datetime.now(timezone.utc)-timedelta(days=1)
        body=dict(revision=1,work_order='OS-001',started_at=(now-timedelta(minutes=30)).isoformat(),finished_at=now.isoformat(),executor='Técnico',result='Sem anomalias',conformity='Conforme',release='Liberado',released_by='Supervisor')
        self.role('operator');url=f'/maintenance/plans/{p["id"]}/executions'
        r=self.client.post(url,json=body);self.assertEqual(r.status_code,201,r.text)
        self.assertEqual(r.json()['plan']['revision'],2)
        self.assertEqual(self.client.post(url,json=body).status_code,409)
        h=self.client.get(url).json();self.assertEqual(len(h),1);self.assertEqual(h[0]['plan_snapshot']['last_execution'],'2026-01-01')
        self.role('viewer');self.assertEqual(self.client.post(url,json={**body,'revision':2}).status_code,403)
    def test_validation_conflict_and_migration(self):
        self.create();self.assertEqual(self.client.post('/maintenance/plans',json=self.payload).status_code,409)
        self.assertEqual(self.client.post('/maintenance/plans',json={**self.payload,'interval_days':0}).status_code,422)
        self.assertEqual(self.client.post('/maintenance/plans',json={**self.payload,'company_id':2}).status_code,422)
        with self.engine.begin() as con: migrate_maintenance(con);migrate_maintenance(con)
        self.assertEqual(len(self.client.get('/maintenance/plans').json()),1)
    def test_edit_conflict_and_due_date(self):
        p=self.create();self.assertEqual(p['next_due'],'2026-01-08')
        url=f'/maintenance/plans/{p["id"]}'
        body={**self.payload,'revision':1,'notes':'Alteração'}
        self.assertEqual(self.client.put(url,json=body).status_code,200)
        self.assertEqual(self.client.put(url,json=body).status_code,409)
        self.role('company_admin',2);self.assertEqual(self.client.put(url,json=body).status_code,404)

class MaintenanceAuthenticationTests(unittest.TestCase):
    def test_real_authentication_and_deletion_protection(self):
        import test_stabilization as fixture
        b=fixture.backend
        with TestClient(b.app) as client:
            self.assertEqual(client.get('/maintenance/plans').status_code,401)
            self.assertEqual(client.get('/maintenance/equipment').status_code,401)
            login=client.post('/auth/login',json={'username':fixture.ENV['ADMIN_USERNAME'],'password':fixture.ENV['ADMIN_PASSWORD']})
            self.assertEqual(login.status_code,200,login.text)
            headers={'Authorization':'Bearer '+login.json()['token']}
            with b.SessionLocal() as db:
                e=b.Equipment(company_id=b.DEFAULT_COMPANY_ID,tag='MAINT-'+secrets.token_hex(4),name='Instrumento teste',photo='test-only')
                db.add(e);db.commit();id=e.id
            result=client.post('/maintenance/plans',headers=headers,json={'code':'M-'+secrets.token_hex(4),'equipment_id':id,'activity':'Inspeção','responsible':'Equipe','interval_days':7})
            self.assertEqual(result.status_code,201,result.text)
            self.assertEqual(result.headers.get('cache-control'),'no-store')
            blocked = client.delete(f'/equipment/{id}', headers=headers)
            self.assertEqual(blocked.status_code, 409)
            self.assertEqual(blocked.json()['detail']['code'], 'equipment_has_maintenance_plan')
            self.assertEqual(client.get('/maintenance/plans', headers=headers).status_code, 200)
            with b.SessionLocal() as db:
                self.assertIsNotNone(db.get(b.Equipment, id))
                unlinked = b.Equipment(company_id=b.DEFAULT_COMPANY_ID, tag='FREE-'+secrets.token_hex(4),
                                       name='Instrumento sem plano', photo='test-only')
                db.add(unlinked)
                db.commit()
                unlinked_id = unlinked.id
            self.assertEqual(client.delete(f'/equipment/{unlinked_id}', headers=headers).status_code, 200)
            with b.SessionLocal() as db:
                self.assertIsNone(db.get(b.Equipment, unlinked_id))

if __name__=='__main__':unittest.main()
