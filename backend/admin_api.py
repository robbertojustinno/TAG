"""Authentication and superadmin endpoints, with explicit safe response fields."""
from typing import Literal
import re
import json
from fastapi import APIRouter, Depends, Header, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
if __package__:
    from .models import Company, Unit, User, UserCompany
    from .passwords import hash_password, verify_password
else:
    from models import Company, Unit, User, UserCompany
    from passwords import hash_password, verify_password

Role = Literal['company_admin','supervisor','operator','viewer']

class Input(BaseModel):
    model_config = ConfigDict(extra='forbid')

class LoginPayload(Input):
    username: str | None = Field(default=None, max_length=254)
    email: str | None = Field(default=None, max_length=254)
    password: str = Field(max_length=1024)

class SelectCompany(Input):
    company_id: int = Field(gt=0, strict=True)

class NewCompany(Input):
    name: str = Field(min_length=1, max_length=200)
    slug: str = Field(pattern=r'^[a-z0-9]+(?:-[a-z0-9]+)*$', max_length=100)

class CompanyState(Input):
    active: bool

class CompanyUpdate(Input):
    name: str | None = Field(default=None, max_length=200)
    slug: str | None = Field(default=None, pattern=r'^[a-z0-9]+(?:-[a-z0-9]+)*$', max_length=100)
    active: bool | None = None
    admin_email: str | None = Field(default=None, max_length=254)
    email_domains: list[str] | None = Field(default=None, max_length=100)
    email_exceptions: list[str] | None = Field(default=None, max_length=100)

    @field_validator('email_domains', 'email_exceptions')
    @classmethod
    def validate_email_policy(cls, values, info):
        if values is None:
            raise ValueError('Use an empty list to clear the policy')
        result = []
        for value in values:
            value = value.strip().lower()
            pattern = r'[^\s@]+@[^\s@]+\.[^\s@]+' if info.field_name == 'email_exceptions' else r'(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}'
            if len(value) > 254 or not re.fullmatch(pattern, value):
                raise ValueError('Invalid email policy')
            result.append(value)
        return sorted(set(result))

    @field_validator('admin_email')
    @classmethod
    def validate_admin_email(cls, value):
        if value is None or value == '':
            return None
        return NewUser.normalize_email(value)

    @field_validator('name')
    @classmethod
    def normalize_company_name(cls, value):
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError('Company name is required')
        return value

class NewUser(Input):
    name: str = Field(min_length=1, max_length=200)
    email: str = Field(max_length=254)
    password: str = Field(min_length=12, max_length=1024)
    active: bool = True

    @field_validator('email')
    @classmethod
    def normalize_email(cls, value):
        value = value.strip().lower()
        if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', value):
            raise ValueError('Invalid email')
        return value

class UserState(Input):
    name: str | None = Field(default=None, max_length=200)
    email: str | None = Field(default=None, max_length=254)
    active: bool | None = None

    @field_validator('name')
    @classmethod
    def normalize_user_name(cls, value):
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError('User name is required')
        return value

    @field_validator('email')
    @classmethod
    def normalize_user_email(cls, value):
        if value is None:
            return None
        value = value.strip().lower()
        if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', value):
            raise ValueError('Invalid email')
        return value

class ResetPassword(Input):
    password: str = Field(min_length=12, max_length=1024)

class Membership(Input):
    company_id: int = Field(gt=0, strict=True)
    role: Role
    active: bool = True

def company_json(c):
    return {'id': c.id, 'name': c.name, 'slug': c.slug, 'active': c.active, 'created_at': c.created_at, 'logo_url': c.logo_url, 'admin_email': c.admin_email,
            'email_domains': json.loads(c.email_domains or '[]'),
            'email_exceptions': json.loads(c.email_exceptions or '[]')}

def user_json(u):
    return {'id': u.id, 'name': u.name, 'email': u.email, 'active': u.active,
            'is_superadmin': u.is_superadmin, 'created_at': u.created_at}

def unit_json(unit):
    return {'id': unit.id, 'company_id': unit.company_id, 'name': unit.name,
            'slug': unit.slug, 'active': unit.active, 'created_at': unit.created_at}

def commit(db):
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'Record conflicts with an existing value') from None

