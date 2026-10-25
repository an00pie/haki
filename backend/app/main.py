from fastapi import FastAPI, APIRouter, Depends, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from app.config import settings
from app.database import Base, engine, get_db
from app.models import entities
from app.api.routes import router, ScanPayload, scan_seller, scan_stage2_video

Base.metadata.create_all(bind=engine)
app=FastAPI(title=settings.app_name,version="0.2.0",description="Local-first, user-triggered seller investigation service")
allowed_origins = list(set(["http://localhost:3000", "http://127.0.0.1:3000"] + settings.origins))
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=r"chrome-extension://[a-p]{32}",
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS", "HEAD"],
    allow_headers=["Content-Type", "Authorization", "Accept"],
)
app.include_router(router)
# Support top-level /scan and /scan/{id}/video directly as per architecture specification
scan_router = APIRouter()
@scan_router.post("/scan", status_code=201)
async def top_level_scan(payload: ScanPayload, db: Session = Depends(get_db)):
    return await scan_seller(payload, db)

@scan_router.post("/scan/{case_id}/video", status_code=201)
async def top_level_scan_video(case_id: str, file: UploadFile = File(...), reference_text: str = Form("", max_length=1000), db: Session = Depends(get_db)):
    return await scan_stage2_video(case_id, file, reference_text, db)

app.include_router(scan_router)

@app.get("/")
def root(): return {"app": settings.app_name, "docs": "/docs", "api": "/api/v1", "scan": "/scan"}

@app.get("/health")
def root_health(): return {"status": "ok", "app": settings.app_name}

