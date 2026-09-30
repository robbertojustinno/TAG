from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Header, Depends, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import cloudinary
import cloudinary.uploader
import os
from io import BytesIO

from sqlalchemy import create_engine, Column, Integer, String, Text, Numeric, inspect, text, Boolean, ForeignKey
from sqlalchemy.orm import sessionmaker, declarative_base, relationship

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
import qrcode
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from xml.sax.saxutils import escape
if __package__:
    from .metrology import metrology_form, apply_metrology, serialize_metrology, LABELS as METROLOGY_LABELS
    from .migrate_metrology import migrate_metrology
else:
    from metrology import metrology_form, apply_metrology, serialize_metrology, LABELS as METROLOGY_LABELS
    from migrate_metrology import migrate_metrology


DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL nÃ£o configurada")

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://", 1)

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "123456")
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "tagcheck-admin-token")

engine = create_engine(DATABASE_URL, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


class AssetCategory(Base):
    __tablename__ = "tagcheck_asset_categories"
    id = Column(Integer, primary_key=True)
    parent_id = Column(Integer, ForeignKey("tagcheck_asset_categories.id", ondelete="RESTRICT"), nullable=True)
    name = Column(String(200), nullable=False)
    slug = Column(String(200), nullable=False)
    active = Column(Boolean, nullable=False, default=True)
    sort_order = Column(Integer, nullable=False, default=0)
    parent = relationship("AssetCategory", remote_side=[id])


class Equipment(Base):
    __tablename__ = "tagcheck_equipment"

    id = Column(Integer, primary_key=True, index=True)
    tag = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    photo = Column(String, nullable=False)

    category_id = Column(Integer, ForeignKey("tagcheck_asset_categories.id", ondelete="RESTRICT"), nullable=True)
    category = relationship("AssetCategory")
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
    measurand = Column(String(200), nullable=True)
    measurement_unit = Column(String(200), nullable=True)
    range_min = Column(Numeric(24, 10), nullable=True)
    range_max = Column(Numeric(24, 10), nullable=True)
    accuracy_class = Column(String(200), nullable=True)
    resolution = Column(Numeric(24, 10), nullable=True)
    ema = Column(Numeric(24, 10), nullable=True)
    reading_contribution = Column(Numeric(24, 10), nullable=True)



Base.metadata.create_all(bind=engine)


def ensure_extra_columns() -> None:
    inspector = inspect(engine)
    existing_columns = {col["name"] for col in inspector.get_columns("tagcheck_equipment")}

    wanted_columns = {
        "equipment_type": "VARCHAR",
        "sector": "VARCHAR",
        "location": "VARCHAR",
        "manufacturer": "VARCHAR",
        "model": "VARCHAR",
        "serial_number": "VARCHAR",
        "calibration_date": "VARCHAR",
        "next_calibration_date": "VARCHAR",
        "status": "VARCHAR",
        "notes": "TEXT",
    }

    with engine.begin() as connection:
        for column_name, column_type in wanted_columns.items():
            if column_name not in existing_columns:
                connection.execute(
                    text(f'ALTER TABLE tagcheck_equipment ADD COLUMN "{column_name}" {column_type}')
                )


ensure_extra_columns()
with engine.begin() as connection:
    migrate_metrology(connection)

if __package__:
    from .migrate_categories import migrate_categories
    from .categories import build_category_router, category_path, category_ids, validate_category
else:
    from migrate_categories import migrate_categories
    from categories import build_category_router, category_path, category_ids, validate_category
with engine.begin() as connection:
    migrate_categories(connection)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
)


class LoginPayload(BaseModel):
    username: str
    password: str


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
        "category_id": item.category_id,
        "category_name": item.category.name if item.category else "",
        "category_path": category_path(item.category),
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
    


def require_admin(authorization: str = Header(default=None)) -> str:
    expected = f"Bearer {ADMIN_TOKEN}"
    if authorization != expected:
        raise HTTPException(status_code=401, detail="NÃ£o autorizado.")
    return authorization


