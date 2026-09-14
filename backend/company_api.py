"""Company administration: every local operation uses the validated session."""
from io import BytesIO
import json
import secrets
import warnings
from pathlib import PurePath
from typing import Literal
from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile
from PIL import Image, UnidentifiedImageError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
if __package__:
    from .models import Company, User, UserCompany
    from .admin_api import NewUser, UserState, ResetPassword, commit
    from .passwords import hash_password
else:
    from models import Company, User, UserCompany
    from admin_api import NewUser, UserState, ResetPassword, commit
    from passwords import hash_password

LocalRole = Literal['supervisor', 'operator', 'viewer']

class CompanyUserCreate(NewUser):
    role: LocalRole

class CompanyUserUpdate(UserState):
    role: LocalRole | None = None


def identity(c):
    return {'name': c.name, 'logo_url': c.logo_url, 'active': c.active}


def local_user(user, link):
    return {'id': user.id, 'name': user.name, 'email': user.email, 'role': link.role,
            'active': bool(user.active and link.active), 'membership_active': link.active}


def validate_domain(company, email):
    domains = json.loads(company.email_domains or '[]')
    exceptions = json.loads(company.email_exceptions or '[]')
    # Empty configuration keeps migrated accounts usable; policy applies to new emails.
    if domains and email.rsplit('@', 1)[-1] not in domains and email not in exceptions:
        raise HTTPException(422, 'E-mail fora dos domínios autorizados para esta empresa.')


