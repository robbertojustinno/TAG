import unittest
from sqlalchemy import select,func
from test_maintenance import MaintenanceTests
from maintenance_import import import_maintenance
from maintenance_api import MaintenancePlan
from models import Equipment

class SpreadsheetImportTests(MaintenanceTests):
    def import_payload(self):
        return {'company_name':'A','rows':[{'code':'PREV-001','tag':'TT-1','equipment_name':'Descrição planilha','activity':'Aferição','responsible':'Equipe','interval_days':7,'last_execution':'2027-06-01','equipment_type':'PT100'}, {'code':'PREV-002','tag':'NEW','equipment_name':'Novo instrumento','activity':'Inspeção','responsible':'Equipe','interval_days':7}]}
    def test_additive_idempotent_and_scoped(self):
        result=import_maintenance(self.sessions,self.import_payload())
        self.assertEqual(result['created'],2);self.assertEqual(result['assets_created'],1)
        result=import_maintenance(self.sessions,self.import_payload());self.assertEqual(result['created'],0);self.assertEqual(result['existing'],2)
        with self.sessions() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(MaintenancePlan).where(MaintenancePlan.company_id==2)),0)
            self.assertEqual(db.get(Equipment,1).name,'Temperatura')
        plans=self.client.get('/maintenance/plans').json()
        self.assertEqual(plans[0]['equipment_name'],'Descrição planilha')
        self.assertEqual(plans[0]['last_execution'],'2027-06-01')
    def test_unknown_company_does_not_write(self):
        payload=self.import_payload();payload['company_name']='Unknown'
        self.assertEqual(import_maintenance(self.sessions,payload)['status'],'company_not_identified')
        self.assertEqual(self.client.get('/maintenance/plans').json(),[])
    def test_invalid_row_rolls_back_all_records(self):
        payload=self.import_payload();payload['rows'][1]['interval_days']=0
        with self.assertRaises(ValueError):import_maintenance(self.sessions,payload)
        self.assertEqual(self.client.get('/maintenance/plans').json(),[])

if __name__=='__main__':unittest.main()
