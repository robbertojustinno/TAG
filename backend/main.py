from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Header, Depends, Response, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy import or_
from pydantic import BaseModel, Field
import cloudinary
import cloudinary.uploader
import os
import secrets
import hashlib
import hmac
import time
from io import BytesIO
import base64
from PIL import Image as PILImage

from sqlalchemy.orm import sessionmaker

from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak, Image as ReportImage
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
    from .metrology import metrology_form, apply_metrology, serialize_metrology, LABELS as METROLOGY_LABELS
    from .models import Base, Company, Unit, User, UserCompany, Equipment, AssetCategory, DEFAULT_COMPANY_SLUG
    from .migrate_multiempresa import make_engine, migrate
    from .tenancy import Tenancy, CompanyContext, equipment_query
    from .admin_api import build_router
    from .company_api import build_company_router
    from .category_api import build_category_router
else:
    from metrology import metrology_form, apply_metrology, serialize_metrology, LABELS as METROLOGY_LABELS
    from models import Base, Company, Unit, User, UserCompany, Equipment, AssetCategory, DEFAULT_COMPANY_SLUG
    from migrate_multiempresa import make_engine, migrate
    from tenancy import Tenancy, CompanyContext, equipment_query
    from admin_api import build_router
    from company_api import build_company_router
    from category_api import build_category_router

ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "legacy-admin@tagcheck.invalid").strip().lower()
engine = make_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
try:
    MIGRATION = migrate(engine, ADMIN_USERNAME, ADMIN_PASSWORD, ADMIN_EMAIL)
except Exception as migration_error:
    import logging
    import re

    driver_error = getattr(migration_error, "orig", None)
    sqlstate = (getattr(driver_error, "sqlstate", None)
                or getattr(driver_error, "pgcode", None)
                or getattr(migration_error, "sqlstate", None)
                or getattr(migration_error, "pgcode", None))
    if not isinstance(sqlstate, str) or not re.fullmatch(r"[0-9A-Z]{5}", sqlstate):
        sqlstate = "unavailable"

    # Never log exception text, SQL, parameters, connection URLs or tracebacks.
    # Classify locally and emit only fixed diagnostic phrases.
    diagnostic = {
        "28P01": "authentication failed",
        "28000": "invalid authorization specification",
        "42501": "permission denied",
        "3D000": "database does not exist",
        "3F000": "invalid schema name",
        "42P01": "undefined table",
        "42703": "undefined column",
        "23502": "not-null constraint violation",
        "23503": "foreign key constraint violation",
        "23505": "unique constraint violation",
        "23514": "check constraint violation",
        "53300": "too many connections",
        "57014": "query canceled or statement timeout",
    }.get(sqlstate)
    if diagnostic is None:
        error_text = str(driver_error if driver_error is not None else migration_error).lower()
        diagnostic = "migration failed; details withheld"
        for marker, safe_message in (
            ("password authentication failed", "authentication failed"),
            ("could not translate host name", "could not translate host name"),
            ("name or service not known", "could not translate host name"),
            ("timeout", "timeout"),
            ("timed out", "timeout"),
            ("connection refused", "connection refused"),
            ("permission denied", "permission denied"),
            ("invalid existing company association", "invalid existing company association"),
            ("equipment count changed", "equipment count changed"),
        ):
            if marker in error_text:
                diagnostic = safe_message
                break
        del error_text

    exception_type = re.sub(r"[^a-zA-Z0-9_]", "", type(migration_error).__name__)[:80]
    driver_type = (re.sub(r"[^a-zA-Z0-9_]", "", type(driver_error).__name__)[:80]
                   if driver_error is not None else "unavailable")
    logging.getLogger(__name__).error(
        "Migration failed: exception=%s SQLSTATE=%s driver=%s message=%s",
        exception_type, sqlstate, driver_type, diagnostic,
    )
    engine.dispose()
    raise RuntimeError("Database migration failed; no automatic destructive repair was attempted") from None