def build_company_router(auth):
    router = APIRouter()

    def administrator(context=Depends(auth.current)):
        if context.role != 'company_admin' or context.is_superadmin:
            raise HTTPException(403, 'Administrador da empresa necessário.')
        return context

    def target(db, context, user_id):
        row = db.execute(select(User, UserCompany).join(UserCompany).where(
            User.id == user_id, UserCompany.company_id == context.company_id,
            User.is_superadmin.is_(False))).first()
        if row is None:
            raise HTTPException(404, 'Usuário não encontrado.')
        user, link = row
        if link.role == 'company_admin':
            raise HTTPException(403, 'Alteração reservada ao suporte administrativo.')
        return user, link

    @router.get('/company')
    def current_company(context=Depends(administrator)):
        with auth.sessions() as db:
            return identity(db.get(Company, context.company_id))

    @router.get('/company/users')
    def users(context=Depends(administrator)):
        with auth.sessions() as db:
            return [local_user(u, m) for u, m in db.execute(select(User, UserCompany).join(UserCompany).where(
                UserCompany.company_id == context.company_id, User.is_superadmin.is_(False)).order_by(User.name, User.id))]

    @router.post('/company/users', status_code=201)
    def create_user(payload: CompanyUserCreate, context=Depends(administrator)):
        if not payload.name.strip():
            raise HTTPException(422, 'Nome obrigatório.')
        with auth.sessions() as db:
            validate_domain(db.get(Company, context.company_id), payload.email)
            user = User(name=payload.name.strip(), email=payload.email, password_hash=hash_password(payload.password),
                        active=True, is_superadmin=False)
            db.add(user)
            try:
                db.flush()
            except IntegrityError:
                db.rollback()
                raise HTTPException(409, 'Não foi possível cadastrar este e-mail.') from None
            link = UserCompany(user_id=user.id, company_id=context.company_id, role=payload.role, active=payload.active)
            db.add(link)
            commit(db)
            return local_user(user, link)

    def check_shared(db, user, company_id):
        if db.scalar(select(UserCompany.id).where(UserCompany.user_id == user.id, UserCompany.company_id != company_id)):
            raise HTTPException(409, 'Alteração reservada ao suporte administrativo.')

    @router.patch('/company/users/{user_id}')
    def update_user(user_id: int, payload: CompanyUserUpdate, context=Depends(administrator)):
        with auth.sessions() as db:
            user, link = target(db, context, user_id)
            if payload.name is not None or payload.email is not None:
                check_shared(db, user, context.company_id)
            if payload.email is not None and payload.email != user.email:
                validate_domain(db.get(Company, context.company_id), payload.email)
                user.email = payload.email
            if payload.name is not None:
                user.name = payload.name
            if payload.role is not None:
                link.role = payload.role
            if payload.active is not None:
                link.active = payload.active
            commit(db)
            return local_user(user, link)

    @router.post('/company/users/{user_id}/reset-password')
    def reset(user_id: int, payload: ResetPassword, context=Depends(administrator)):
        with auth.sessions() as db:
            user, link = target(db, context, user_id)
            check_shared(db, user, context.company_id)
            user.password_hash = hash_password(payload.password)
            commit(db)
            return {'ok': True}

    async def save_logo(company_id, file, request):
        form = await request.form()
        if set(form.keys()) != {'file'} or len(form.getlist('file')) != 1:
            raise HTTPException(422, 'Envie apenas o arquivo da logo.')
        formats = {'.png': ('image/png', 'PNG'), '.jpg': ('image/jpeg', 'JPEG'),
                   '.jpeg': ('image/jpeg', 'JPEG'), '.webp': ('image/webp', 'WEBP')}
        expected = formats.get(PurePath(file.filename or '').suffix.lower())
        if not expected or file.content_type != expected[0]:
            raise HTTPException(422, 'Use PNG, JPG ou WEBP.')
        raw = await file.read(2 * 1024 * 1024 + 1)
        if not raw or len(raw) > 2 * 1024 * 1024:
            raise HTTPException(422, 'Envie uma imagem de até 2 MB.')
        try:
            with warnings.catch_warnings():
                warnings.simplefilter('error', Image.DecompressionBombWarning)
                with Image.open(BytesIO(raw)) as img:
                    if img.format != expected[1] or img.width * img.height > 16_000_000:
                        raise ValueError()
                    img.verify()
                # Decode and re-encode: strip metadata, trailing payloads and animation.
                with Image.open(BytesIO(raw)) as img:
                    img.load()
                    output = BytesIO()
                    img.convert('RGB' if expected[1] == 'JPEG' else 'RGBA').save(output, format=expected[1])
                    clean = output.getvalue()
                if len(clean) > 2 * 1024 * 1024:
                    raise ValueError()
        except (ValueError, OSError, UnidentifiedImageError, Image.DecompressionBombError, Image.DecompressionBombWarning):
            raise HTTPException(422, 'Imagem inválida ou muito grande.') from None
        with auth.sessions() as db:
            company = db.get(Company, company_id)
            if not company:
                raise HTTPException(404, 'Empresa não encontrada.')
            company.logo_data, company.logo_mime = clean, expected[0]
            company.logo_url = '/company/logo?v=' + secrets.token_hex(16)
            commit(db)
            return identity(company)

    def remove_logo(company_id):
        with auth.sessions() as db:
            company = db.get(Company, company_id)
            if not company:
                raise HTTPException(404, 'Empresa não encontrada.')
            company.logo_data = company.logo_mime = company.logo_url = None
            commit(db)
            return identity(company)

    def read_logo(company_id):
        with auth.sessions() as db:
            company = db.get(Company, company_id)
            if not company or not company.logo_data:
                raise HTTPException(404, 'Logo não encontrada.')
            return Response(company.logo_data, media_type=company.logo_mime,
                            headers={'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'})

    @router.post('/company/logo')
    async def upload_logo(request: Request, file: UploadFile = File(...), context=Depends(administrator)):
        return await save_logo(context.company_id, file, request)

    @router.delete('/company/logo')
    def delete_logo(context=Depends(administrator)):
        return remove_logo(context.company_id)

    @router.get('/company/logo')
    def get_logo(context=Depends(auth.current)):
        return read_logo(context.company_id)

    @router.post('/companies/{company_id}/logo')
    async def global_upload(company_id: int, request: Request, file: UploadFile = File(...), _=Depends(auth.superadmin)):
        return await save_logo(company_id, file, request)

    @router.delete('/companies/{company_id}/logo')
    def global_delete(company_id: int, _=Depends(auth.superadmin)):
        return remove_logo(company_id)

    @router.get('/companies/{company_id}/logo')
    def global_read(company_id: int, _=Depends(auth.superadmin)):
        return read_logo(company_id)

    return router
