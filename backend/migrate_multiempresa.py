"""Additive, idempotent migration. No tables, rows or legacy IDs are removed."""
import os
from sqlalchemy import create_engine, event, inspect, select, text
from sqlalchemy.orm import Session
if __package__:
    from .models import Base, Company, Unit, User, UserCompany, Equipment, DEFAULT_COMPANY_SLUG
    from .passwords import hash_password, verify_password
else:
    from models import Base, Company, Unit, User, UserCompany, Equipment, DEFAULT_COMPANY_SLUG
    from passwords import hash_password, verify_password

def make_engine(url):
    engine = create_engine(url, pool_pre_ping=True, future=True)
    if engine.dialect.name == 'sqlite':
        @event.listens_for(engine, 'connect')
        def sqlite_foreign_keys(connection, _):
            connection.execute('PRAGMA foreign_keys=ON')
    return engine

def migrate(engine, username, password, email):
    if engine.dialect.name not in ('sqlite', 'postgresql'):
        raise RuntimeError('Migration supports PostgreSQL and SQLite only')
    with engine.begin() as connection:
        if engine.dialect.name == 'sqlite':
            # Explicit BEGIN includes DDL in the transaction in sqlite3 legacy mode.
            connection.exec_driver_sql('BEGIN IMMEDIATE')
        else:
            connection.execute(text('SELECT pg_advisory_xact_lock(2026091002)'))
        existing = inspect(connection).has_table('tagcheck_equipment')
        before = connection.execute(text('SELECT COUNT(*) FROM tagcheck_equipment')).scalar_one() if existing else 0
        Base.metadata.create_all(connection, tables=[Company.__table__, Unit.__table__, User.__table__, UserCompany.__table__])
        with Session(bind=connection) as db:
            company = db.scalar(select(Company).where(Company.slug == DEFAULT_COMPANY_SLUG))
            if company is None:
                company = Company(name='Empresa Padrão', slug=DEFAULT_COMPANY_SLUG)
                db.add(company)
                db.flush()
            company_id = company.id
            # ADMIN_EMAIL is the stable identity behind the environment's legacy
            # username. Do not match User.name: display names are not unique.
            user = db.scalar(select(User).where(User.email == email.lower().strip()))
            if user is None:
                user = User(name=username, email=email.lower().strip(), password_hash=hash_password(password), is_superadmin=True)
                db.add(user)
                db.flush()
                db.add(UserCompany(user_id=user.id, company_id=company_id, role='company_admin'))
                db.flush()
            elif not verify_password(user.password_hash, password):
                # The environment remains authoritative for the legacy credential.
                # Replacing the hash also changes Tenancy.credential_stamp, revoking
                # previously issued JWTs without changing memberships or user state.
                user.password_hash = hash_password(password)
                db.flush()
            user_id = user.id
        if not existing:
            Equipment.__table__.create(connection)
        else:
            columns = {column['name'] for column in inspect(connection).get_columns('tagcheck_equipment')}
            if 'company_id' not in columns:
                connection.execute(text('ALTER TABLE tagcheck_equipment ADD COLUMN company_id INTEGER REFERENCES companies(id)'))
            # Preserve the existing optional-column upgrade for older installations.
            for name in ('equipment_type', 'sector', 'location', 'manufacturer', 'model', 'serial_number', 'calibration_date', 'next_calibration_date', 'status', 'notes'):
                if name not in columns:
                    connection.execute(text(f'ALTER TABLE tagcheck_equipment ADD COLUMN "{name}" TEXT'))
        reassigned = connection.execute(text('UPDATE tagcheck_equipment SET company_id=:company WHERE company_id IS NULL'), {'company': company_id}).rowcount
        orphaned = connection.execute(text('SELECT COUNT(*) FROM tagcheck_equipment e LEFT JOIN companies c ON e.company_id=c.id WHERE c.id IS NULL')).scalar_one()
        if orphaned:
            raise RuntimeError('Migration stopped: invalid existing company association')
        connection.execute(text('CREATE INDEX IF NOT EXISTS ix_tagcheck_equipment_company_id ON tagcheck_equipment(company_id)'))
        if engine.dialect.name == 'postgresql':
            connection.execute(text('ALTER TABLE tagcheck_equipment ALTER COLUMN company_id SET NOT NULL'))
        else:
            # SQLite cannot add NOT NULL + REFERENCES to a populated table without
            # rebuilding it. Triggers enforce NOT NULL without deleting/recreating data.
            for operation in ('INSERT', 'UPDATE'):
                connection.exec_driver_sql(f'''CREATE TRIGGER IF NOT EXISTS equipment_company_required_{operation.lower()}
                    BEFORE {operation} ON tagcheck_equipment WHEN NEW.company_id IS NULL
                    BEGIN SELECT RAISE(ABORT, 'company_id is required'); END''')
            if connection.exec_driver_sql('PRAGMA foreign_key_check').fetchall():
                raise RuntimeError('Migration stopped: foreign key validation failed')
        after = connection.execute(text('SELECT COUNT(*) FROM tagcheck_equipment')).scalar_one()
        if before != after:
            raise RuntimeError('Migration stopped: equipment count changed')
    return {'default_company_id': company_id, 'legacy_user_id': user_id, 'equipment_count': after, 'assigned': reassigned}

if __name__ == '__main__':
    needed = ('DATABASE_URL', 'ADMIN_USERNAME', 'ADMIN_PASSWORD')
    if any(not os.environ.get(key) for key in needed):
        raise SystemExit('Configure DATABASE_URL, ADMIN_USERNAME and ADMIN_PASSWORD')
    url = os.environ['DATABASE_URL'].replace('postgres://', 'postgresql://', 1)
    engine = make_engine(url)
    try:
        result = migrate(engine, os.environ['ADMIN_USERNAME'], os.environ['ADMIN_PASSWORD'], os.getenv('ADMIN_EMAIL', 'legacy-admin@tagcheck.invalid'))
        print('Migration completed; equipment preserved:', result['equipment_count'])
    except Exception:
        raise SystemExit('Migration failed and was rolled back; inspect schema securely') from None
    finally:
        engine.dispose()
