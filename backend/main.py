from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import cloudinary
import cloudinary.uploader
import os
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import sessionmaker, declarative_base

# DB CONFIG
DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

# MODEL
class Equipment(Base):
    __tablename__ = "equipment"

    id = Column(Integer, primary_key=True, index=True)
    tag = Column(String, unique=True)
    name = Column(String)
    photo = Column(String)

Base.metadata.create_all(bind=engine)

# APP
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# CLOUDINARY
cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
)

@app.get("/")
def root():
    return {"ok": True}

@app.post("/equipment")
async def create_equipment(
    tag: str = Form(...),
    name: str = Form(...),
    photo: UploadFile = File(...)
):
    db = SessionLocal()

    try:
        # upload imagem
        result = cloudinary.uploader.upload(
            photo.file,
            folder="tagcheck/equipments"
        )
        image_url = result.get("secure_url")

        # salvar no banco
        item = Equipment(
            tag=tag.strip(),
            name=name.strip(),
            photo=image_url
        )

        db.add(item)
        db.commit()
        db.refresh(item)

        return {
            "id": item.id,
            "tag": item.tag,
            "name": item.name,
            "photo": item.photo
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        db.close()

@app.get("/equipment")
def list_equipment():
    db = SessionLocal()
    items = db.query(Equipment).all()
    db.close()

    return [
        {
            "id": i.id,
            "tag": i.tag,
            "name": i.name,
            "photo": i.photo
        }
        for i in items
    ]

@app.get("/equipment/tag/{tag}")
def get_by_tag(tag: str):
    db = SessionLocal()
    item = db.query(Equipment).filter(Equipment.tag == tag).first()
    db.close()

    if not item:
        raise HTTPException(status_code=404, detail="Equipamento não encontrado")

    return {
        "id": item.id,
        "tag": item.tag,
        "name": item.name,
        "photo": item.photo
    }