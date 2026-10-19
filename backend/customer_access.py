"""Atomic customer setup and operator-approved, expiring password recovery."""
from datetime import datetime, timezone, timedelta
import hashlib, hmac, secrets
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import Field
from sqlalchemy import select, func, update
from sqlalchemy.exc import IntegrityError
if __package__:
    from .models import Company, User, UserCompany, PasswordRecovery
    from .admin_api import Input, NewCompany, NewUser, commit, company_json, user_json
    from .passwords import hash_password, verify_password
else:
    from models import Company, User, UserCompany, PasswordRecovery
    from admin_api import Input, NewCompany, NewUser, commit, company_json, user_json
    from passwords import hash_password, verify_password

class CustomerSetup(Input):
    company_id: int | None = Field(None, gt=0)
    company: NewCompany | None = None
    trial_days: int | None = Field(None, ge=7, le=10, strict=True)
    administrator: NewUser

class RecoveryRequest(Input):
    email: str = Field(min_length=3, max_length=254)

class RecoveryFinish(Input):
    token: str = Field(min_length=32, max_length=200)
    new_password: str = Field(min_length=12, max_length=1024)
    confirm_password: str = Field(max_length=1024)

def safe_flush(db):
    try: db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409,'Empresa ou e-mail já cadastrado.') from None

def now():
    return datetime.now(timezone.utc)

