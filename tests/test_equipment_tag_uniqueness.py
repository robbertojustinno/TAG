"""TAG migration on disposable SQLite and opt-in PostgreSQL test schemas.

PostgreSQL: set TAGCHECK_TEST_POSTGRES=1 and DATABASE_URL for tagcheck_fase2_test.
No production database is accepted. Each case owns a random, disposable schema.
"""
import os
from pathlib import Path
import secrets
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from sqlalchemy import inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from migrate_multiempresa import make_engine, migrate
from models import Company, Equipment


class TagUniquenessCases:
    def migrate(self):
        return migrate(self.engine, 'test-admin', self.password, 'tag-test@example.invalid')

    def assert_company_uniqueness(self):
        with Session(self.engine) as db:
            a = Company(name='A', slug='tag-a')
            b = Company(name='B', slug='tag-b')
            db.add_all([a, b]); db.flush()
            a_id, b_id = a.id, b.id
            items = [Equipment(company_id=company, tag='SHARED', name='Shared', photo='local')
                     for company in (a_id, b_id)]
            db.add_all(items); db.flush()
            ids = [item.id for item in items]
            self.assertNotEqual(*ids)
            db.commit()
        with self.assertRaises(IntegrityError), Session(self.engine) as db:
            db.add(Equipment(company_id=a_id, tag='SHARED', name='Duplicate', photo='local'))
            db.commit()
        # Uniqueness must also reject moving equipment into a conflicting tenant.
        with self.assertRaises(IntegrityError), Session(self.engine) as db:
            db.get(Equipment, ids[1]).company_id = a_id
            db.commit()
        with self.engine.connect() as c:
            before = c.execute(text('SELECT * FROM tagcheck_equipment ORDER BY id')).mappings().all()
        self.migrate()
        self.migrate()
        with self.engine.connect() as c:
            after = c.execute(text('SELECT * FROM tagcheck_equipment ORDER BY id')).mappings().all()
        self.assertEqual(before, after)
        indexes = inspect(self.engine).get_indexes('tagcheck_equipment')
        self.assertFalse(any(i['unique'] and i['column_names'] == ['tag'] for i in indexes))
        constraints = inspect(self.engine).get_unique_constraints('tagcheck_equipment')
        self.assertTrue(any(i['name'] == 'uq_equipment_company_tag'
                            and i['column_names'] == ['company_id', 'tag']
                            for i in constraints + indexes))

    def test_fresh_model_scopes_tag_to_company(self):
        self.migrate()
        self.assert_company_uniqueness()

    def legacy_table(self, inline=False):
        primary_key = 'SERIAL PRIMARY KEY' if self.engine.dialect.name == 'postgresql' else 'INTEGER PRIMARY KEY'
        with self.engine.begin() as c:
            c.execute(text(f'CREATE TABLE tagcheck_equipment (id {primary_key}, '
                           f'tag TEXT NOT NULL {"UNIQUE" if inline else ""}, '
                           'name TEXT NOT NULL, photo TEXT NOT NULL)'))
            if not inline:
                # Exercise quoted names instead of depending on ORM naming.
                c.execute(text('CREATE UNIQUE INDEX "Legacy TAG unique" ON tagcheck_equipment(tag)'))
            c.execute(text("INSERT INTO tagcheck_equipment(tag,name,photo) VALUES('LEGACY','Preserved','old.png')"))
            self.legacy_id = c.scalar(text("SELECT id FROM tagcheck_equipment WHERE tag='LEGACY'"))

    def test_legacy_global_index_replaced_without_data_loss(self):
        self.legacy_table()
        self.migrate()
        self.assert_company_uniqueness()
        with self.engine.connect() as c:
            self.assertEqual(c.execute(text("SELECT id,name,photo FROM tagcheck_equipment WHERE tag='LEGACY'")).one(),
                             (self.legacy_id, 'Preserved', 'old.png'))

    def test_duplicate_tenant_tags_roll_back_migration(self):
        self.legacy_table()
        with self.engine.begin() as c:
            c.execute(text('DROP INDEX "Legacy TAG unique"'))
            c.execute(text("INSERT INTO tagcheck_equipment(tag,name,photo) VALUES('LEGACY','Duplicate','second.png')"))
        with self.assertRaisesRegex(RuntimeError, 'normalized TAG collision within company'):
            self.migrate()
        self.assertEqual(inspect(self.engine).get_table_names(), ['tagcheck_equipment'])
        with self.engine.connect() as c:
            self.assertEqual(c.scalar(text('SELECT COUNT(*) FROM tagcheck_equipment')), 2)
        self.assertNotIn('company_id', {c['name'] for c in inspect(self.engine).get_columns('tagcheck_equipment')})

    def test_normalize_existing_tags_preserves_ids_and_tenants(self):
        self.migrate()
        with Session(self.engine) as db:
            companies = [Company(name=name, slug='normalize-'+name) for name in ('a', 'b')]
            db.add_all(companies); db.flush()
            items = [Equipment(company_id=company.id, tag=tag, name='Original', photo='original.png', notes='Keep')
                     for company, tag in zip(companies, (' demo-001 ', 'Demo-001'))]
            items.append(Equipment(company_id=companies[0].id, tag=' straße-é ', name='Unicode', photo='unicode.png'))
            db.add_all(items); db.commit()
        with self.engine.connect() as c:
            before = [dict(row) for row in c.execute(text('SELECT * FROM tagcheck_equipment ORDER BY id')).mappings()]
        self.migrate()
        self.migrate()
        with self.engine.connect() as c:
            after = [dict(row) for row in c.execute(text('SELECT * FROM tagcheck_equipment ORDER BY id')).mappings()]
        expected = [{**row, 'tag': row['tag'].strip().upper()} for row in before]
        self.assertEqual(after, expected)
        self.assertEqual([row['tag'] for row in after], ['DEMO-001', 'DEMO-001', 'STRASSE-É'])

    def test_legacy_case_collision_rolls_back_schema_and_all_rows(self):
        self.legacy_table()
        with self.engine.begin() as c:
            c.execute(text("INSERT INTO tagcheck_equipment(tag,name,photo) VALUES(' legacy ','Duplicate','second.png')"))
            c.execute(text("INSERT INTO tagcheck_equipment(tag,name,photo) VALUES('other','Other','third.png')"))
        with self.engine.connect() as c:
            before = c.execute(text('SELECT * FROM tagcheck_equipment ORDER BY id')).all()
        for _ in range(2):
            with self.assertRaisesRegex(RuntimeError, 'normalized TAG collision within company'):
                self.migrate()
            self.assertEqual(inspect(self.engine).get_table_names(), ['tagcheck_equipment'])
            with self.engine.connect() as c:
                self.assertEqual(c.execute(text('SELECT * FROM tagcheck_equipment ORDER BY id')).all(), before)

    def test_unicode_collision_leaves_existing_schema_and_tags_unchanged(self):
        result = self.migrate()
        with Session(self.engine) as db:
            db.add_all([Equipment(company_id=result['default_company_id'], tag=tag, name='Keep', photo='keep.png')
                        for tag in ('straße', 'STRASSE', 'unrelated')])
            db.commit()
        with self.engine.connect() as c:
            before = c.execute(text('SELECT * FROM tagcheck_equipment ORDER BY id')).all()
        indexes = inspect(self.engine).get_indexes('tagcheck_equipment')
        with self.assertRaisesRegex(RuntimeError, 'normalized TAG collision within company'):
            self.migrate()
        with self.engine.connect() as c:
            self.assertEqual(c.execute(text('SELECT * FROM tagcheck_equipment ORDER BY id')).all(), before)
        self.assertEqual(inspect(self.engine).get_indexes('tagcheck_equipment'), indexes)


