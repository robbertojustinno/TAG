"""Database models. Importing this module never opens or migrates a database."""
from datetime import datetime, timezone
from sqlalchemy import (Boolean, CheckConstraint, Column, DateTime, ForeignKey,
                        Integer, String, Text, LargeBinary, UniqueConstraint, select, false)
from sqlalchemy.orm import declarative_base, relationship, deferred

Base = declarative_base()
DEFAULT_COMPANY_SLUG = 'empresa-padrao'
ROLES = ('company_admin', 'supervisor', 'operator', 'viewer')

def utcnow():
    return datetime.now(timezone.utc)

class Company(Base):
    __tablename__ = 'companies'
    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    slug = Column(String(100), nullable=False, unique=True, index=True)
    logo_url = Column(String(300), nullable=True)
    logo_data = deferred(Column(LargeBinary, nullable=True))
    logo_mime = Column(String(30), nullable=True)
    admin_email = Column(String(254), nullable=True)
    email_domains = Column(Text, nullable=True)
    email_exceptions = Column(Text, nullable=True)
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    units = relationship('Unit', back_populates='company', passive_deletes='all')

class Unit(Base):
    __tablename__ = 'units'
    __table_args__ = (UniqueConstraint('company_id', 'slug', name='uq_unit_company_slug'),)
    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey('companies.id', ondelete='RESTRICT'), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    slug = Column(String(100), nullable=False)
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    company = relationship('Company', back_populates='units')

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    email = Column(String(254), nullable=False, unique=True, index=True)
    password_hash = Column(String(512), nullable=False)
    must_change_password = Column(Boolean, nullable=False, default=False, server_default=false())
    active = Column(Boolean, nullable=False, default=True)
    is_superadmin = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

class UserCompany(Base):
    __tablename__ = 'user_companies'
    __table_args__ = (
        UniqueConstraint('user_id', 'company_id', name='uq_user_company'),
        CheckConstraint("role IN ('company_admin','supervisor','operator','viewer')", name='ck_user_company_role'),
    )
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='RESTRICT'), nullable=False, index=True)
    company_id = Column(Integer, ForeignKey('companies.id', ondelete='RESTRICT'), nullable=False, index=True)
    role = Column(String(30), nullable=False)
    active = Column(Boolean, nullable=False, default=True)

class AssetCategory(Base):
    __tablename__ = 'asset_categories'
    __table_args__ = (UniqueConstraint('company_id', 'parent_id', 'slug', name='uq_asset_category_company_parent_slug'),)
    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey('companies.id', ondelete='RESTRICT'), nullable=False, index=True)
    parent_id = Column(Integer, ForeignKey('asset_categories.id', ondelete='RESTRICT'), nullable=True, index=True)
    name = Column(String(200), nullable=False)
    slug = Column(String(100), nullable=False)
    active = Column(Boolean, nullable=False, default=True)
    sort_order = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    parent = relationship('AssetCategory', remote_side=[id], back_populates='children')
    children = relationship('AssetCategory', back_populates='parent', passive_deletes=True)
    company = relationship('Company')

def legacy_company_default(context):
    """Compatibility for existing Python integrations; API writes set company explicitly."""
    company_id = context.connection.execute(select(Company.id).where(Company.slug == DEFAULT_COMPANY_SLUG)).scalar_one()
    return company_id

class Equipment(Base):
    __tablename__ = 'tagcheck_equipment'
    __table_args__ = (
        UniqueConstraint('company_id', 'tag', name='uq_equipment_company_tag'),
    )
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey('companies.id', ondelete='RESTRICT'), nullable=False,
                        index=True, default=legacy_company_default)
    unit_id = Column(Integer, ForeignKey('units.id', ondelete='RESTRICT'), nullable=True, index=True)
    category_id = Column(Integer, ForeignKey('asset_categories.id', ondelete='RESTRICT'), nullable=True, index=True)
    unit = relationship('Unit')
    category = relationship('AssetCategory')
    tag = Column(String, index=True, nullable=False)
    name = Column(String, nullable=False)
    photo = Column(String, nullable=False)
    equipment_type = Column(String, nullable=True)
    sector = Column(String, nullable=True)
    location = Column(String, nullable=True)
    manufacturer = Column(String, nullable=True)
    model = Column(String, nullable=True)
    serial_number = Column(String, nullable=True)
    calibration_date = Column(String, nullable=True)
    next_calibration_date = Column(String, nullable=True)
    status = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
