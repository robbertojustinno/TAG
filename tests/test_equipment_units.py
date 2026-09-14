"""Six focused equipment/unit cases; temporary databases and mocked uploads."""
from pathlib import Path
import secrets
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session
import test_stabilization as fixture
from models import Unit
from migrate_multiempresa import make_engine, migrate

b = fixture.backend


class EquipmentUnitTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(b.app)
        self.addCleanup(self.client.close)
        self.prefix = secrets.token_hex(5)
        with b.SessionLocal() as db:
            company = b.Company(name='Other', slug='other-' + self.prefix)
            db.add(company)
            db.flush()
            self.units = []
            for name, company_id in [('first', b.DEFAULT_COMPANY_ID), ('second', b.DEFAULT_COMPANY_ID), ('foreign', company.id)]:
                unit = Unit(name=name, slug=name + '-' + self.prefix, company_id=company_id)
                db.add(unit)
                db.flush()
                self.units.append(unit.id)
            user = db.get(b.User, b.LEGACY_USER_ID)
            link = b.auth.membership(db, user.id, b.DEFAULT_COMPANY_ID)
            token = b.auth.issue(user, link)
            db.commit()
        self.headers = {'Authorization': 'Bearer ' + token}
        self.upload = self.enterContext(patch.object(b.cloudinary.uploader, 'upload', return_value={'secure_url': 'https://example.invalid/photo.png'}))

    def create(self, **extra):
        return self.client.post('/equipment', headers=self.headers,
                                data={'tag': self.prefix, 'name': 'Instrument', **extra},
                                files={'photo': ('test.png', b'test', 'image/png')})

    def update(self, item, **extra):
        return self.client.put(f'/equipment/{item["id"]}', headers=self.headers,
                               data={'tag': item['tag'], 'name': item['name'], **extra})

    def test_create_without_unit(self):
        response = self.create()
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()['unit_id'])
        self.assertIsNone(response.json()['unit_name'])

    def test_create_with_valid_unit(self):
        response = self.create(unit_id=self.units[0])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['unit_id'], self.units[0])
        self.assertEqual(response.json()['unit_name'], 'first')
        fetched = self.client.get('/equipment/tag/' + self.prefix, headers=self.headers)
        self.assertEqual(fetched.json()['unit_name'], 'first')
        listed = next(item for item in self.client.get('/equipment', headers=self.headers).json() if item['tag'] == self.prefix.upper())
        self.assertEqual(listed['unit_id'], self.units[0])

    def test_block_foreign_unit(self):
        response = self.create(unit_id=self.units[2])
        self.assertEqual(response.status_code, 404)
        self.upload.assert_not_called()
        item = self.create(unit_id=self.units[0]).json()
        self.assertEqual(self.update(item, unit_id=self.units[2]).status_code, 404)
        self.assertEqual(self.update(item, unit_id=999999999).status_code, 404)
        with b.SessionLocal() as db:
            self.assertEqual(db.get(b.Equipment, item['id']).unit_id, self.units[0])

    def test_change_unit(self):
        item = self.create(unit_id=self.units[0]).json()
        response = self.update(item, unit_id=self.units[1])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['unit_id'], self.units[1])
        self.assertEqual(response.json()['unit_name'], 'second')
        # An old admin client editing other fields must not clear the association.
        unchanged = self.update(item)
        self.assertEqual(unchanged.status_code, 200)
        self.assertEqual(unchanged.json()['unit_id'], self.units[1])

    def test_remove_unit(self):
        item = self.create(unit_id=self.units[0]).json()
        response = self.update(item, unit_id='')
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()['unit_id'])
        self.assertIsNone(response.json()['unit_name'])
        with b.SessionLocal() as db:
            self.assertIsNone(db.get(b.Equipment, item['id']).unit_id)

    def test_preserve_legacy_equipment(self):
        with tempfile.TemporaryDirectory(prefix='tagcheck-equipment-unit-') as directory:
            engine = make_engine('sqlite:///' + (Path(directory) / 'old.db').as_posix())
            try:
                with engine.begin() as connection:
                    connection.execute(text('CREATE TABLE tagcheck_equipment (id INTEGER PRIMARY KEY, tag TEXT UNIQUE NOT NULL, name TEXT NOT NULL, photo TEXT NOT NULL)'))
                    connection.execute(text("INSERT INTO tagcheck_equipment VALUES (42, 'OLD-42', 'Preserved', 'old.png')"))
                password = secrets.token_urlsafe(24)
                for _ in range(2):
                    migrate(engine, 'test-admin', password, 'migration@example.invalid')
                    with Session(engine) as db:
                        item = db.get(b.Equipment, 42)
                        self.assertEqual((item.id, item.tag, item.name, item.photo), (42, 'OLD-42', 'Preserved', 'old.png'))
                        self.assertIsNone(item.unit_id)
                        self.assertIsNone(b.serialize_equipment(item)['unit_name'])
                schema = inspect(engine)
                self.assertTrue(next(c for c in schema.get_columns('tagcheck_equipment') if c['name'] == 'unit_id')['nullable'])
                self.assertTrue(any(fk['constrained_columns'] == ['unit_id'] and fk['referred_table'] == 'units' for fk in schema.get_foreign_keys('tagcheck_equipment')))
                self.assertTrue(any(index['column_names'] == ['unit_id'] for index in schema.get_indexes('tagcheck_equipment')))
            finally:
                engine.dispose()


if __name__ == '__main__':
    unittest.main(verbosity=2)
