"""Authentication and superadmin endpoints, with explicit safe response fields."""
from typing import Literal
import re
from fastapi import APIRouter, Depends, Header, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
if __package__:
    from .models import Company, User, UserCompany
    from .passwords import hash_password, verify_password
else:
    from models import Company, User, UserCompany
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

class NewUser(Input):
    name: str = Field(min_length=1, max_length=200)
    email: str = Field(max_length=254)
    password: str = Field(min_length=12, max_length=1024)
    active: bool = True
    is_superadmin: bool = False

    @field_validator('email')
    @classmethod
    def normalize_email(cls, value):
        value = value.strip().lower()
        if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', value):
            raise ValueError('Invalid email')
        return value

class UserState(Input):
    active: bool

class Membership(Input):
    company_id: int = Field(gt=0, strict=True)
    role: Role
    active: bool = True

def company_json(c):
    return {'id': c.id, 'name': c.name, 'slug': c.slug, 'active': c.active, 'created_at': c.created_at}

def user_json(u):
    return {'id': u.id, 'name': u.name, 'email': u.email, 'active': u.active,
            'is_superadmin': u.is_superadmin, 'created_at': u.created_at}

def commit(db):
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'Record conflicts with an existing value') from None

def build_router(auth):
    router = APIRouter()
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
            company_name = db.get(Company, context.company_id).name
        return {'user_id': context.user_id, 'email': context.email, 'company_id': context.company_id,
                'company_name': company_name,
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
    def company_state(company_id: int, payload: CompanyState, _=Depends(auth.superadmin)):
        if not payload.active and company_id == _.company_id:
            raise HTTPException(409, 'Select another active company before disabling the current one')
        with auth.sessions() as db:
            item = db.get(Company, company_id)
            if not item:
                raise HTTPException(404, 'Company not found')
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
                        active=payload.active, is_superadmin=payload.is_superadmin)
            db.add(user)
            commit(db)
            return user_json(user)

    @router.patch('/users/{user_id}')
    def user_state(user_id: int, payload: UserState, _=Depends(auth.superadmin)):
        if not payload.active and user_id == _.user_id:
            raise HTTPException(409, 'Cannot disable your own administration account')
        with auth.sessions() as db:
            user = db.get(User, user_id)
            if not user:
                raise HTTPException(404, 'User not found')
            user.active = payload.active
            commit(db)
            return user_json(user)

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