app.include_router(build_category_router(SessionLocal, AssetCategory, Equipment, require_admin))


@app.get("/")
def root():
    return {"ok": True, "message": "TagCheck backend online"}


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/auth/login")
def login(payload: LoginPayload):
    username = (payload.username or "").strip()
    password = payload.password or ""

    if username != ADMIN_USERNAME or password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="UsuÃ¡rio ou senha invÃ¡lidos.")

    return {
        "ok": True,
        "token": ADMIN_TOKEN,
        "username": ADMIN_USERNAME,
    }


@app.post("/equipment")
async def create_equipment(
    tag: str = Form(...),
    name: str = Form(...),
    photo: UploadFile = File(...),
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
    category_id: int | None = Form(None, gt=0),
    metrology: dict = Depends(metrology_form),
    _auth: str = Depends(require_admin),
):
    if not tag.strip():
        raise HTTPException(status_code=400, detail="TAG Ã© obrigatÃ³ria.")
    if not name.strip():
        raise HTTPException(status_code=400, detail="Nome Ã© obrigatÃ³rio.")
    if not photo or not photo.filename:
        raise HTTPException(status_code=400, detail="Foto Ã© obrigatÃ³ria.")

    db = SessionLocal()
    try:
        existing = db.query(Equipment).filter(Equipment.tag == tag.strip()).first()
        if existing:
            raise HTTPException(status_code=400, detail="TAG jÃ¡ cadastrada.")

        validate_category(db, AssetCategory, category_id)
        apply_metrology(Equipment(), metrology)
        result = cloudinary.uploader.upload(
            photo.file,
            folder="tagcheck/equipments",
            resource_type="image",
        )
        image_url = result.get("secure_url")
        if not image_url:
            raise HTTPException(status_code=500, detail="Falha ao obter URL da imagem.")

        item = Equipment(
            category_id=category_id,
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
        apply_metrology(item, metrology)
        db.add(item)
        db.commit()
        db.refresh(item)

        return serialize_equipment(item)
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Erro ao salvar equipamento: {str(e)}")
    finally:
        db.close()


@app.get("/equipment")
def list_equipment(category_id: int | None = Query(None, gt=0), include_children: bool = True):
    db = SessionLocal()
    try:
        query = db.query(Equipment)
        if category_id is not None:
            query = query.filter(Equipment.category_id.in_(category_ids(db, AssetCategory, category_id, include_children)))
        items = query.order_by(Equipment.id.desc()).all()
        return [serialize_equipment(i) for i in items]
    finally:
        db.close()


@app.get("/equipment/tag/{tag}")
def get_by_tag(tag: str):
    db = SessionLocal()
    try:
        clean_tag = tag.strip()
        item = db.query(Equipment).filter(Equipment.tag == clean_tag).first()
        if not item:
            raise HTTPException(status_code=404, detail="Equipamento nÃ£o encontrado.")
        return serialize_equipment(item)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao buscar TAG: {str(e)}")
    finally:
        db.close()


@app.get("/equipment/{id}/qr-payload")
def get_qr_payload(id: int):
    db = SessionLocal()
    try:
        item = db.query(Equipment).filter(Equipment.id == id).first()
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
    category_id: int | None = Form(None, gt=0),
    metrology: dict = Depends(metrology_form),
    _auth: str = Depends(require_admin),
):
    db = SessionLocal()
    try:
        item = db.query(Equipment).filter(Equipment.id == id).first()
        if not item:
            raise HTTPException(status_code=404, detail="Equipamento nÃ£o encontrado.")

        duplicated = db.query(Equipment).filter(
            Equipment.tag == tag.strip(),
            Equipment.id != id
        ).first()
        if duplicated:
            raise HTTPException(status_code=400, detail="TAG jÃ¡ cadastrada em outro equipamento.")

        if "category_id" in await request.form():
            validate_category(db, AssetCategory, category_id)
            item.category_id = category_id
        apply_metrology(item, metrology)
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
                folder="tagcheck/equipments",
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
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Erro ao atualizar equipamento: {str(e)}")
    finally:
        db.close()


