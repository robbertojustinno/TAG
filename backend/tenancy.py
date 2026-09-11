"""Central authentication, membership validation and company context."""
from dataclasses import dataclass
import hashlib
import hmac
import re
import secrets
import time
import jwt
from fastapi import Header, HTTPException, Request
from sqlalchemy import select
if __package__:
    from .models import Company, User, UserCompany, Equipment, ROLES
    from .passwords import verify_password
else:
    from models import Company, User, UserCompany, Equipment, ROLES
    from passwords import verify_password

@dataclass(frozen=True)
class CompanyContext:
    user_id: int | None
    email: str | None
    company_id: int
    role: str
    is_superadmin: bool = False
    legacy: bool = False

class Tenancy:
    def __init__(self, sessions, signing_key, default_company_id, legacy_user_id, username, password):
        self.sessions = sessions
        self.key = signing_key
        self.default_company_id = default_company_id
        self.legacy_user_id = legacy_user_id
        self.username = username
        self.password = password

    def credential_stamp(self, user):
        # Opaque credential identifier, not a password verifier: deriving it requires
        # the server-only signing key. A persisted password change revokes every JWT
        # purpose for this user (session, selection and PDF), including normal users.
        return hmac.new(self.key.encode(), user.password_hash.encode(), hashlib.sha256).hexdigest()

    def issue(self, user, membership=None, purpose='session', ttl=28800, legacy=False):
        claims = {'user_id': user.id, 'email': user.email,
                  'company_id': membership.company_id if membership else None,
                  'role': membership.role if membership else None,
                  'is_superadmin': bool(user.is_superadmin), 'exp': int(time.time()) + ttl,
                  'iat': int(time.time()), 'jti': secrets.token_hex(16),
                  'purpose': purpose, 'legacy': legacy, 'credential_stamp': self.credential_stamp(user),
                  'iss': 'tagcheck-backend', 'aud': 'tagcheck:' + purpose}
        return jwt.encode(claims, self.key, algorithm='HS256')

    def decode(self, token, purpose):
        try:
            if len(token) > 8192:
                raise ValueError()
            claims = jwt.decode(token, self.key, algorithms=['HS256'], issuer='tagcheck-backend',
                                audience='tagcheck:' + purpose,
                                options={'require': ['exp','iat','user_id','email','is_superadmin','purpose','credential_stamp']})
            if 'company_id' not in claims or 'role' not in claims:
                raise ValueError()
            if claims['purpose'] != purpose or type(claims['user_id']) is not int:
                raise ValueError()
            if type(claims['exp']) is not int or claims['exp'] <= int(time.time()):
                raise ValueError()
            if type(claims['is_superadmin']) is not bool:
                raise ValueError()
            return claims
        except (jwt.PyJWTError, ValueError, TypeError, KeyError):
            raise HTTPException(401, 'Invalid or expired session') from None

    def validate_identity(self, db, claims):
        user = db.get(User, claims['user_id'])
        if not user or not user.active:
            raise HTTPException(403, 'User is inactive or unavailable')
        if claims['email'] != user.email or not hmac.compare_digest(claims['credential_stamp'], self.credential_stamp(user)):
            raise HTTPException(401, 'Session no longer valid')
        if claims['is_superadmin'] != bool(user.is_superadmin):
            raise HTTPException(403, 'Permissions changed; sign in again')
        return user

    def membership(self, db, user_id, company_id):
        if type(company_id) is not int:
            raise HTTPException(403, 'Select an authorized company')
        link = db.scalar(select(UserCompany).join(Company).where(
            UserCompany.user_id == user_id, UserCompany.company_id == company_id,
            UserCompany.active.is_(True), Company.active.is_(True)))
        if not link or link.role not in ROLES:
            raise HTTPException(403, 'Company membership is inactive or unauthorized')
        return link

    def permitted_companies(self, db, user_id):
        return db.execute(select(Company, UserCompany).join(UserCompany).where(
            UserCompany.user_id == user_id, UserCompany.active.is_(True), Company.active.is_(True))
            .order_by(Company.name, Company.id)).all()

    def old_session(self, token):
        """Accept already-issued pre-migration sessions only for Empresa Padrão."""
        if not re.fullmatch(r'\d+\.[a-f0-9]{64}\.[a-f0-9]{64}', token):
            return None
        expires, nonce, signature = token.split('.')
        payload = expires + '.' + nonce
        expected = hmac.new(self.key.encode(), (self.username+'\0'+self.password+'\0'+payload).encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected) or int(expires) <= int(time.time()):
            raise HTTPException(401, 'Invalid or expired session')
        with self.sessions() as db:
            user = db.get(User, self.legacy_user_id)
            if not user or not user.active or not verify_password(user.password_hash, self.password):
                raise HTTPException(403, 'Legacy user is inactive or credentials changed')
            link = self.membership(db, user.id, self.default_company_id)
            # Pre-migration sessions cannot acquire new global administration powers.
            return CompanyContext(user.id, user.email, link.company_id, link.role, False, True)

    def from_token(self, token, purpose='session'):
        if purpose == 'session':
            old = self.old_session(token)
            if old:
                return old
        claims = self.decode(token, purpose)
        with self.sessions() as db:
            user = self.validate_identity(db, claims)
            link = self.membership(db, user.id, claims['company_id'])
            if claims['role'] != link.role:
                raise HTTPException(403, 'Role changed; sign in again')
            if claims.get('legacy') and link.company_id != self.default_company_id:
                raise HTTPException(403, 'Legacy session is restricted to the default company')
            return CompanyContext(user.id, user.email, link.company_id, link.role, bool(user.is_superadmin), bool(claims.get('legacy')))

    @staticmethod
    def bearer(authorization):
        if not authorization or not authorization.startswith('Bearer '):
            raise HTTPException(401, 'Authentication required')
        return authorization[7:]

    @staticmethod
    def check_company_hint(request, context):
        # Hints never establish context; they must agree with the validated one.
        hints = request.query_params.getlist('company_id')
        if request.headers.get('x-company-id') is not None:
            hints.append(request.headers['x-company-id'])
        for hint in hints:
            if hint != str(context.company_id):
                raise HTTPException(401 if context.user_id is None else 403, 'Company context cannot be overridden')

    def current(self, request: Request, authorization: str | None = Header(default=None)):
        context = self.from_token(self.bearer(authorization))
        self.check_company_hint(request, context)
        return context

    def read_context(self, request: Request, authorization: str | None = Header(default=None)):
        if authorization is not None:
            return self.current(request, authorization)
        with self.sessions() as db:
            company = db.get(Company, self.default_company_id)
            if not company or not company.active:
                raise HTTPException(403, 'Public company is inactive')
        context = CompanyContext(None, None, self.default_company_id, 'viewer')
        self.check_company_hint(request, context)
        return context

    def writer(self, request: Request, authorization: str | None = Header(default=None)):
        context = self.current(request, authorization)
        if context.role not in ('company_admin', 'supervisor', 'operator'):
            raise HTTPException(403, 'Role cannot modify equipment')
        return context

    def deleter(self, request: Request, authorization: str | None = Header(default=None)):
        context = self.current(request, authorization)
        if context.role not in ('company_admin', 'supervisor'):
            raise HTTPException(403, 'Role cannot delete equipment')
        return context

    def superadmin(self, request: Request, authorization: str | None = Header(default=None)):
        context = self.current(request, authorization)
        if not context.is_superadmin:
            raise HTTPException(403, 'Superadmin required')
        return context

def equipment_query(db, context):
    """The only application-level entry point for company-owned equipment queries."""
    return db.query(Equipment).filter(Equipment.company_id == context.company_id)
