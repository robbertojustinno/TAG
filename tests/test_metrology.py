"""Metrology compatibility, decimal arithmetic, persistence, tenancy and PDF."""
from io import BytesIO
from pathlib import Path
import secrets, tempfile, unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from pypdf import PdfReader
from sqlalchemy import inspect, text
import test_stabilization as fixture
from migrate_multiempresa import make_engine, migrate
from metrology import LABELS
b = fixture.backend

class MetrologyTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(b.app)
        self.addCleanup(self.client.close)
        with b.SessionLocal() as db:
            user = db.get(b.User, b.LEGACY_USER_ID)
            self.headers = {'Authorization': 'Bearer ' + b.auth.issue(user, b.auth.membership(db, user.id, b.DEFAULT_COMPANY_ID))}
        self.upload = self.enterContext(patch.object(b.cloudinary.uploader, 'upload', return_value={'secure_url':'https://example.invalid/test.png'}))

    def create(self, **values):
        return self.client.post('/equipment', headers=self.headers, data={'tag':secrets.token_hex(6), 'name':'Pressure', **values}, files={'photo':('t.png',b'test','image/png')})

    def update(self, item, **values):
        return self.client.put(f'/equipment/{item["id"]}', headers=self.headers, data={'tag':item['tag'],'name':item['name'],**values})

    def test_example_calculation_manual_and_legacy_update(self):
        response = self.create(measurand='Pressão', measurement_unit='mmWS', range_min='0', range_max='630', accuracy_class='2,0', resolution='10', reading_contribution='5', calculate_ema='true')
        self.assertEqual(response.status_code, 200, response.text)
        item = response.json()
        self.assertEqual(item['ema'],12.6)
        self.assertEqual(item['range_min'],0)
        self.assertEqual(self.update(item).json()['ema'],12.6)
        self.assertEqual(self.update(item, ema='9,5').json()['ema'],9.5)
        fetched=self.client.get('/equipment/tag/'+item['tag'],headers=self.headers).json()
        self.assertEqual(fetched['reading_contribution'],5)
        self.assertEqual(fetched['measurement_unit'],'mmWS')
        self.assertIsNone(self.update(item, ema='').json()['ema'])

    def test_optional_fields(self):
        item=self.create().json()
        for key in LABELS: self.assertIsNone(item[key])
        self.assertEqual(self.update(item, range_min='-50',range_max='50',accuracy_class='2%',calculate_ema='true').json()['ema'],2)

    def test_invalid_input_and_range(self):
        for values in ({'ema':'NaN'},{'ema':'inf'},{'resolution':'-1'},{'range_min':'20','range_max':'10'},{'ema':'1e99'},{'calculate_ema':'true'},{'ema':'1.00000000001'}):
            with self.subTest(values=values): self.assertEqual(self.create(**values).status_code,422)
        self.upload.assert_not_called()

    def test_company_isolation_and_pdf(self):
        item=self.create(measurand='Pressão', measurement_unit='mmWS', range_min='0',range_max='630',accuracy_class='2,0',ema='12,6',resolution='10',reading_contribution='5').json()
        with b.SessionLocal() as db:
            company=b.Company(name='Foreign',slug=secrets.token_hex(6));db.add(company);db.flush()
            user=b.User(name='Foreign',email=secrets.token_hex(6)+'@example.invalid',password_hash='unused');db.add(user);db.flush()
            link=b.UserCompany(user_id=user.id,company_id=company.id,role='company_admin');db.add(link);db.flush()
            foreign={'Authorization':'Bearer '+b.auth.issue(user,link)};db.commit()
        self.assertEqual(self.client.put(f'/equipment/{item["id"]}',headers=foreign,data={'tag':item['tag'],'name':'Foreign','ema':'100'}).status_code,404)
        self.assertEqual(self.client.get(f'/equipment/{item["id"]}/report-pdf',headers=foreign).status_code,404)
        pdf=self.client.get(f'/equipment/{item["id"]}/report-pdf',headers=self.headers)
        self.assertEqual(pdf.status_code,200)
        contents=''.join(page.extract_text() for page in PdfReader(BytesIO(pdf.content)).pages)
        for term in ('Dados Metrológicos','Pressão','mmWS','12,6','Contribuição estimada da leitura'): self.assertIn(term,contents)
        Path('/tmp/metrology-test.pdf').write_bytes(pdf.content)

    def test_additive_idempotent_migration(self):
        with tempfile.TemporaryDirectory() as directory:
            engine=make_engine('sqlite:///'+directory+'/old.db')
            with engine.begin() as connection:
                connection.execute(text('CREATE TABLE tagcheck_equipment (id INTEGER PRIMARY KEY, tag TEXT UNIQUE NOT NULL, name TEXT NOT NULL, photo TEXT NOT NULL)'))
                connection.execute(text("INSERT INTO tagcheck_equipment VALUES (42, 'OLD', 'Preserved', 'old.png')"))
            for _ in range(2): migrate(engine,'admin','test-'+secrets.token_hex(20),'test@example.invalid')
            columns={col['name']:col for col in inspect(engine).get_columns('tagcheck_equipment')}
            for field in LABELS: self.assertTrue(columns[field]['nullable'])
            with engine.connect() as connection:
                row=connection.execute(text('SELECT * FROM tagcheck_equipment')).mappings().one()
                self.assertEqual((row['id'],row['tag'],row['photo']),(42,'OLD','old.png'))
                for field in LABELS:self.assertIsNone(row[field])
            engine.dispose()