@app.delete("/equipment/{id}")
def delete_equipment(
    id: int,
    _auth: str = Depends(require_admin),
):
    db = SessionLocal()
    try:
        item = db.query(Equipment).filter(Equipment.id == id).first()
        if not item:
            raise HTTPException(status_code=404, detail="Equipamento nÃ£o encontrado.")

        db.delete(item)
        db.commit()
        return {"ok": True}
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Erro ao excluir equipamento: {str(e)}")
    finally:
        db.close()

@app.get("/equipment/pdf")
def equipment_pdf_labels():
    db = SessionLocal()
    try:
        items = db.query(Equipment).order_by(Equipment.id.asc()).all()

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


def build_asset_report(equipment_id=None):
    db = SessionLocal()
    try:
        query = db.query(Equipment)
        if equipment_id is not None:
            query = query.filter(Equipment.id == equipment_id)
        items = query.order_by(Equipment.tag).all()
        if not items:
            raise HTTPException(404, detail="Nenhum ativo encontrado")
        buffer = BytesIO()
        styles = getSampleStyleSheet()
        styles['Normal'].fontSize = 9
        story = [Paragraph('TAGCHECK', styles['Title']),
                 Paragraph('FICHA DO ATIVO' if equipment_id is not None else 'RELATÓRIO DE ATIVOS', styles['Heading2'])]
        labels = {'tag': 'TAG', 'name': 'Nome', 'category_path': 'Categoria', 'equipment_type': 'Tipo', 'sector': 'Setor',
                  'location': 'Localização', 'manufacturer': 'Fabricante', 'model': 'Modelo',
                  'serial_number': 'Número de série', 'calibration_date': 'Data de calibração',
                  'next_calibration_date': 'Próxima calibração', 'status': 'Status', 'notes': 'Observações'}
        def value_text(value):
            if value is None or value == '':
                return 'Não informado'
            if isinstance(value, float):
                return format(value, '.10f').rstrip('0').rstrip('.').replace('.', ',')
            return str(value)
        def data_table(values, names):
            rows = [[Paragraph(escape(label), styles['Normal']), Paragraph(escape(value_text(values.get(key))), styles['Normal'])]
                    for key, label in names.items()]
            table = Table(rows, colWidths=[75*mm, 105*mm])
            table.setStyle(TableStyle([('GRID', (0,0), (-1,-1), .25, colors.lightgrey), ('VALIGN', (0,0), (-1,-1), 'TOP'),
                                       ('LEFTPADDING', (0,0), (-1,-1), 6), ('BOTTOMPADDING', (0,0), (-1,-1), 6)]))
            return table
        for item in items:
            values = serialize_equipment(item)
            story.extend([Spacer(1, 4*mm), Paragraph(escape(f'{item.tag} - {item.name}'), styles['Heading3']), data_table(values, labels)])
            story.append(KeepTogether([Spacer(1, 4*mm), Paragraph('Dados Metrológicos', styles['Heading3']), data_table(values, METROLOGY_LABELS)]))
        SimpleDocTemplate(buffer, pagesize=A4, leftMargin=15*mm, rightMargin=15*mm, topMargin=15*mm, bottomMargin=15*mm).build(story)
        buffer.seek(0)
        return StreamingResponse(buffer, media_type='application/pdf', headers={'Content-Disposition':'attachment; filename=ativos.pdf'})
    finally:
        db.close()

@app.get('/equipment/{id}/report-pdf', response_class=StreamingResponse)
def asset_report_pdf(id: int):
    return build_asset_report(id)

@app.get('/equipment/report-pdf', response_class=StreamingResponse)
def all_assets_report_pdf():
    return build_asset_report()