def build_router(auth):
    router = APIRouter()

    def unit_admin(context=Depends(auth.current)):
        if not context.is_superadmin and context.role != 'company_admin':
            raise HTTPException(403, 'Company administrator required')
        return context

    @router.get('/units')
    def units(context=Depends(auth.current)):
        with auth.sessions() as db:
            return [unit_json(unit) for unit in db.scalars(
                select(Unit).where(Unit.company_id == context.company_id).order_by(Unit.id))]

    @router.post('/units', status_code=201)
    def create_unit(payload: NewCompany, context=Depends(unit_admin)):
        if not payload.name.strip():
            raise HTTPException(422, 'Unit name is required')
        with auth.sessions() as db:
            unit = Unit(company_id=context.company_id, name=payload.name.strip(), slug=payload.slug)
            db.add(unit)
            commit(db)
            return unit_json(unit)

    @router.patch('/units/{unit_id}')
    def unit_state(unit_id: int, payload: CompanyState, context=Depends(unit_admin)):
        with auth.sessions() as db:
            unit = db.scalar(select(Unit).where(Unit.id == unit_id, Unit.company_id == context.company_id))
            if not unit:
                raise HTTPException(404, 'Unit not found')
            unit.active = payload.active
            commit(db)
            return unit_json(unit)

    # Equal-cost password verification for unknown accounts.
    import secrets
    dummy_hash = hash_password(secrets.token_urlsafe(32))

    @router.post('/auth/login')
    def login(payload: LoginPayload, response: Response):
        response.headers['Cache-Control'] = 'no-store'
        response.headers['Pragma'] = 'no-cache'
        legacy = payload.email is None and (payload.username or '').strip() == auth.username
        with auth.sessions() as db:
            if legacy:
                user = db.get(User, auth.legacy_user_id)
            else:
                email = (payload.email or payload.username or '').strip().lower()
                user = db.scalar(select(User).where(User.email == email))
            valid = verify_password(user.password_hash if user else dummy_hash, payload.password)
            if not valid or user is None:
                raise HTTPException(401, 'Invalid login credentials')
            if not user.active:
                raise HTTPException(403, 'User is inactive')
            companies = auth.permitted_companies(db, user.id)
            if legacy:
                companies = [(c, m) for c, m in companies if c.id == auth.default_company_id]
            if not companies:
                raise HTTPException(403, 'No active company is associated with this user')
            if len(companies) > 1:
                return {'ok': True, 'requires_company_selection': True,
                        'selection_token': auth.issue(user, purpose='selection', ttl=300),
                        'expires_in': 300,
                        'companies': [{'id': c.id, 'name': c.name, 'slug': c.slug, 'role': m.role} for c, m in companies]}
            _, link = companies[0]
            return {'ok': True, 'requires_company_selection': False,
                    'token': auth.issue(user, link, legacy=legacy), 'expires_in': 28800,
                    'username': auth.username if legacy else user.name, 'user_id': user.id,
                    'email': user.email, 'company_id': link.company_id, 'role': link.role,
                    'is_superadmin': bool(user.is_superadmin)}

    @router.post('/auth/select-company')
    def select_company(payload: SelectCompany, response: Response, authorization: str | None = Header(default=None)):
        token = auth.bearer(authorization)
        # Accept either a short-lived selection credential or an established session.
        try:
            claims = auth.decode(token, 'selection')
        except HTTPException:
            claims = auth.decode(token, 'session')
        with auth.sessions() as db:
            user = auth.validate_identity(db, claims)
            if claims.get('legacy') and payload.company_id != auth.default_company_id:
                raise HTTPException(403, 'Use email login to select another company')
            if claims['purpose'] == 'session':
                auth.membership(db, user.id, claims['company_id'])
            link = auth.membership(db, user.id, payload.company_id)
            response.headers['Cache-Control'] = 'no-store'
            return {'ok': True, 'token': auth.issue(user, link, legacy=bool(claims.get('legacy'))),
                    'expires_in': 28800, 'user_id': user.id, 'email': user.email,
                    'company_id': link.company_id, 'role': link.role, 'is_superadmin': bool(user.is_superadmin)}

    @router.get('/auth/me')
    def me(context=Depends(auth.current)):
        with auth.sessions() as db:
            company = db.get(Company, context.company_id)
            company_name, logo_url = company.name, company.logo_url
        return {'user_id': context.user_id, 'email': context.email, 'company_id': context.company_id,
                'company_name': company_name, 'logo_url': logo_url,
                'role': context.role, 'is_superadmin': context.is_superadmin}

    @router.get('/companies')
    def companies(_=Depends(auth.superadmin)):
        with auth.sessions() as db:
            return [company_json(c) for c in db.scalars(select(Company).order_by(Company.id))]

    @router.post('/companies', status_code=201)
    def create_company(payload: NewCompany, _=Depends(auth.superadmin)):
        with auth.sessions() as db:
            if not payload.name.strip():
                raise HTTPException(422, 'Company name is required')
            item = Company(name=payload.name.strip(), slug=payload.slug)
            db.add(item)
            commit(db)
            return company_json(item)

    @router.patch('/companies/{company_id}')
    def company_state(company_id: int, payload: CompanyUpdate, _=Depends(auth.superadmin)):
        if payload.active is False and company_id == _.company_id:
            raise HTTPException(409, 'Select another active company before disabling the current one')
        with auth.sessions() as db:
            item = db.get(Company, company_id)
            if not item:
                raise HTTPException(404, 'Company not found')
            for field in ('email_domains', 'email_exceptions'):
                if field in payload.model_fields_set:
                    setattr(item, field, json.dumps(getattr(payload, field)))
            if 'admin_email' in payload.model_fields_set:
                item.admin_email = payload.admin_email
            if payload.name is not None:
                item.name = payload.name
            if payload.slug is not None:
                item.slug = payload.slug
            if payload.active is not None:
                item.active = payload.active
            commit(db)
            return company_json(item)

    @router.get('/users')
    def users(_=Depends(auth.superadmin)):
        with auth.sessions() as db:
            return [user_json(u) for u in db.scalars(select(User).order_by(User.id))]

    @router.post('/users', status_code=201)
    def create_user(payload: NewUser, _=Depends(auth.superadmin)):
        with auth.sessions() as db:
            if not payload.name.strip():
                raise HTTPException(422, 'User name is required')
            user = User(name=payload.name.strip(), email=payload.email, password_hash=hash_password(payload.password),
                        active=payload.active, is_superadmin=False)
            db.add(user)
            commit(db)
            return user_json(user)

    @router.patch('/users/{user_id}')
    def user_state(user_id: int, payload: UserState, _=Depends(auth.superadmin)):
        if payload.active is False and user_id == _.user_id:
            raise HTTPException(409, 'Cannot disable your own administration account')
        with auth.sessions() as db:
            user = db.get(User, user_id)
            if not user:
                raise HTTPException(404, 'User not found')
            if payload.name is not None:
                user.name = payload.name
            if payload.email is not None:
                user.email = payload.email
            if payload.active is not None:
                user.active = payload.active
            commit(db)
            return user_json(user)

    @router.post('/users/{user_id}/reset-password')
    def reset_password(user_id: int, payload: ResetPassword, _=Depends(auth.superadmin)):
        with auth.sessions() as db:
            user = db.get(User, user_id)
            if not user:
                raise HTTPException(404, 'User not found')
            user.password_hash = hash_password(payload.password)
            commit(db)
            return {'ok': True}

    @router.get('/users/{user_id}/companies')
    def memberships(user_id: int, _=Depends(auth.superadmin)):
        with auth.sessions() as db:
            if not db.get(User, user_id):
                raise HTTPException(404, 'User not found')
            return [{'id': link.id, 'user_id': link.user_id, 'company_id': link.company_id,
                     'role': link.role, 'active': link.active}
                    for link in db.scalars(select(UserCompany).where(UserCompany.user_id == user_id)
                                           .order_by(UserCompany.company_id))]

    @router.post('/users/{user_id}/companies')
    def associate(user_id: int, payload: Membership, _=Depends(auth.superadmin)):
        with auth.sessions() as db:
            if not db.get(User, user_id) or not db.get(Company, payload.company_id):
                raise HTTPException(404, 'User or company not found')
            link = db.scalar(select(UserCompany).where(UserCompany.user_id == user_id, UserCompany.company_id == payload.company_id))
            if link is None:
                link = UserCompany(user_id=user_id, company_id=payload.company_id)
                db.add(link)
            link.role, link.active = payload.role, payload.active
            commit(db)
            return {'id': link.id, 'user_id': link.user_id, 'company_id': link.company_id, 'role': link.role, 'active': link.active}

    return router