DEFAULT_COMPANY_ID = MIGRATION["default_company_id"]
LEGACY_USER_ID = MIGRATION["legacy_user_id"]

auth = Tenancy(SessionLocal, ADMIN_TOKEN, DEFAULT_COMPANY_ID, LEGACY_USER_ID, ADMIN_USERNAME, ADMIN_PASSWORD)
app = FastAPI()
app.include_router(build_router(auth))
app.include_router(build_company_router(auth))
app.include_router(build_category_router(auth))

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


def persist_equipment_photo(upload: UploadFile, company_id: int) -> str:
    """Store equipment photos without making Cloudinary a single point of failure.

    Existing Cloudinary behavior remains preferred. If that provider rejects or is
    unavailable, store a bounded JPEG data URL in the Fase 2 database only.
    """
    raw = upload.file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Foto vazia.")

    try:
        result = cloudinary.uploader.upload(
            BytesIO(raw),
            folder="tagcheck/equipments" if company_id == DEFAULT_COMPANY_ID else f"tagcheck/companies/{company_id}/equipments",
            resource_type="image",
        )
        image_url = result.get("secure_url")
        if image_url:
            return image_url
    except Exception:
        # Provider failures must not block field work. Do not log credentials or
        # provider exception text.
        pass

    try:
        image = PILImage.open(BytesIO(raw))
        if image.mode not in ("RGB", "L"):
            image = image.convert("RGB")
        elif image.mode == "L":
            image = image.convert("RGB")
        image.thumbnail((1280, 1280))
        output = BytesIO()
        image.save(output, format="JPEG", quality=82, optimize=True)
        encoded = base64.b64encode(output.getvalue()).decode("ascii")
        return f"data:image/jpeg;base64,{encoded}"
    except Exception:
        raise HTTPException(status_code=500, detail="Falha ao armazenar a foto do equipamento.") from None


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
    category_path = []
    category = item.category
    while category is not None:
        category_path.append(category.name)
        category = category.parent
    category_path.reverse()
    return {
        "id": item.id,
        "unit_id": item.unit_id,
        "unit_name": item.unit.name if item.unit is not None else None,
        "category_id": item.category_id,
        "category_name": item.category.name if item.category is not None else None,
        "category_path": category_path,
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
        **serialize_metrology(item),
        "qr_payload": build_qr_payload(item),
    }
    


@app.get("/")
def root():
    return {"ok": True, "message": "TagCheck backend online"}


@app.head("/")
def root_head():
    return Response(status_code=200)


@app.get("/health")
def health():
    return {"ok": True}


def validate_equipment_unit(db, unit_id, company_id):
    if unit_id is not None and not db.query(Unit).filter(Unit.id == unit_id, Unit.company_id == company_id).first():
        raise HTTPException(status_code=404, detail="Unit not found in the active company")

def validate_equipment_category(db, category_id, company_id):
    if category_id is not None and not db.query(AssetCategory).filter(
        AssetCategory.id == category_id, AssetCategory.company_id == company_id
    ).first():
        raise HTTPException(status_code=404, detail="Category not found in the active company")


