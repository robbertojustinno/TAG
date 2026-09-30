"""Fase 1 regression: only generated credentials, temporary DB and mocked uploads."""
from pathlib import Path
from io import BytesIO
import importlib.util, json, os, secrets, sys, tempfile, unittest
from unittest.mock import patch
from sqlalchemy import create_engine, inspect, text
from fastapi.testclient import TestClient
from pypdf import PdfReader
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
TMP=tempfile.TemporaryDirectory(prefix='tagcheck-fase1-test-')
url='sqlite:///'+TMP.name+'/test.db'
engine=create_engine(url)
with engine.begin() as connection:
    connection.execute(text('CREATE TABLE tagcheck_equipment (id INTEGER PRIMARY KEY, tag TEXT UNIQUE NOT NULL, name TEXT NOT NULL, photo TEXT NOT NULL, notes TEXT)'))
    connection.execute(text("INSERT INTO tagcheck_equipment VALUES (42, 'OLD-42', 'Original', 'original.png', 'Preservar')"))
engine.dispose()
os.environ.update(DATABASE_URL=url,ADMIN_USERNAME='test-admin',ADMIN_PASSWORD=secrets.token_hex(20),ADMIN_TOKEN=secrets.token_hex(24),CLOUDINARY_CLOUD_NAME='test',CLOUDINARY_API_KEY='test',CLOUDINARY_API_SECRET='test')
spec=importlib.util.spec_from_file_location('fase1_test_backend',ROOT/'backend/main.py')
b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
from metrology import LABELS
from migrate_metrology import migrate_metrology

