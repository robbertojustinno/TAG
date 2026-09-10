import ast, os, subprocess, importlib.util, tempfile, secrets, unittest, re
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient

ROOT=Path(__file__).resolve().parents[1]
TMP=tempfile.TemporaryDirectory(prefix='tagcheck-test-')
# Only generated test credentials; never load local .env or id.txt.
ENV={'DATABASE_URL':'sqlite:///'+str(Path(TMP.name)/'test.sqlite').replace('\\','/'),
     'ADMIN_USERNAME':'test-admin', 'ADMIN_PASSWORD':secrets.token_hex(24),
     'ADMIN_TOKEN':secrets.token_hex(32), 'CLOUDINARY_CLOUD_NAME':'test-only',
     'CLOUDINARY_API_KEY':'test-only', 'CLOUDINARY_API_SECRET':secrets.token_hex(24)}
os.environ.update(ENV)
os.environ.pop('CLOUDINARY_URL',None)
source=(ROOT/'backend/main.py').read_text(encoding='utf-8-sig')
ast.parse(source)
spec=importlib.util.spec_from_file_location('tagcheck_test_backend',ROOT/'backend/main.py')
backend=importlib.util.module_from_spec(spec)
spec.loader.exec_module(backend)

class StabilizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client=TestClient(backend.app)

    @classmethod
    def tearDownClass(cls):
        cls.client.close()
        backend.engine.dispose()

    def login(self):
        r=self.client.post('/auth/login',json={'username':ENV['ADMIN_USERNAME'],'password':ENV['ADMIN_PASSWORD']})
        self.assertEqual(r.status_code,200)
        self.assertEqual(r.headers.get('cache-control'),'no-store')
        self.assertNotIn(ENV['ADMIN_TOKEN'],r.text)
        self.assertNotIn(ENV['ADMIN_PASSWORD'],r.text)
        return r.json()['token']

    def test_missing_configuration(self):
        for name in ENV:
            with self.subTest(variable=name),patch.dict(os.environ, {k:v for k,v in ENV.items() if k!=name},clear=True):
                with self.assertRaisesRegex(RuntimeError,name):
                    exec(compile(source,str(ROOT/'backend/main.py'),'exec'),{'__name__':'missing_config_test'})

    def test_health_and_login(self):
        self.assertEqual(self.client.get('/health').status_code,200)
        r=self.client.post('/auth/login',json={'username':'invalid','password':'invalid'})
        self.assertEqual(r.status_code,401)
        self.assertNotEqual(self.login(),self.login())

    def test_protected_write(self):
        self.assertEqual(self.client.delete('/equipment/999999').status_code,401)
        token=self.login()
        self.assertEqual(self.client.delete('/equipment/999999',headers={'Authorization':'Bearer '+token}).status_code,404)
        self.assertEqual(self.client.delete('/equipment/999999',headers={'Authorization':'Bearer '+ENV['ADMIN_TOKEN']}).status_code,401)
        self.assertEqual(self.client.delete('/equipment/999999',headers={'Authorization':'Bearer '+token+'tampered'}).status_code,401)
        with patch.object(backend.time,'time',return_value=backend.time.time()+9*3600):
            self.assertEqual(self.client.delete('/equipment/999999',headers={'Authorization':'Bearer '+token}).status_code,401)

    def test_pdf_with_equipment(self):
        with backend.SessionLocal() as db:
            db.add(backend.Equipment(tag='TEST-QR-001',name='Test instrument',photo='test-only'))
            db.commit()
        response=self.client.get('/equipment/pdf')
        self.assertEqual(response.status_code,200)
        self.assertTrue(response.content.startswith(b'%PDF-'))
        self.assertIn('application/pdf',response.headers['content-type'])

    def test_declared_dependencies(self):
        from importlib.metadata import version
        from packaging.requirements import Requirement
        for line in (ROOT/'backend/requirements.txt').read_text().splitlines():
            if not line.strip() or line.startswith('#'): continue
            dep=Requirement(line)
            self.assertIn(version(dep.name),dep.specifier)

if __name__=='__main__':
    try:
        unittest.main(verbosity=2)
    finally:
        backend.engine.dispose()
        TMP.cleanup()
