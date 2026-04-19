from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import cloudinary
import cloudinary.uploader
import os

from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL não configurada")

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


class Equipment(Base):
    __tablename__ = "tagcheck_equipment"

    id = Column(Integer, primary_key=True, index=True)
    tag = Column(String, unique=True, index=True)
    name = Column(String)
    photo = Column(String)


Base.metadata.create_all(bind=engine)

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


@app.post("/equipment")
async def create_equipment(
    tag: str = Form(...),
    name: str = Form(...),
    photo: UploadFile = File(...)
):
    db = SessionLocal()
    try:
        result = cloudinary.uploader.upload(photo.file)
        image_url = result.get("secure_url")

        item = Equipment(tag=tag, name=name, photo=image_url)
        db.add(item)
        db.commit()
        db.refresh(item)
        return item.__dict__
    finally:
        db.close()


@app.get("/equipment")
def list_equipment():
    db = SessionLocal()
    items = db.query(Equipment).all()
    db.close()
    return [i.__dict__ for i in items]


@app.get("/equipment/tag/{tag}")
def get_by_tag(tag: str):
    db = SessionLocal()
    item = db.query(Equipment).filter(Equipment.tag == tag).first()
    db.close()

    if not item:
        raise HTTPException(404, "Equipamento não encontrado")

    return item.__dict__


# 🔥 NOVO: EDITAR
@app.put("/equipment/{id}")
async def update_equipment(
    id: int,
    tag: str = Form(...),
    name: str = Form(...),
    photo: UploadFile = File(None)
):
    db = SessionLocal()
    try:
        item = db.query(Equipment).filter(Equipment.id == id).first()
        if not item:
            raise HTTPException(404, "Não encontrado")

        item.tag = tag
        item.name = name

        if photo:
            result = cloudinary.uploader.upload(photo.file)
            item.photo = result.get("secure_url")

        db.commit()
        return {"ok": True}
    finally:
        db.close()


# 🔥 NOVO: EXCLUIR
@app.delete("/equipment/{id}")
def delete_equipment(id: int):
    db = SessionLocal()
    try:
        item = db.query(Equipment).filter(Equipment.id == id).first()
        if not item:
            raise HTTPException(404, "Não encontrado")

        db.delete(item)
        db.commit()
        return {"ok": True}
    finally:
        db.close()