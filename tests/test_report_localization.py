"""Report language changes captions while preserving tenant-owned content."""
import unittest
from types import SimpleNamespace
import test_stabilization
from calibration_record import master_html
from report_locale import translate_template

class ReportLocalizationTests(unittest.TestCase):
    def test_static_template_only(self):
        for language,caption in [('en','Manufacturer'),('es','Fabricante')]:
            html=translate_template('<html lang="pt-BR"><label>Fabricante</label></html>',language)
            self.assertIn('>'+caption+'<',html)
        self.assertEqual(translate_template('<label>Fabricante</label>','pt'),'<label>Fabricante</label>')

    def test_instrument_and_company_values_remain_original(self):
        item=SimpleNamespace(tag='TAG-TRAD-001',name='Pressão',manufacturer='Fabricante',
            calibration_date='2026-11-04',next_calibration_date='2027-11-04',sector='Setor',
            location='Localização',status='Ativo',range_min=None,range_max=None,
            measurement_unit='bar',ema=None,calibration_record={})
        for language,title in [('en','Manufacturer'),('es','Fabricante')]:
            html=master_html(item,'Empresa de Manutenção','Unidade Principal',language)
            self.assertIn('>'+title+'<',html)
            for value in ['Pressão','Empresa de Manutenção','Unidade Principal','TAG-TRAD-001']:
                self.assertIn(value,html)
            self.assertIn('id="fab">Fabricante<',html)
            self.assertNotIn('Procedimento não informado',html)
        self.assertIn('11/04/2026',master_html(item,'Empresa','','en'))
        self.assertIn('04/11/2026',master_html(item,'Empresa','','es'))
