"""Add nullable category links without changing existing assets."""
from sqlalchemy import inspect, text

def migrate_categories(connection):
    if 'category_id' not in {c['name'] for c in inspect(connection).get_columns('tagcheck_equipment')}:
        connection.execute(text('ALTER TABLE tagcheck_equipment ADD COLUMN category_id INTEGER REFERENCES tagcheck_asset_categories(id)'))
    connection.execute(text('CREATE INDEX IF NOT EXISTS ix_equipment_category ON tagcheck_equipment(category_id)'))
    connection.execute(text('CREATE UNIQUE INDEX IF NOT EXISTS uq_category_sibling ON tagcheck_asset_categories(COALESCE(parent_id, 0), slug)'))
    for name in ('BOMBAS', 'INSTRUMENTOS', 'MOTORES'):
        connection.execute(text('INSERT INTO tagcheck_asset_categories(name, slug, active, sort_order) VALUES (:name, :slug, true, 0) ON CONFLICT DO NOTHING'), {'name':name, 'slug':name.lower()})

