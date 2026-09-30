"""Additive, transactional, idempotent upgrade; never rewrites existing rows."""
from sqlalchemy import inspect, text

FIELDS = {
    "measurand": "VARCHAR(200)",
    "measurement_unit": "VARCHAR(200)",
    "range_min": "NUMERIC(24, 10)",
    "range_max": "NUMERIC(24, 10)",
    "accuracy_class": "VARCHAR(200)",
    "resolution": "NUMERIC(24, 10)",
    "ema": "NUMERIC(24, 10)",
    "reading_contribution": "NUMERIC(24, 10)",
}

def migrate_metrology(connection):
    existing = {c['name'] for c in inspect(connection).get_columns('tagcheck_equipment')}
    for name, sql_type in FIELDS.items():
        if name not in existing:
            connection.execute(text(f'ALTER TABLE tagcheck_equipment ADD COLUMN "{name}" {sql_type}'))
