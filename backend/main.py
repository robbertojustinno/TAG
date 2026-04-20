from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import cloudinary
import cloudinary.uploader
import os

from sqlalchemy import create_engine, Column, Integer, String, Text, inspect, text
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL não configurada")

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "123456")
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "tagcheck-admin-token")

engine = create_engine(DATABASE_URL, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


class Equipment(Base):
    __tablename__ = "tagcheck_equipment"

    id = Column(Integer, primary_key=True, index=True)
    tag = Column(String, unique=True, index=True, nullable=False)
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


def serialize_equipment(item: Equipment) -> dict:
    return {
        "id": item.id,
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
    }


def require_admin(authorization: str = Header(default=None)) -> str:
    expected = f"Bearer {ADMIN_TOKEN}"
    if authorization != expected:
        raise HTTPException(status_code=401, detail="Não autorizado.")
    return authorization


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
        raise HTTPException(status_code=401, detail="Usuário ou senha inválidos.")

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
    _auth: str = Depends(require_admin),
):
    if not tag.strip():
        raise HTTPException(status_code=400, detail="TAG é obrigatória.")
    if not name.strip():
        raise HTTPException(status_code=400, detail="Nome é obrigatório.")
    if not photo or not photo.filename:
        raise HTTPException(status_code=400, detail="Foto é obrigatória.")

    db = SessionLocal()
    try:
        existing = db.query(Equipment).filter(Equipment.tag == tag.strip()).first()
        if existing:
            raise HTTPException(status_code=400, detail="TAG já cadastrada.")

        result = cloudinary.uploader.upload(
            photo.file,
            folder="tagcheck/equipments",
            resource_type="image",
        )
        image_url = result.get("secure_url")
        if not image_url:
            raise HTTPException(status_code=500, detail="Falha ao obter URL da imagem.")

        item = Equipment(
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
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Erro ao salvar equipamento: {str(e)}")
    finally:
        db.close()


@app.get("/equipment")
def list_equipment():
    db = SessionLocal()
    try:
        items = db.query(Equipment).order_by(Equipment.id.desc()).all()
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
            raise HTTPException(status_code=404, detail="Equipamento não encontrado.")
        return serialize_equipment(item)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao buscar TAG: {str(e)}")
    finally:
        db.close()


@app.put("/equipment/{id}")
async def update_equipment(
    id: int,
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
    _auth: str = Depends(require_admin),
):
    db = SessionLocal()
    try:
        item = db.query(Equipment).filter(Equipment.id == id).first()
        if not item:
            raise HTTPException(status_code=404, detail="Equipamento não encontrado.")

        duplicated = db.query(Equipment).filter(
            Equipment.tag == tag.strip(),
            Equipment.id != id
        ).first()
        if duplicated:
            raise HTTPException(status_code=400, detail="TAG já cadastrada em outro equipamento.")

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
            raise HTTPException(status_code=404, detail="Equipamento não encontrado.")

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