class MetrologyTests(unittest.TestCase):
    @classmethod
    def tearDownClass(cls):b.engine.dispose();TMP.cleanup()
    def setUp(self):
        self.client=TestClient(b.app);self.addCleanup(self.client.close)
        self.headers={'Authorization':'Bearer '+os.environ['ADMIN_TOKEN']}
        self.upload=self.enterContext(patch.object(b.cloudinary.uploader,'upload',return_value={'secure_url':'https://example.invalid/photo.png'}))
    def create(self,**values):
        return self.client.post('/equipment',headers=self.headers,data={'tag':secrets.token_hex(6),'name':'Pressão',**values},files={'photo':('photo.png',b'test','image/png')})
    def update(self,item,**values):
        return self.client.put(f'/equipment/{item["id"]}',headers=self.headers,data={'tag':item['tag'],'name':item['name'],**values})
    def test_legacy_rows_and_idempotent_migration(self):
        for _ in range(2):
            with b.engine.begin() as connection:migrate_metrology(connection)
        item=self.client.get('/equipment/tag/OLD-42').json()
        self.assertEqual((item['id'],item['name'],item['photo'],item['notes']),(42,'Original','original.png','Preservar'))
        for key in LABELS:self.assertIsNone(item[key])
        columns={c['name']:c for c in inspect(b.engine).get_columns('tagcheck_equipment')}
        for key in LABELS:self.assertTrue(columns[key]['nullable'])
    def test_optional_fields(self):
        item=self.create().json()
        for key in LABELS:self.assertIsNone(item[key])
    def test_example_calculation_and_api_reads(self):
        response=self.create(measurand='Pressão',measurement_unit='mmWS',range_min='0',range_max='630',accuracy_class='2,0',resolution='10',reading_contribution='5',calculate_ema='true')
        self.assertEqual(response.status_code,200,response.text);item=response.json()
        self.assertEqual(item['ema'],12.6);self.assertEqual(item['range_min'],0)
        self.assertEqual(self.client.get('/equipment/tag/'+item['tag']).json()['measurement_unit'],'mmWS')
        self.assertEqual(next(row for row in self.client.get('/equipment').json() if row['id']==item['id'])['reading_contribution'],5)
    def test_manual_value_preserved_for_old_clients(self):
        item=self.create(range_min='0',range_max='630',accuracy_class='2,0',ema='9,5').json()
        self.assertEqual(item['ema'],9.5)
        self.assertEqual(self.update(item).json()['ema'],9.5)
        self.assertEqual(self.update(item,ema='12,6').json()['ema'],12.6)
        self.assertIsNone(self.update(item,ema='').json()['ema'])
    def test_custom_grandeza_and_unit(self):
        item=self.create(measurand='Personalizada',measurement_unit='Minha unidade').json()
        self.assertEqual(self.update(item).json()['measurement_unit'],'Minha unidade')
    def test_invalid_values_do_not_upload(self):
        for values in ({'ema':'NaN'},{'ema':'Infinity'},{'resolution':'-1'},{'range_min':'20','range_max':'10'},{'calculate_ema':'true'}):
            self.assertEqual(self.create(**values).status_code,422)
        self.upload.assert_not_called()
    def test_negative_range(self):
        item=self.create(range_min='-50',range_max='50',accuracy_class='2%',calculate_ema='true').json()
        self.assertEqual(item['ema'],2)
    def test_write_authentication_unchanged(self):
        self.assertEqual(self.client.post('/equipment',data={'tag':'UNAUTHORIZED','name':'No'},files={'photo':('t.png',b'test','image/png')}).status_code,401)
        self.assertEqual(self.client.delete('/equipment/42').status_code,401)
        item=self.create().json();self.assertEqual(self.client.delete(f'/equipment/{item["id"]}',headers=self.headers).status_code,200)
    def test_asset_and_general_pdf_and_qr(self):
        item=self.create(measurand='Pressão',measurement_unit='mmWS',range_min='0',range_max='630',accuracy_class='2,0',resolution='10',ema='12,6',reading_contribution='5').json()
        for path in (f'/equipment/{item["id"]}/report-pdf','/equipment/report-pdf'):
            response=self.client.get(path);self.assertEqual(response.status_code,200,response.text[:100])
            text=''.join(page.extract_text() for page in PdfReader(BytesIO(response.content)).pages)
            for term in ('Dados Metrológicos','Pressão','mmWS','12,6','Contribuição estimada da leitura'):self.assertIn(term,text)
            if path.startswith('/equipment/'+str(item['id'])):Path('/tmp/tagcheck-fase1-test.pdf').write_bytes(response.content)
        self.assertTrue(self.client.get('/equipment/pdf').content.startswith(b'%PDF-'))
        self.assertEqual(self.client.get(f'/equipment/{item["id"]}/qr-payload').status_code,200)
    def test_category_hierarchy_filter_and_pdf(self):
        parent=self.client.post('/asset-categories',headers=self.headers,json={'name':'Categoria '+secrets.token_hex(4)}).json()
        response=self.client.post('/asset-categories',headers=self.headers,json={'name':'Instrumentos','parent_id':parent['id']})
        self.assertEqual(response.status_code,201,response.text);child=response.json()
        item=self.create(category_id=child['id']).json()
        self.assertEqual(item['category_path'],parent['name']+' / Instrumentos')
        self.assertEqual([r['id'] for r in self.client.get('/equipment',params={'category_id':parent['id']}).json()],[item['id']])
        self.assertEqual(self.client.get('/equipment',params={'category_id':parent['id'],'include_children':'false'}).json(),[])
        root=next(r for r in self.client.get('/asset-categories/tree').json() if r['id']==parent['id'])
        self.assertEqual(root['asset_count'],1);self.assertEqual(root['children'][0]['asset_count'],1)
        self.assertEqual(self.update(item).json()['category_id'],child['id'])
        pdf=self.client.get(f'/equipment/{item["id"]}/report-pdf')
        content=''.join(page.extract_text() for page in PdfReader(BytesIO(pdf.content)).pages)
        self.assertIn('Categoria',content);self.assertIn('Instrumentos',content)
        self.assertEqual(self.client.delete('/asset-categories/'+str(child['id']),headers=self.headers).status_code,409)
        self.assertEqual(self.client.delete('/asset-categories/'+str(parent['id']),headers=self.headers).status_code,409)
        self.assertEqual(self.client.patch('/asset-categories/'+str(parent['id']),headers=self.headers,json={'parent_id':child['id']}).status_code,422)
        self.assertIsNone(self.update(item,category_id='').json()['category_id'])
        self.assertEqual(self.client.delete('/asset-categories/'+str(child['id']),headers=self.headers).status_code,200)
        self.assertEqual(self.client.delete('/asset-categories/'+str(parent['id']),headers=self.headers).status_code,200)

    def test_category_validation_and_migration(self):
        from migrate_categories import migrate_categories
        before=self.client.get('/equipment/tag/OLD-42').json()
        for _ in range(2):
            with b.engine.begin() as connection:migrate_categories(connection)
        self.assertEqual(before,self.client.get('/equipment/tag/OLD-42').json())
        self.assertIsNone(before['category_id'])
        for body in ({'name':' '},{'name':'Missing parent','parent_id':999999}):
            self.assertEqual(self.client.post('/asset-categories',headers=self.headers,json=body).status_code,422)
        self.assertEqual(self.client.post('/asset-categories',headers=self.headers,json={'name':'bombas'}).status_code,409)
        self.assertEqual(self.client.post('/asset-categories',json={'name':'Unauthorized'}).status_code,401)
        self.assertEqual(self.create(category_id=999999).status_code,422);self.upload.assert_not_called()
        self.assertEqual(self.client.get('/equipment',params={'category_id':999999}).status_code,422)
        category=self.client.get('/asset-categories').json()[0]
        for body in ({'name':None},{'active':None},{'sort_order':None},{'name':' '}):
            self.assertEqual(self.client.patch('/asset-categories/'+str(category['id']),headers=self.headers,json=body).status_code,422)

    def test_unknown_asset_pdf(self):self.assertEqual(self.client.get('/equipment/999999/report-pdf').status_code,404)

if __name__=='__main__':unittest.main(verbosity=2)