@app.post("/equipment")
async def create_equipment(
    tag: str = Form(...),
    name: str = Form(...),
    photo: UploadFile = File(...),
    unit_id: int | None = Form(None, gt=0),
    category_id: int | None = Form(None, gt=0),
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
    metrology: dict = Depends(metrology_form),
    _auth: CompanyContext = Depends(auth.writer),
):
    tag = tag.strip().upper()
    if not tag:
        raise HTTPException(status_code=400, detail="TAG Ã© obrigatÃ³ria.")
    if not name.strip():
        raise HTTPException(status_code=400, detail="Nome Ã© obrigatÃ³rio.")
    if not photo or not photo.filename:
        raise HTTPException(status_code=400, detail="Foto Ã© obrigatÃ³ria.")

    db = SessionLocal()
    try:
        validate_equipment_unit(db, unit_id, _auth.company_id)
        validate_equipment_category(db, category_id, _auth.company_id)
        existing = equipment_query(db, _auth).filter(Equipment.tag == tag).first()
        if existing:
            raise HTTPException(status_code=400, detail="TAG jÃ¡ cadastrada.")

        apply_metrology(Equipment(), metrology)
        image_url = persist_equipment_photo(photo, _auth.company_id)

        item = Equipment(
            company_id=_auth.company_id,
            unit_id=unit_id,
            category_id=category_id,
            tag=tag,
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
        apply_metrology(item, metrology)
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
def list_equipment(unit_id: int | None = Query(None, gt=0), category_id: int | None = Query(None, gt=0), include_children: bool = Query(False), status: str | None = Query(None), search: str | None = Query(None), _auth: CompanyContext = Depends(auth.read_context)):
    db = SessionLocal()
    try:
        if unit_id is not None:
            if _auth.user_id is None:
                raise HTTPException(status_code=401, detail="Authentication required for unit filters")
            unit = db.query(Unit).filter(Unit.id == unit_id, Unit.company_id == _auth.company_id).first()
            if not unit:
                raise HTTPException(status_code=404, detail="Unit not found in the active company")
        category_ids = None
        if category_id is not None:
            root = db.query(AssetCategory).filter(AssetCategory.id == category_id, AssetCategory.company_id == _auth.company_id).first()
            if not root:
                raise HTTPException(status_code=404, detail="Category not found in the active company")
            category_ids = [root.id]
            if include_children:
                pending = [root.id]
                while pending:
                    child_ids = [row.id for row in db.query(AssetCategory.id).filter(AssetCategory.parent_id.in_(pending), AssetCategory.company_id == _auth.company_id)]
                    category_ids.extend(child_ids)
                    pending = child_ids
        query = equipment_query(db, _auth)
        if unit_id is not None:
            query = query.filter(Equipment.unit_id == unit_id)
        if category_ids is not None:
            query = query.filter(Equipment.category_id.in_(category_ids))
        if status and status.strip():
            query = query.filter(Equipment.status == status.strip())
        if search and search.strip():
            term = f"%{search.strip()}%"
            query = query.filter(or_(Equipment.tag.ilike(term), Equipment.name.ilike(term),
                                     Equipment.manufacturer.ilike(term), Equipment.model.ilike(term)))
        items = query.order_by(Equipment.id.desc()).all()
        return [serialize_equipment(i) for i in items]
    finally:
        db.close()


@app.get("/equipment/tag/{tag}")
def get_by_tag(tag: str, category_id: int | None = Query(None, gt=0), include_children: bool = Query(False), _auth: CompanyContext = Depends(auth.read_context)):
    db = SessionLocal()
    try:
        clean_tag = tag.strip().upper()
        query = equipment_query(db, _auth).filter(Equipment.tag == clean_tag)
        if category_id is not None:
            root = db.query(AssetCategory).filter(AssetCategory.id == category_id, AssetCategory.company_id == _auth.company_id).first()
            if not root:
                raise HTTPException(status_code=404, detail="Category not found in the active company")
            category_ids = [root.id]
            if include_children:
                pending = [root.id]
                while pending:
                    child_ids = [row.id for row in db.query(AssetCategory.id).filter(AssetCategory.parent_id.in_(pending), AssetCategory.company_id == _auth.company_id)]
                    category_ids.extend(child_ids)
                    pending = child_ids
            query = query.filter(Equipment.category_id.in_(category_ids))
        item = query.first()
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
    category_id: int | None = Form(None, gt=0),
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
    metrology: dict = Depends(metrology_form),
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
        if 'category_id' in await request.form():
            validate_equipment_category(db, category_id, item.company_id)
            item.category_id = category_id

        tag = tag.strip().upper()
        duplicated = equipment_query(db, _auth).filter(
            Equipment.tag == tag,
            Equipment.id != id
        ).first()
        if duplicated:
            raise HTTPException(status_code=400, detail="TAG jÃ¡ cadastrada em outro equipamento.")

        apply_metrology(item, metrology)
        item.tag = tag
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
            item.photo = persist_equipment_photo(photo, _auth.company_id)

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


class EquipmentReportPayload(BaseModel):
    equipment_id: int | None = Field(default=None, gt=0)
    category_id: int | None = Field(default=None, gt=0)
    unit_id: int | None = Field(default=None, gt=0)
    status: str | None = Field(default=None, max_length=100)
    search: str | None = Field(default=None, max_length=200)

class _ReportCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        canvas.Canvas.__init__(self, *args, **kwargs)
        self._states = []
    def showPage(self):
        self._states.append(dict(self.__dict__))
        self._startPage()
    def save(self):
        total = len(self._states)
        page_width = self._pagesize[0]
        for state in self._states:
            self.__dict__.update(state)
            self.saveState()
            self.setFont('Helvetica', 7)
            self.setFillColor(colors.grey)
            self.drawCentredString(page_width / 2, 7 * mm, f'Página {self._pageNumber} de {total}')
            self.restoreState()
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)


