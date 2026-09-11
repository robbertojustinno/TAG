from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Header, Depends, Response, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
import cloudinary
import cloudinary.uploader
import os
import secrets
import hashlib
import hmac
import time
from io import BytesIO

from sqlalchemy.orm import sessionmaker

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
import qrcode

def required_env(name: str) -> str:
    value = os.environ.get(name)
    if not value or not value.strip():
        raise RuntimeError(f"Required environment variable is missing: {name}")
    return value


DATABASE_URL = required_env("DATABASE_URL")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
ADMIN_USERNAME = required_env("ADMIN_USERNAME")
ADMIN_PASSWORD = required_env("ADMIN_PASSWORD")
# Server-only signing key; never return this value to a client.
ADMIN_TOKEN = required_env("ADMIN_TOKEN")
if len(ADMIN_TOKEN) < 32:
    raise RuntimeError("ADMIN_TOKEN must contain at least 32 characters")
CLOUDINARY_CLOUD_NAME = required_env("CLOUDINARY_CLOUD_NAME")
CLOUDINARY_API_KEY = required_env("CLOUDINARY_API_KEY")
CLOUDINARY_API_SECRET = required_env("CLOUDINARY_API_SECRET")
SESSION_TTL_SECONDS = 8 * 60 * 60

if __package__:
    from .models import Base, Company, Unit, User, UserCompany, Equipment, DEFAULT_COMPANY_SLUG
    from .migrate_multiempresa import make_engine, migrate
    from .tenancy import Tenancy, CompanyContext, equipment_query
    from .admin_api import build_router
else:
    from models import Base, Company, Unit, User, UserCompany, Equipment, DEFAULT_COMPANY_SLUG
    from migrate_multiempresa import make_engine, migrate
    from tenancy import Tenancy, CompanyContext, equipment_query
    from admin_api import build_router

ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "legacy-admin@tagcheck.invalid").strip().lower()
engine = make_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
try:
    MIGRATION = migrate(engine, ADMIN_USERNAME, ADMIN_PASSWORD, ADMIN_EMAIL)
except Exception:
    engine.dispose()
    raise RuntimeError("Database migration failed; no automatic destructive repair was attempted") from None
DEFAULT_COMPANY_ID = MIGRATION["default_company_id"]
LEGACY_USER_ID = MIGRATION["legacy_user_id"]

auth = Tenancy(SessionLocal, ADMIN_TOKEN, DEFAULT_COMPANY_ID, LEGACY_USER_ID, ADMIN_USERNAME, ADMIN_PASSWORD)
app = FastAPI()
app.include_router(build_router(auth))

@app.exception_handler(RequestValidationError)
async def safe_validation_error(request: Request, exc: RequestValidationError):
    # FastAPI's default validation output can echo submitted passwords/tokens.
    return JSONResponse(status_code=422, content={"detail": [
        {"loc": list(e["loc"]), "msg": e["msg"], "type": e["type"]} for e in exc.errors()
    ]})

