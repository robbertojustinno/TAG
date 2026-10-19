"""Tenant isolation, persistence, roles, tag validation and concurrent edits."""
import copy
import json
import secrets
import unittest
from fastapi.testclient import TestClient
import test_stabilization as fixture
from models import TaggingHierarchy
b = fixture.backend

class TaggingDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(b.app)
        self.headers = {}
        with b.SessionLocal() as db:
            for label in ('a','b'):
                company=b.Company(name=label,slug='tag-'+secrets.token_hex(8));db.add(company);db.flush()
                for role in ('company_admin','supervisor','operator','viewer'):
                    user=b.User(name=role,email=secrets.token_hex(12)+'@test.example',password_hash='test');db.add(user);db.flush()
                    membership=b.UserCompany(user_id=user.id,company_id=company.id,role=role);db.add(membership);db.flush()
                    self.headers[label,role]={'Authorization':'Bearer '+b.auth.issue(user,membership)}
            db.commit()
        self.state={'version':2,'workshops':[{'id':'w','name':'SEEX','code':'SEEX','tag':'SEEX'}],
                    'subsections':[{'id':'s','name':'UN6','code':'UN6','workshopId':'w','tag':'SEEX-UN6'}],
                    'equipments':[{'id':'e','name':'Reator','type':'R','subsectionId':'s','tag':'SEEX-UN6-R001'}],
                    'instruments':[{'id':'i','description':'Pressão','quantity':'P','function':'I','loop':'001','equipmentId':'e','tag':'SEEX-UN6-R001-PI001'}]}
    def tearDown(self): self.client.close()
    def put(self, state=None, revision=0, company='a', role='company_admin', extra=None):
        payload={'revision':revision,'state':self.state if state is None else state};payload.update(extra or {})
        return self.client.put('/tagging',headers=self.headers[company,role],json=payload)
    def test_persistence_and_tenant_isolation(self):
        r=self.put();self.assertEqual(r.status_code,200,r.text)
        with b.SessionLocal() as db:self.assertTrue(db.query(TaggingHierarchy).count())
        a=self.client.get('/tagging',headers=self.headers['a','viewer']).json();self.assertEqual(a['state']['instruments'][0]['tag'],'SEEX-UN6-R001-PI001')
        other=self.client.get('/tagging',headers=self.headers['b','company_admin']).json();self.assertEqual(other['revision'],0)
        self.assertEqual(self.put(company='b').status_code,200)
        self.assertEqual(self.client.get('/tagging').status_code,401)
        self.assertEqual(self.put(extra={'company_id':999}).status_code,422)
        h={**self.headers['a','company_admin'],'X-Company-Id':str(other['company_id'])}
        self.assertEqual(self.client.get('/tagging',headers=h).status_code,403)
    def test_roles_and_deletion(self):
        self.assertEqual(self.put(role='viewer').status_code,403)
        self.assertEqual(self.put(role='operator').status_code,200)
        state=copy.deepcopy(self.state);state['instruments']=[]
        self.assertEqual(self.put(state,1,role='operator').status_code,403)
        self.assertEqual(self.put(state,1,role='supervisor').status_code,200)
    def test_conflict_no_overwrite(self):
        self.assertEqual(self.put().status_code,200)
        state=copy.deepcopy(self.state);state['workshops'][0]['name']='Edited'
        self.assertEqual(self.put(state,1).status_code,200)
        self.assertEqual(self.put(revision=1).status_code,409)
        self.assertEqual(self.client.get('/tagging',headers=self.headers['a','viewer']).json()['state']['workshops'][0]['name'],'Edited')
    def test_invalid_links_tags_and_duplicates(self):
        for mutation in (lambda s:s['instruments'][0].update(equipmentId='foreign'),lambda s:s['subsections'][0].update(workshopId='foreign'),lambda s:s['equipments'][0].update(tag='WRONG'),lambda s:s['instruments'].append(s['instruments'][0]),lambda s:s['instruments'][0].update(quantity=[])):
            state=copy.deepcopy(self.state);mutation(state);self.assertEqual(self.put(state).status_code,422)
    def test_edits_and_delete_persist(self):
        self.assertEqual(self.put().status_code,200)
        state=copy.deepcopy(self.state)
        for rows in (state['workshops'],state['subsections'],state['equipments'],state['instruments']):
            for row in rows:row['tag']=row['tag'].replace('SEEX','TNR')
        state['workshops'][0]['code']='TNR'
        self.assertEqual(self.put(state,1).status_code,200)
        state['instruments']=[];self.assertEqual(self.put(state,2).status_code,200)
        state['equipments']=[];self.assertEqual(self.put(state,3).status_code,200)
        state['subsections']=[];self.assertEqual(self.put(state,4).status_code,200)
        state['workshops']=[];self.assertEqual(self.put(state,5).status_code,200)