@app.post("/equipment/report-pdf", response_class=StreamingResponse)
def equipment_report_pdf(payload: EquipmentReportPayload, _auth: CompanyContext = Depends(auth.read_context)):
    db = SessionLocal()
    try:
        category_ids = None
        category_title = None
        if payload.category_id is not None:
            root = db.query(AssetCategory).filter(
                AssetCategory.id == payload.category_id,
                AssetCategory.company_id == _auth.company_id
            ).first()
            if not root:
                raise HTTPException(status_code=404, detail="Category not found in the active company")
            category_ids = [root.id]
            pending = [root.id]
            while pending:
                child_ids = [row.id for row in db.query(AssetCategory.id).filter(
                    AssetCategory.parent_id.in_(pending),
                    AssetCategory.company_id == _auth.company_id
                )]
                category_ids.extend(child_ids)
                pending = child_ids
            path = []
            current = root
            while current is not None:
                path.append(current.name)
                current = current.parent
            category_title = " > ".join(reversed(path))

        query = equipment_query(db, _auth)
        if payload.equipment_id is not None:
            query = query.filter(Equipment.id == payload.equipment_id)
        if category_ids is not None:
            query = query.filter(Equipment.category_id.in_(category_ids))
        if payload.unit_id is not None:
            validate_equipment_unit(db, payload.unit_id, _auth.company_id)
            query = query.filter(Equipment.unit_id == payload.unit_id)
        if payload.status and payload.status.strip():
            query = query.filter(Equipment.status == payload.status.strip())
        if payload.search and payload.search.strip():
            term = f"%{payload.search.strip()}%"
            query = query.filter(or_(
                Equipment.tag.ilike(term),
                Equipment.name.ilike(term),
                Equipment.manufacturer.ilike(term),
                Equipment.model.ilike(term)
            ))

        items = query.order_by(Equipment.tag.asc(), Equipment.id.asc()).all()
        if not items:
            raise HTTPException(status_code=404, detail="Nenhum equipamento encontrado para o relatório")

        company = db.get(Company, _auth.company_id)
        buffer = BytesIO()
        styles = getSampleStyleSheet()
        normal = styles['Normal']
        normal.fontName = 'Helvetica'
        normal.fontSize = 7
        normal.leading = 8

        title_style = styles['Title']
        title_style.fontName = 'Helvetica-Bold'
        title_style.fontSize = 14

        story = []
        if getattr(company, 'logo_data', None):
            story.append(ReportImage(BytesIO(company.logo_data), width=28*mm, height=11*mm, kind='proportional'))
        story.append(Paragraph('TAGCHECK', title_style))
        story.append(Paragraph(company.name, styles['Heading2']))

        report_title = 'LISTA DE ATIVOS'
        if category_title:
            report_title += f' - {category_title}'
        story.extend([
            Spacer(1, 2*mm),
            Paragraph(report_title, styles['Heading2']),
            Paragraph(
                f"Emissão: {time.strftime('%d/%m/%Y %H:%M:%S')}  |  Quantidade: {len(items)}",
                normal
            ),
            Spacer(1, 3*mm)
        ])

        from xml.sax.saxutils import escape

        def cell(value):
            text_value = '-' if value is None or str(value).strip() == '' else str(value)
            return Paragraph(escape(text_value), normal)

        headers = [
            'Seq', 'TAG', 'Descrição', 'Tipo', 'Setor', 'Local',
            'Categoria', 'Unidade', 'Fabricante', 'Status',
            'Data Calib.', 'Próx. Calib.'
        ]

        rows = []
        for seq, item in enumerate(items, start=1):
            serialized = serialize_equipment(item)
            category_path = ' > '.join(serialized['category_path']) or 'Sem categoria'
            rows.append([
                cell(seq),
                cell(item.tag),
                cell(item.name),
                cell(item.equipment_type),
                cell(item.sector),
                cell(item.location),
                cell(category_path),
                cell(item.unit.name if item.unit else '-'),
                cell(item.manufacturer),
                cell(item.status or 'Ativo'),
                cell(item.calibration_date),
                cell(item.next_calibration_date),
            ])

        page_size = landscape(A4)
        # Mantém a tabela inteira dentro da largura útil do A4 horizontal.
        col_widths = [
            7*mm, 20*mm, 36*mm, 20*mm, 22*mm, 26*mm,
            30*mm, 22*mm, 24*mm, 18*mm, 22*mm, 23*mm
        ]

        table_style = TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1f2937')),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('ALIGN', (0,0), (0,-1), 'CENTER'),
            ('ALIGN', (9,1), (9,-1), 'CENTER'),
            ('FONTSIZE', (0,0), (-1,-1), 5.6),
            ('LEADING', (0,0), (-1,-1), 6.3),
            ('GRID', (0,0), (-1,-1), 0.3, colors.HexColor('#9ca3af')),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#f3f4f6')]),
            ('LEFTPADDING', (0,0), (-1,-1), 1.4),
            ('RIGHTPADDING', (0,0), (-1,-1), 1.4),
            ('TOPPADDING', (0,0), (-1,-1), 1.8),
            ('BOTTOMPADDING', (0,0), (-1,-1), 1.8),
        ])

        # Distribuição mais equilibrada: 16 ativos por página.
        # Isso evita uma primeira página muito cheia e uma segunda quase vazia.
        page_rows = 16
        for index in range(0, len(rows), page_rows):
            chunk = rows[index:index + page_rows]
            data = [[cell(h) for h in headers]] + chunk
            table = Table(data, repeatRows=1, colWidths=col_widths, hAlign='LEFT')
            table.setStyle(table_style)
            story.append(table)
            if index + page_rows < len(rows):
                story.append(PageBreak())

        doc = SimpleDocTemplate(
            buffer,
            pagesize=page_size,
            rightMargin=5*mm,
            leftMargin=5*mm,
            topMargin=8*mm,
            bottomMargin=13*mm,
            title='TagCheck - Lista de Ativos'
        )
        doc.build(story, canvasmaker=_ReportCanvas)
        buffer.seek(0)

        filename = 'lista_ativos.pdf' if not category_title else 'lista_ativos_categoria.pdf'
        return StreamingResponse(
            buffer,
            media_type='application/pdf',
            headers={'Content-Disposition': f'attachment; filename={filename}'}
        )
    finally:
        db.close()


@app.get("/equipment/{id}/report-pdf", response_class=StreamingResponse)
def asset_report_pdf(id: int, _auth: CompanyContext = Depends(auth.read_context)):
    return equipment_report_pdf(EquipmentReportPayload(equipment_id=id), _auth)


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