@app.middleware("http")
async def prevent_private_caching(request: Request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

cloudinary.config(
    cloud_name=CLOUDINARY_CLOUD_NAME,
    api_key=CLOUDINARY_API_KEY,
    api_secret=CLOUDINARY_API_SECRET,
)


def build_qr_payload(item: Equipment) -> str:
    calibration_value = (
        (item.next_calibration_date or "").strip()
        or (item.calibration_date or "").strip()
        or "-"
    )

    equipment_type = (item.equipment_type or "").strip() or "-"

    return (
        f"TAGCHECK | MODO HIBRIDO\n"
        f"TAG: {item.tag}\n"
        f"NOME: {item.name}\n"
        f"TIPO: {equipment_type}\n"
        f"CALIBRACAO: {calibration_value}\n"
        f"DADOS MINIMOS PORQUE TA OFFLINE"
    )


def serialize_equipment(item: Equipment) -> dict:
    return {
        "id": item.id,
        "unit_id": item.unit_id,
        "unit_name": item.unit.name if item.unit is not None else None,
        "tag": item.tag,
        "name": item.name,
        "photo": item.photo,
        "equipment_type": item.equipment_type or "",
        "sector": item.sector or "",
        "location": item.location or "",
        "manufacturer": item.manufacturer or "",
        "model": item.model or "",
        "serial_number": item.serial_number or "",
        "calibration_date": item.calibration_date or "",
        "next_calibration_date": item.next_calibration_date or "",
        "status": item.status or "Ativo",
        "notes": item.notes or "",
        "qr_payload": build_qr_payload(item),
    }
    


@app.get("/")
def root():
    return {"ok": True, "message": "TagCheck backend online"}


@app.get("/health")
def health():
    return {"ok": True}


def validate_equipment_unit(db, unit_id, company_id):
    if unit_id is not None and not db.query(Unit).filter(Unit.id == unit_id, Unit.company_id == company_id).first():
        raise HTTPException(status_code=404, detail="Unit not found in the active company")


@app.post("/equipment")
async def create_equipment(
    tag: str = Form(...),
    name: str = Form(...),
    photo: UploadFile = File(...),
    unit_id: int | None = Form(None, gt=0),
    equipment_type: str = Form(""),
    sector: str = Form(""),
    location: str = Form(""),
    manufacturer: str = Form(""),
    model: str = Form(""),
    serial_number: str = Form(""),
    calibration_date: str = Form(""),
    next_calibration_date: str = Form(""),
    status: str = Form("Ativo"),
    notes: str = Form(""),
    _auth: CompanyContext = Depends(auth.writer),
):
    if not tag.strip():
        raise HTTPException(status_code=400, detail="TAG Ã© obrigatÃ³ria.")
    if not name.strip():
        raise HTTPException(status_code=400, detail="Nome Ã© obrigatÃ³rio.")
    if not photo or not photo.filename:
        raise HTTPException(status_code=400, detail="Foto Ã© obrigatÃ³ria.")

    db = SessionLocal()
    try:
        validate_equipment_unit(db, unit_id, _auth.company_id)
        existing = equipment_query(db, _auth).filter(Equipment.tag == tag.strip()).first()
        if existing:
            raise HTTPException(status_code=400, detail="TAG jÃ¡ cadastrada.")

        result = cloudinary.uploader.upload(
            photo.file,
            folder="tagcheck/equipments" if _auth.company_id == DEFAULT_COMPANY_ID else f"tagcheck/companies/{_auth.company_id}/equipments",
            resource_type="image",
        )
        image_url = result.get("secure_url")
        if not image_url:
            raise HTTPException(status_code=500, detail="Falha ao obter URL da imagem.")

        item = Equipment(
            company_id=_auth.company_id,
            unit_id=unit_id,
            tag=tag.strip(),
            name=name.strip(),
            photo=image_url,
            equipment_type=equipment_type.strip(),
            sector=sector.strip(),
            location=location.strip(),
            manufacturer=manufacturer.strip(),
            model=model.strip(),
            serial_number=serial_number.strip(),
            calibration_date=calibration_date.strip(),
            next_calibration_date=next_calibration_date.strip(),
            status=status.strip() or "Ativo",
            notes=notes.strip(),
        )
        db.add(item)
        db.commit()
        db.refresh(item)

        return serialize_equipment(item)
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Equipment conflicts with an existing record") from None
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Equipment operation failed") from None
    finally:
        db.close()


@app.get("/equipment")
def list_equipment(unit_id: int | None = Query(None, gt=0), _auth: CompanyContext = Depends(auth.read_context)):
    db = SessionLocal()
    try:
        if unit_id is not None:
            if _auth.user_id is None:
                raise HTTPException(status_code=401, detail="Authentication required for unit filters")
            unit = db.query(Unit).filter(Unit.id == unit_id, Unit.company_id == _auth.company_id).first()
            if not unit:
                raise HTTPException(status_code=404, detail="Unit not found in the active company")
        query = equipment_query(db, _auth)
        if unit_id is not None:
            query = query.filter(Equipment.unit_id == unit_id)
        items = query.order_by(Equipment.id.desc()).all()
        return [serialize_equipment(i) for i in items]
    finally:
        db.close()


@app.get("/equipment/tag/{tag}")
def get_by_tag(tag: str, _auth: CompanyContext = Depends(auth.read_context)):
    db = SessionLocal()
    try:
        clean_tag = tag.strip()
        item = equipment_query(db, _auth).filter(Equipment.tag == clean_tag).first()
        if not item:
            raise HTTPException(status_code=404, detail="Equipamento nÃ£o encontrado.")
        return serialize_equipment(item)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Equipment lookup failed") from None
    finally:
        db.close()


@app.get("/equipment/{id}/qr-payload")
def get_qr_payload(id: int, _auth: CompanyContext = Depends(auth.read_context)):
    db = SessionLocal()
    try:
        item = equipment_query(db, _auth).filter(Equipment.id == id).first()
        if not item:
            raise HTTPException(status_code=404, detail="Equipamento nÃ£o encontrado.")

        return {
            "id": item.id,
            "tag": item.tag,
            "qr_payload": build_qr_payload(item),
        }
    finally:
        db.close()


@app.put("/equipment/{id}")
async def update_equipment(
    id: int,
    request: Request,
    tag: str = Form(...),
    name: str = Form(...),
    photo: UploadFile | None = File(None),
    unit_id: int | None = Form(None, gt=0),
    equipment_type: str = Form(""),
    sector: str = Form(""),
    location: str = Form(""),
    manufacturer: str = Form(""),
    model: str = Form(""),
    serial_number: str = Form(""),
    calibration_date: str = Form(""),
    next_calibration_date: str = Form(""),
    status: str = Form("Ativo"),
    notes: str = Form(""),
    _auth: CompanyContext = Depends(auth.writer),
):
    db = SessionLocal()
    try:
        item = equipment_query(db, _auth).filter(Equipment.id == id).first()
        if not item:
            raise HTTPException(status_code=404, detail="Equipamento nÃ£o encontrado.")

        # Existing clients omit this field. Only an explicit empty field clears it.
        if 'unit_id' in await request.form():
            validate_equipment_unit(db, unit_id, item.company_id)
            item.unit_id = unit_id

        duplicated = equipment_query(db, _auth).filter(
            Equipment.tag == tag.strip(),
            Equipment.id != id
        ).first()
        if duplicated:
            raise HTTPException(status_code=400, detail="TAG jÃ¡ cadastrada em outro equipamento.")

        item.tag = tag.strip()
        item.name = name.strip()
        item.equipment_type = equipment_type.strip()
        item.sector = sector.strip()
        item.location = location.strip()
        item.manufacturer = manufacturer.strip()
        item.model = model.strip()
        item.serial_number = serial_number.strip()
        item.calibration_date = calibration_date.strip()
        item.next_calibration_date = next_calibration_date.strip()
        item.status = status.strip() or "Ativo"
        item.notes = notes.strip()

        if photo and photo.filename:
            result = cloudinary.uploader.upload(
                photo.file,
                folder="tagcheck/equipments" if _auth.company_id == DEFAULT_COMPANY_ID else f"tagcheck/companies/{_auth.company_id}/equipments",
                resource_type="image",
            )
            image_url = result.get("secure_url")
            if image_url:
                item.photo = image_url

        db.commit()
        db.refresh(item)
        return serialize_equipment(item)
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Equipment conflicts with an existing record") from None
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Equipment operation failed") from None
    finally:
        db.close()


@app.delete("/equipment/{id}")
def delete_equipment(
    id: int,
    _auth: CompanyContext = Depends(auth.deleter),
):
    db = SessionLocal()
    try:
        item = equipment_query(db, _auth).filter(Equipment.id == id).first()
        if not item:
            raise HTTPException(status_code=404, detail="Equipamento nÃ£o encontrado.")

        db.delete(item)
        db.commit()
        return {"ok": True}
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Equipment conflicts with an existing record") from None
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Equipment operation failed") from None
    finally:
        db.close()

from fastapi.responses import StreamingResponse

def equipment_pdf_labels(_auth: CompanyContext):
    db = SessionLocal()
    try:
        items = equipment_query(db, _auth).order_by(Equipment.id.asc()).all()

        if not items:
            raise HTTPException(status_code=404, detail="Nenhum equipamento cadastrado.")

        buffer = BytesIO()
        pdf = canvas.Canvas(buffer, pagesize=A4)
        page_width, page_height = A4

        cols = 4
        rows = 8
        margin_x = 8 * mm
        margin_y = 10 * mm
        gap_x = 4 * mm
        gap_y = 6 * mm

        label_width = (page_width - (2 * margin_x) - ((cols - 1) * gap_x)) / cols
        label_height = (page_height - (2 * margin_y) - ((rows - 1) * gap_y)) / rows

        qr_size = min(label_width * 0.75, label_height * 0.70)

        for index, item in enumerate(items):
            page_index = index % (cols * rows)
            col = page_index % cols
            row = page_index // cols

            if index > 0 and page_index == 0:
                pdf.showPage()

            x = margin_x + col * (label_width + gap_x)
            y = page_height - margin_y - ((row + 1) * label_height) - (row * gap_y)

            pdf.roundRect(x, y, label_width, label_height, 4 * mm, stroke=1, fill=0)

            payload = build_qr_payload(item)
            qr_img = qrcode.make(payload)
            qr_buffer = BytesIO()
            qr_img.save(qr_buffer, format="PNG")
            qr_buffer.seek(0)

            qr_x = x + (label_width - qr_size) / 2
            qr_y = y + (label_height - qr_size) / 2 - 2 * mm

            pdf.drawImage(
                ImageReader(qr_buffer),
                qr_x,
                qr_y,
                qr_size,
                qr_size,
                preserveAspectRatio=True,
                mask='auto'
            )

            # TAG no topo do card
            pdf.setFont("Helvetica-Bold", 10)
            pdf.drawCentredString(
                x + (label_width / 2),
                y + label_height - 5 * mm,
                (item.tag or "-")[:28]
            )

        pdf.save()
        buffer.seek(0)

        return StreamingResponse(
            buffer,
            media_type="application/pdf",
            headers={"Content-Disposition": "inline; filename=etiquetas_qr.pdf"},
        )
         
    finally:
        db.close()


@app.post("/equipment/pdf-access")
def create_pdf_access(_auth: CompanyContext = Depends(auth.current)):
    with SessionLocal() as db:
        user = db.get(User, _auth.user_id)
        link = auth.membership(db, user.id, _auth.company_id)
        return {"token": auth.issue(user, link, purpose="pdf", ttl=120, legacy=_auth.legacy), "expires_in": 120}


@app.get("/equipment/pdf", response_class=StreamingResponse)
def public_or_session_pdf(_auth: CompanyContext = Depends(auth.read_context)):
    return equipment_pdf_labels(_auth)


@app.post("/equipment/pdf", response_class=StreamingResponse)
def temporary_pdf(request: Request, pdf_token: str = Form(..., max_length=8192)):
    context = auth.from_token(pdf_token, purpose="pdf")
    auth.check_company_hint(request, context)
    return equipment_pdf_labels(context)
