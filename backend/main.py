from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import cloudinary
import cloudinary.uploader
import os

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

db = []

@app.get("/")
def root():
    return {"ok": True, "message": "TagCheck backend online"}

@app.get("/health")
def health():
    return {
        "ok": True,
        "cloudinary_configured": bool(
            os.getenv("CLOUDINARY_CLOUD_NAME")
            and os.getenv("CLOUDINARY_API_KEY")
            and os.getenv("CLOUDINARY_API_SECRET")
        )
    }

@app.post("/equipment")
async def create_equipment(
    tag: str = Form(...),
    name: str = Form(...),
    photo: UploadFile = File(...)
):
    if not tag.strip():
        raise HTTPException(status_code=400, detail="TAG é obrigatória.")

    if not name.strip():
        raise HTTPException(status_code=400, detail="Nome é obrigatório.")

    if not photo or not photo.filename:
        raise HTTPException(status_code=400, detail="Foto é obrigatória.")

    try:
        result = cloudinary.uploader.upload(
            photo.file,
            folder="tagcheck/equipments",
            resource_type="image"
        )
        image_url = result.get("secure_url")

        if not image_url:
            raise HTTPException(status_code=500, detail="Falha ao obter URL da imagem.")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro no upload da foto: {str(e)}")

    item = {
        "id": len(db) + 1,
        "tag": tag.strip(),
        "name": name.strip(),
        "photo": image_url
    }

    db.append(item)
    return item

@app.get("/equipment")
def list_equipment():
    return db

@app.get("/equipment/tag/{tag}")
def get_by_tag(tag: str):
    for item in db:
        if item["tag"].strip().lower() == tag.strip().lower():
            return item
    raise HTTPException(status_code=404, detail="Equipamento não encontrado.")