class SQLiteTagUniquenessTests(TagUniquenessCases, unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='tag-uniqueness-')
        self.addCleanup(self.tmp.cleanup)
        self.engine = make_engine('sqlite:///' + (Path(self.tmp.name) / 'test.db').as_posix())
        self.addCleanup(self.engine.dispose)
        self.password = secrets.token_urlsafe(24)

    def test_inline_legacy_unique_preserved_without_table_rebuild(self):
        self.legacy_table(inline=True)
        self.migrate()
        self.migrate()
        with self.engine.connect() as c:
            self.assertEqual(c.scalar(text('SELECT id FROM tagcheck_equipment')), self.legacy_id)
        # SQLite cannot drop its inline UNIQUE autoindex without rebuilding.
        self.assertTrue(any(c['column_names'] == ['tag'] for c in
                            inspect(self.engine).get_unique_constraints('tagcheck_equipment')))


@unittest.skipUnless(os.getenv('TAGCHECK_TEST_POSTGRES') == '1', 'PostgreSQL explicitly opt-in')
class PostgreSQLTagUniquenessTests(TagUniquenessCases, unittest.TestCase):
    def setUp(self):
        url = make_url(os.environ['DATABASE_URL'].replace('postgres://', 'postgresql://', 1))
        if url.get_backend_name() != 'postgresql' or url.database != 'tagcheck_fase2_test':
            raise RuntimeError('Only PostgreSQL tagcheck_fase2_test is allowed')
        self.root = make_engine(url)
        self.addCleanup(self.root.dispose)
        self.schema = 'test_tag_uniqueness_' + secrets.token_hex(12)
        with self.root.begin() as c:
            c.execute(text('CREATE SCHEMA ' + self.schema))
        self.addCleanup(self.drop_schema)
        self.engine = make_engine(url.update_query_dict({'options': '-csearch_path=' + self.schema}))
        self.addCleanup(self.engine.dispose)
        self.password = secrets.token_urlsafe(24)

    def drop_schema(self):
        with self.root.begin() as c:
            c.execute(text('DROP SCHEMA ' + self.schema + ' CASCADE'))

    def test_legacy_global_constraint_replaced(self):
        self.legacy_table(inline=True)
        self.migrate()
        self.assert_company_uniqueness()
        self.assertFalse(any(c['column_names'] == ['tag'] for c in
                             inspect(self.engine).get_unique_constraints('tagcheck_equipment')))


if __name__ == '__main__':
    unittest.main(verbosity=2)