def aware(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value

def build_customer_router(auth):
    router = APIRouter()
    def digest(value):
        return hmac.new(auth.key.encode(), value.encode(), hashlib.sha256).hexdigest()

    @router.post('/superadmin/onboard', status_code=201)
    def onboard(payload: CustomerSetup, context=Depends(auth.superadmin)):
        if bool(payload.company_id) == bool(payload.company):
            raise HTTPException(422, 'Escolha uma empresa existente ou informe uma nova empresa.')
        with auth.sessions() as db:
            if payload.trial_days is not None and payload.company_id:
                raise HTTPException(422, "Para teste, cadastre uma nova empresa.")
            if payload.company_id:
                company = db.scalar(select(Company).where(Company.id == payload.company_id).with_for_update())
                if not company or not company.active:
                    raise HTTPException(404, 'Empresa ativa não encontrada.')
                if db.scalar(select(UserCompany.id).where(UserCompany.company_id == company.id, UserCompany.role == 'company_admin', UserCompany.active.is_(True)).limit(1)):
                    raise HTTPException(409, 'A empresa já possui administrador. Use a gestão de vínculos.')
            else:
                if not payload.company.name.strip():
                    raise HTTPException(422, 'Informe o nome da empresa.')
                company = Company(name=payload.company.name.strip(), slug=payload.company.slug, admin_email=payload.administrator.email)
                db.add(company); safe_flush(db)
            if not payload.administrator.name.strip() or not payload.administrator.active:
                raise HTTPException(422, 'O administrador deve ter nome e estar ativo.')
            if db.scalar(select(User.id).where(User.email == payload.administrator.email)):
                raise HTTPException(409, 'E-mail já cadastrado. Confira o usuário antes de criar o cliente.')
            user = User(name=payload.administrator.name.strip(), email=payload.administrator.email,
                        password_hash=hash_password(payload.administrator.password), active=True,
                        is_superadmin=False, must_change_password=True)
            db.add(user); safe_flush(db)
            db.add(UserCompany(user_id=user.id, company_id=company.id, role='company_admin', active=True))
            company.trial_days = payload.trial_days
            company.admin_email = user.email
            commit(db)
            return {'company': company_json(company), 'administrator': user_json(user), 'must_change_password': True}

    @router.post('/auth/forgot-password', status_code=202)
    def forgot(payload: RecoveryRequest, request: Request, response: Response):
        response.headers['Cache-Control'] = 'no-store'
        message = {'message':'Se o e-mail estiver cadastrado, a solicitação ficará disponível para o administrador. Contate o responsável para validar sua identidade e receber um link de recuperação.'}
        email = payload.email.strip().lower()
        ed, ip = digest('email:'+email), digest('ip:'+(request.client.host if request.client else 'unknown'))
        with auth.sessions() as db:
            since = now()-timedelta(minutes=15)
            same = db.scalar(select(func.count()).select_from(PasswordRecovery).where(PasswordRecovery.email_digest==ed, PasswordRecovery.created_at>=since))
            total = db.scalar(select(func.count()).select_from(PasswordRecovery).where(PasswordRecovery.ip_digest==ip, PasswordRecovery.created_at>=since))
            if same >= 3 or total >= 20:
                return message
            user = db.scalar(select(User).where(User.email==email, User.active.is_(True)))
            db.add(PasswordRecovery(user_id=user.id if user else None, email_digest=ed, ip_digest=ip))
            commit(db)
        return message

    def authorized_user(db, user_id, context):
        user=db.get(User,user_id)
        if not user or not user.active:
            raise HTTPException(404,'Solicitação indisponível.')
        if not context.is_superadmin:
            # A company admin cannot reset a global identity shared with another
            # company or another administrator. Those requests go to Superadmin.
            links=list(db.scalars(select(UserCompany).where(UserCompany.user_id==user_id)))
            company=db.get(Company,context.company_id)
            if not company or not company.active or user.is_superadmin or len(links)!=1 or links[0].company_id!=context.company_id or not links[0].active or links[0].role=='company_admin':
                raise HTTPException(404,'Solicitação indisponível.')
        return user

    def manager(context=Depends(auth.current)):
        if not context.is_superadmin and context.role!='company_admin':
            raise HTTPException(403,'Administrador necessário.')
        return context

    @router.get('/password-recovery/requests')
    def requests(context=Depends(manager)):
        result=[]
        with auth.sessions() as db:
            rows=db.scalars(select(PasswordRecovery).where(PasswordRecovery.user_id.is_not(None),PasswordRecovery.used_at.is_(None),PasswordRecovery.created_at>=now()-timedelta(days=1)).order_by(PasswordRecovery.id.desc()).limit(200))
            for row in rows:
                try: user=authorized_user(db,row.user_id,context)
                except HTTPException: continue
                result.append({'id':row.id,'name':user.name,'email':user.email,'created_at':row.created_at,'link_issued':row.token_digest is not None})
        return result

    @router.post('/password-recovery/requests/{request_id}/issue')
    def issue(request_id:int, response:Response, context=Depends(manager)):
        response.headers['Cache-Control']='no-store'
        with auth.sessions() as db:
            candidate=db.get(PasswordRecovery,request_id)
            if candidate and candidate.user_id:
                db.scalar(select(User).where(User.id==candidate.user_id).with_for_update())
            row=db.scalar(select(PasswordRecovery).where(PasswordRecovery.id==request_id).with_for_update().execution_options(populate_existing=True))
            if not row or row.user_id is None or row.used_at or aware(row.created_at)<now()-timedelta(days=1):
                raise HTTPException(404,'Solicitação indisponível.')
            user=authorized_user(db,row.user_id,context)
            if user.id == auth.legacy_user_id:
                raise HTTPException(409,'Esta conta de manutenção requer recuperação pelo responsável técnico.')
            token=secrets.token_urlsafe(48)
            # Reissuing revokes all other outstanding links for this account.
            db.execute(update(PasswordRecovery).where(PasswordRecovery.user_id==user.id).values(token_digest=None))
            row.token_digest=digest(token); row.credential_stamp=auth.credential_stamp(user)
            row.expires_at=now()+timedelta(minutes=30); row.approved_by=context.user_id
            commit(db)
            return {'token':token,'expires_in':1800,'email':user.email}

    @router.post('/auth/reset-password')
    def finish(payload:RecoveryFinish,response:Response):
        response.headers['Cache-Control']='no-store'
        if payload.new_password!=payload.confirm_password:
            raise HTTPException(422,'A confirmação deve coincidir com a nova senha.')
        with auth.sessions() as db:
            candidate=db.scalar(select(PasswordRecovery).where(PasswordRecovery.token_digest==digest(payload.token)))
            if candidate and candidate.user_id:
                db.scalar(select(User).where(User.id==candidate.user_id).with_for_update())
            row=db.scalar(select(PasswordRecovery).where(PasswordRecovery.token_digest==digest(payload.token)).with_for_update().execution_options(populate_existing=True))
            if not row or row.used_at or not row.expires_at or aware(row.expires_at)<=now():
                raise HTTPException(400,'Link inválido, expirado ou já utilizado.')
            user=db.scalar(select(User).where(User.id==row.user_id).with_for_update())
            if not user or not user.active or not hmac.compare_digest(row.credential_stamp or '',auth.credential_stamp(user)) or not auth.permitted_companies(db,user.id):
                raise HTTPException(400,'Link inválido, expirado ou já utilizado.')
            if verify_password(user.password_hash,payload.new_password):
                raise HTTPException(422,'Escolha uma senha diferente da anterior.')
            user.password_hash=hash_password(payload.new_password);user.must_change_password=False
            row.used_at=now();row.token_digest=None
            db.execute(update(PasswordRecovery).where(PasswordRecovery.user_id==user.id).values(token_digest=None))
            commit(db)
        return {'message':'Senha alterada. Entre novamente com sua nova senha.'}
    return router
