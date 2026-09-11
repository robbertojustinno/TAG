from pathlib import Path
import sys, tempfile, secrets, unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from sqlalchemy import text, inspect
from migrate_multiempresa import make_engine, migrate

class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='tagcheck-migration-')
        self.engine=make_engine('sqlite:///'+str(Path(self.tmp.name)/'migration.db').replace('\\','/'))
        self.password=secrets.token_urlsafe(24)

    def tearDown(self):
        self.engine.dispose(); self.tmp.cleanup()

    def migrate(self):
        return migrate(self.engine,'legacy',self.password,'legacy@example.invalid')

    def test_legacy_rows_ids_and_idempotence(self):
        with self.engine.begin() as c:
            c.execute(text('CREATE TABLE tagcheck_equipment (id INTEGER PRIMARY KEY, tag TEXT UNIQUE NOT NULL, name TEXT NOT NULL, photo TEXT NOT NULL, notes TEXT)'))
            c.execute(text("INSERT INTO tagcheck_equipment VALUES (42, 'LEGACY-42', 'Equipamento original', 'original.png', 'Não perder')"))
        first=self.migrate()
        self.assertEqual(first['assigned'],1)
        with self.engine.connect() as c:
            before=c.execute(text('SELECT * FROM tagcheck_equipment')).mappings().one()
            self.assertEqual(before['id'],42)
            self.assertEqual(before['notes'],'Não perder')
            self.assertEqual(before['company_id'],first['default_company_id'])
            self.assertEqual(c.execute(text('SELECT name FROM companies WHERE id=:id'),{'id':first['default_company_id']}).scalar_one(),'Empresa Padrão')
        self.assertEqual(self.migrate()['assigned'],0)
        with self.engine.connect() as c:
            after=c.execute(text('SELECT * FROM tagcheck_equipment')).mappings().one()
            self.assertEqual(dict(before),dict(after))
            self.assertEqual(c.execute(text('SELECT COUNT(*) FROM users')).scalar_one(),1)

    def test_failure_rolls_back_all_ddl_and_data(self):
        with self.engine.begin() as c:
            c.execute(text('CREATE TABLE tagcheck_equipment (id INTEGER PRIMARY KEY, tag TEXT, name TEXT, photo TEXT, company_id INTEGER)'))
            c.execute(text("INSERT INTO tagcheck_equipment VALUES (7,'old','old','old.png',999)"))
        with self.assertRaisesRegex(RuntimeError,'invalid existing company'):
            self.migrate()
        self.assertEqual(inspect(self.engine).get_table_names(),['tagcheck_equipment'])
        self.assertEqual({c['name'] for c in inspect(self.engine).get_columns('tagcheck_equipment')},{'id','tag','name','photo','company_id'})
        with self.engine.connect() as c:
            self.assertEqual(c.execute(text('SELECT company_id FROM tagcheck_equipment WHERE id=7')).scalar_one(),999)

    def test_constraints_and_nondefault_data_preserved(self):
        from sqlalchemy.exc import IntegrityError
        first=self.migrate()
        with self.engine.begin() as c:
            c.execute(text("INSERT INTO companies (id,name,slug,active,created_at) VALUES (77,'Other','other',1,CURRENT_TIMESTAMP)"))
            c.execute(text("INSERT INTO tagcheck_equipment (id,tag,name,photo,company_id) VALUES (88,'OTHER-88','Other','other.png',77)"))
        self.migrate()
        with self.engine.connect() as c:
            self.assertEqual(c.execute(text('SELECT company_id FROM tagcheck_equipment WHERE id=88')).scalar_one(),77)
        statements=[
            "INSERT INTO tagcheck_equipment(tag,name,photo,company_id) VALUES('x','x','x',NULL)",
            "INSERT INTO tagcheck_equipment(tag,name,photo,company_id) VALUES('x','x','x',999)",
            "INSERT INTO user_companies(user_id,company_id,role,active) VALUES(999,77,'viewer',1)",
            f"INSERT INTO user_companies(user_id,company_id,role,active) VALUES({first['legacy_user_id']},77,'invalid',1)",
            f"INSERT INTO user_companies(user_id,company_id,role,active) VALUES({first['legacy_user_id']},{first['default_company_id']},'viewer',1)",
        ]
        for statement in statements:
            with self.subTest(statement=statement),self.assertRaises(IntegrityError),self.engine.begin() as c:
                c.execute(text(statement))

if __name__=='__main__':unittest.main(verbosity=2)
