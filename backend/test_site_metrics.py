import os
import unittest
from datetime import datetime, timezone
from unittest.mock import patch
from uuid import uuid4
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from backend.site_metrics import build_metrics_router, period_starts

class MetricsTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
        app = FastAPI()
        app.include_router(build_metrics_router(engine))
        self.client = TestClient(app)
        self.env = patch.dict(os.environ, {'ADMIN_TOKEN': 'private-test-token'})
        self.env.start()
        self.addCleanup(self.env.stop)
    def test_private_and_deduplicated(self):
        self.assertEqual(self.client.get('/rovix-metrics/summary').status_code, 401)
        self.assertEqual(self.client.get('/rovix-metrics/summary', headers={'Authorization':'Bearer forged'}).status_code, 401)
        visit = {'visit_id':str(uuid4())}
        headers = {'Origin':'https://rovixautomation.com.br'}
        self.assertEqual(self.client.post('/rovix-metrics/visit', json=visit).status_code,403)
        for _ in range(2):
            self.assertEqual(self.client.post('/rovix-metrics/visit', json=visit, headers=headers).status_code,204)
        r=self.client.get('/rovix-metrics/summary', headers={'Authorization':'Bearer private-test-token'})
        self.assertEqual(r.status_code,200)
        self.assertEqual([r.json()[k] for k in ['daily','weekly','monthly']],[1,1,1])
        self.assertIn('no-store',r.headers['cache-control'])
    def test_details_private_bounded_and_deduplicated(self):
        headers = {'Origin':'https://rovixautomation.com.br', 'User-Agent':'Mozilla/5.0 (Linux; Android 15) Chrome/130.0 Mobile Safari/537.36', 'X-Forwarded-For':'1.2.3.4'}
        payload = {'visit_id':str(uuid4()), 'referrer':'https://example.org/path?secret=private', 'language':'pt-BR', 'screen':'1080×2400', 'timezone':'America/Sao_Paulo'}
        for _ in range(2):
            self.assertEqual(self.client.post('/rovix-metrics/visit',json=payload,headers=headers).status_code,204)
        summary=self.client.get('/rovix-metrics/summary',headers={'Authorization':'Bearer private-test-token'}).json()
        self.assertEqual(len(summary['recent']),1)
        detail=summary['recent'][0]
        self.assertEqual(detail['referrer'],'example.org')
        self.assertEqual(detail['system'],'Android')
        self.assertEqual(detail['device'],'Celular')
        self.assertNotEqual(detail['ip'],'1.2.3.4')
        payload['language']='x'*41
        self.assertEqual(self.client.post('/rovix-metrics/visit',json=payload,headers=headers).status_code,422)

    def test_public_fallback_is_never_accepted(self):
        with patch.dict(os.environ, {'ADMIN_TOKEN':'tagcheck-admin-token'}):
            self.assertEqual(self.client.get('/rovix-metrics/summary',headers={'Authorization':'Bearer tagcheck-admin-token'}).status_code,503)
    def test_brasilia_month_week_boundary(self):
        today,week,month=period_starts(datetime(2026,11,1,2,30,tzinfo=timezone.utc))
        self.assertEqual(str(today),'2026-10-31')
        self.assertEqual(str(week),'2026-10-26')
        self.assertEqual(str(month),'2026-10-01')
    def test_bot_not_counted(self):
        self.client.post('/rovix-metrics/visit',json={'visit_id':str(uuid4())},headers={'Origin':'https://rovixautomation.com.br','User-Agent':'crawler'})
        r=self.client.get('/rovix-metrics/summary',headers={'Authorization':'Bearer private-test-token'})
        self.assertEqual(r.json()['daily'],0)

if __name__ == '__main__': unittest.main()
