from fastapi import FastAPI, UploadFile, File, Form
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
    return {"ok": True}


@app.post("/equipment")
async def create_equipment(
    tag: str = Form(...),
    name: str = Form(...),
    photo: UploadFile | None = File(None)
):
    image_url = None

    if photo and photo.filename:
        result = cloudinary.uploader.upload(photo.file)
        image_url = result.get("secure_url")

    item = {
        "id": len(db) + 1,
        "tag": tag,
        "name": name,
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
        if item["tag"] == tag:
            return item
    return {"error": "not found"}