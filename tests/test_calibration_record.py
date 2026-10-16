"""Certificate persistence, scoped reports and derived arithmetic."""
import json
import secrets
import test_stabilization as fixture
from io import BytesIO
from decimal import Decimal
from types import SimpleNamespace
from pypdf import PdfReader
from fastapi import HTTPException
import test_metrology
import unittest
from calibration_record import evaluate_points, validate_record

class CalibrationTests(unittest.TestCase):
    setUp = test_metrology.MetrologyTests.setUp
    create = test_metrology.MetrologyTests.create
    update = test_metrology.MetrologyTests.update
    def test_record_roundtrip_and_report(self):
        record={'document_type':'Certificado de calibração','certificate_number':'5220/2026','laboratory':'Laboratório exemplo','results':[{'reference':'49,42','indicated':'42','input_unit':'°C','output_unit':'°C','uncertainty':'0,40','k':'2'}],'standards':[{'identification':'PT100','certificate':'1990/2026'}]}
        response=self.create(calibration_record=json.dumps(record),measurement_unit='°C',ema='1')
        self.assertEqual(response.status_code,200,response.text)
        item=response.json();self.assertEqual(item['calibration_record'],record)
        self.assertEqual(self.update(item).json()['calibration_record'],record)
        pdf=self.client.get(f'/equipment/{item["id"]}/master-report-pdf',headers=self.headers)
        self.assertEqual(pdf.status_code,200,pdf.text if pdf.status_code!=200 else '')
        content=''.join(p.extract_text() for p in PdfReader(BytesIO(pdf.content)).pages)
        for value in ('5220/2026','1990/2026','-7.42','Não conforme'): self.assertIn(value,content)
        self.assertEqual(self.client.get(f'/equipment/{item["id"]}/master-report-pdf').status_code,401)
        b=fixture.backend
        with b.SessionLocal() as db:
            company=b.Company(name='Other',slug=secrets.token_hex(6));db.add(company);db.flush()
            user=b.User(name='Other',email=secrets.token_hex(6)+'@example.invalid',password_hash='unused');db.add(user);db.flush()
            link=b.UserCompany(user_id=user.id,company_id=company.id,role='company_admin');db.add(link);db.flush()
            foreign={'Authorization':'Bearer '+b.auth.issue(user,link)};db.commit()
        self.assertEqual(self.client.get(f'/equipment/{item["id"]}/master-report-pdf',headers=foreign).status_code,404)
        self.assertEqual(self.update(item,calibration_record='{}').json()['calibration_record'],{})
    def test_invalid_record_rejected_before_upload(self):
        for record in ('[]','{"unknown":"x"}','{"results":[{"reference":4}]}'):
            self.assertEqual(self.create(calibration_record=record).status_code,422)
        self.upload.assert_not_called()
    def test_decimal_and_units(self):
        item=SimpleNamespace(ema=Decimal('0.2'),measurement_unit='bar')
        record={'results':[{'reference':'0,1','indicated':'0,3','input_unit':'bar','output_unit':'bar'}]}
        self.assertEqual(evaluate_points(item,record)[0],{'error':'0.2','acceptance':'Conforme'})
        record['results'][0]['output_unit']='psi'
        self.assertEqual(evaluate_points(item,record)[0]['acceptance'],'Não avaliado')
        record['results'][0]['output_unit']='bar';record['document_type']='Carta de inspeção'
        self.assertEqual(evaluate_points(item,record)[0]['acceptance'],'Não avaliado')
