import unittest
from io import BytesIO
from sqlalchemy import select,func
from openpyxl import Workbook
from test_maintenance import MaintenanceTests as Fixture
from maintenance_upload import build_maintenance_upload_router
from maintenance_api import MaintenancePlan, MaintenanceExecution
from models import Equipment

class SpreadsheetUploadTests(unittest.TestCase):
    def setUp(self):
        Fixture.setUp(self);self.auth.key='test-only-maintenance-upload-signing-key-123456'
        self.app.include_router(build_maintenance_upload_router(self.auth))
    tearDown=Fixture.tearDown
    role=Fixture.role
    def file(self,rows=None):
        book=Workbook();s=book.active;s.title='Cronograma'
        s.append(['Código atividade','TAG','Equipamento','OFICINA','LOCAL','TIPO','Atividade resumida','Responsável','Última execução','Intervalo (dias)','Observações'])
        for row in rows or [['PREV-001',' tt-1 ','Nome da planilha','SEEX','Linha 1','PT100','Aferição','Equipe','2026-01-01',7,'Nota'],['PREV-002','tt-1','Outro ponto','SEEX','Linha 2','Indicador','Inspeção','Equipe','2026-01-01',30,'']]:s.append(row)
        out=BytesIO();book.save(out);return out.getvalue()
    def preview(self,data=None):
        return self.client.post('/maintenance/import/preview',files={'file':('plano.xlsx',data or self.file())})
    def apply(self,token,data=None):
        return self.client.post('/maintenance/import/apply',files={'file':('plano.xlsx',data or self.file())},data={'preview_token':token})
    def test_existing_tag_reused_idempotence_and_update(self):
        p=self.preview();self.assertEqual(p.status_code,200,p.text);p=p.json()
        self.assertEqual(p['summary']['existing_instruments'],1);self.assertEqual(p['summary']['new_plans'],2)
        self.assertEqual(self.client.get('/maintenance/plans').json(),[])
        r=self.apply(p['preview_token']);self.assertEqual(r.status_code,200,r.text)
        with self.sessions() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(Equipment)),2)
            self.assertEqual(db.get(Equipment,1).name,'Temperatura')
        p=self.preview().json();self.assertEqual(p['summary']['unchanged_plans'],2)
        self.assertEqual(self.apply(p['preview_token']).status_code,200)
        data=self.file([['PREV-001','TT-1','Atualizado','SEEX','Linha 3','PT100','Nova tarefa','Equipe','2026-01-01',14,'Nova nota']])
        p=self.preview(data).json();self.assertEqual(p['summary']['updated_plans'],1)
        self.assertEqual(self.apply(p['preview_token'],data).status_code,200)
        rows=self.client.get('/maintenance/plans').json();self.assertEqual(len(rows),2);self.assertEqual(rows[0]['interval_days'],14)
    def test_new_tag_created_once_with_multiple_activities(self):
        data=self.file([['P1','NEW','Novo','','','','A','Equipe','',7,''],['P2','new','Outro','','','','B','Equipe','',7,'']])
        p=self.preview(data).json();self.assertEqual(p['summary']['new_instruments'],1)
        self.assertEqual(self.apply(p['preview_token'],data).status_code,200)
        with self.sessions() as db:self.assertEqual(db.scalar(select(func.count()).select_from(Equipment).where(Equipment.company_id==1)),2)
    def test_cross_tenant_and_role(self):
        token=self.preview().json()['preview_token'];self.role('company_admin',2)
        self.assertEqual(self.preview().json()['summary']['new_instruments'],1)
        self.assertEqual(self.apply(token).status_code,409)
        self.role('viewer');self.assertEqual(self.preview().status_code,403)
        self.role('operator');self.assertEqual(self.preview().status_code,403)
    def test_changed_file_and_concurrent_plan_conflict(self):
        p=self.preview().json();changed=self.file([['P3','TT-1','Nome','','','','A','Equipe','',3,'']])
        self.assertEqual(self.apply(p['preview_token'],changed).status_code,409)
        self.assertEqual(self.apply(p['preview_token']).status_code,200)
        token=self.preview().json()['preview_token']
        with self.sessions.begin() as db:
            plan=db.scalar(select(MaintenancePlan));plan.revision+=1
        self.assertEqual(self.apply(token).status_code,409)
    def test_duplicate_invalid_and_missing_rows(self):
        data=self.file([['P1','TT-1','Nome','','','','A','Equipe','',7,''],['p1','NEW','Nome','','','','B','Equipe','',7,'']])
        self.assertEqual(self.preview(data).status_code,422)
        data=self.file([['P1','TT-1','Nome','','','','A','Equipe','',0,'']]);self.assertEqual(self.preview(data).status_code,422)
        self.assertEqual(self.client.get('/maintenance/plans').json(),[])
    def test_history_and_other_tag_code_conflict(self):
        token=self.preview().json()['preview_token'];self.apply(token)
        with self.sessions.begin() as db:
            plan=db.scalar(select(MaintenancePlan));db.add(MaintenanceExecution(company_id=1,plan_id=plan.id,data='{}'))
        data=self.file([['PREV-001','TT-1','Nome','','','','A','Equipe','2026-02-01',7,'']])
        p=self.preview(data).json();self.assertIsNone(p['preview_token']);self.assertTrue(p['errors'])
        data=self.file([['PREV-001','OTHER','Nome','','','','A','Equipe','2026-01-01',7,'']])
        self.assertTrue(self.preview(data).json()['errors'])

if __name__=='__main__':unittest.main()
