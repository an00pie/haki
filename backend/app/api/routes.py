import hashlib, shutil, uuid, asyncio, json
import tempfile
from pathlib import Path
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Body
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.entities import Case, Evidence, Finding, InvestigationRun, ToolAudit, Report, InspectionRequest
from app.schemas.cases import CaseCreate, CasePatch, FindingCreate
from app.schemas.inspect import PageInspect, ImageAnalyze, InstagramInspect, InstagramInvestigationOptions
from app.config import settings
from app.security.file_validation import validate_upload
from app.security.url_guard import validate_public_url, validate_url_for_storage, UnsafeURL
from app.services.risk_engine import assess
from app.services.report_builder import create_report
from app.services.ollama import explain_untrusted_evidence, describe_video_frames
from app.tools.web_fetch import fetch_page
from app.tools.image_analysis import difference_hash, hamming_distance, is_visual_candidate
from app.services.instagram_assessment import engagement_metrics, brave_complaint_search, safe_json_get, compare_profile_site_identity
from app.security.file_validation import detect_type
from app.tools.video_analysis import inspect_video, extract_frames, extract_ocr, VideoError
from app.agents.workflow import investigation_graph
from app.schemas.findings import FindingModel, EvidenceModel
from app.services.scoring import score_investigation, SEVERITY_WEIGHTS
from pydantic import BaseModel, Field

router=APIRouter(prefix="/api/v1")

def recommendation(score:int, threshold:int, sufficient:bool)->dict:
    if not sufficient:
        return {"status":"insufficient_evidence","recommend_video":False,"recommend_media":False,"threshold":threshold,"message":"Insufficient evidence to assess seller authenticity. Consider checking additional sources or adding product photos/videos."}
    recommend=score>=threshold
    return {
        "status":"recommend" if recommend else "optional",
        "recommend_video":recommend,
        "recommend_media":recommend,
        "threshold":threshold,
        "message":("Additional product verification recommended! Because this profile shows unverified authenticity metrics, we strongly suggest uploading product pictures or videos shown on the page/messages to check for copied imagery or digital manipulation before paying." if recommend else "Current checks did not cross the verification recommendation threshold. Product picture or video verification remains available voluntarily.")
    }

@router.get("/workflow/config")
def workflow_config():
    return {"video_verification_threshold":settings.video_verification_threshold,"max_video_upload_mb":settings.max_video_upload_mb,"max_video_duration_seconds":settings.max_video_duration_seconds,"max_video_frames":settings.max_video_frames,"supported_video_types":["video/mp4","video/quicktime"]}

@router.get("/system/settings")
def get_system_settings():
    return {
        "app_name": settings.app_name,
        "version": "0.3.0",
        "database": "sqlite",
        "ollama": {
            "status": "configured",
            "url": settings.ollama_url,
            "model": settings.ollama_model,
            "text_model": settings.ollama_text_model,
        },
        "limits": {
            "max_upload_mb": settings.max_upload_mb,
            "max_video_upload_mb": settings.max_video_upload_mb,
            "max_video_duration_seconds": settings.max_video_duration_seconds,
            "max_video_frames": settings.max_video_frames,
            "max_tool_executions": settings.max_tool_executions,
            "video_verification_threshold": settings.video_verification_threshold,
        },
        "features": {
            "public_checks_enabled": settings.public_checks_enabled,
            "brave_search_configured": bool(settings.brave_search_api_key),
            "meta_graph_api_configured": bool(getattr(settings, "instagram_api_token", "")),
        },
    }

def case_or_404(db,id):
    c=db.get(Case,id)
    if not c: raise HTTPException(404,"Case not found")
    return c

def save_json_evidence(db:Session, case:Case, filename:str, payload:dict, source_url:str|None):
    raw=json.dumps(payload,ensure_ascii=False,sort_keys=True).encode("utf-8")
    eid=str(uuid.uuid4()); path=settings.data_dir/"evidence"/case.id/f"{eid}.json"
    path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
    ev=Evidence(id=eid,case_id=case.id,kind="text",filename=filename,storage_path=str(path.resolve()),sha256=hashlib.sha256(raw).hexdigest(),source_url=source_url,extraction_status="completed")
    db.add(ev);db.flush();return ev

@router.post("/instagram/inspect",status_code=201)
def inspect_instagram(payload:InstagramInspect,db:Session=Depends(get_db)):
    if payload.client_request_id:
        prior=db.get(InspectionRequest,str(payload.client_request_id))
        if prior:
            c=case_or_404(db,prior.case_id)
            ev=db.query(Evidence).filter_by(case_id=c.id,filename="instagram-profile-sample.json").first()
            return {"case_id":c.id,"evidence_id":ev.id if ev else None,"message":"Resumed existing Instagram assessment."}
    try:
        validate_url_for_storage(payload.profile_url)
        from urllib.parse import urlparse
        parsed_profile=urlparse(payload.profile_url)
        if (parsed_profile.hostname or "").lower() not in {"instagram.com","www.instagram.com"}:
            raise UnsafeURL("Profile URL must be on instagram.com")
        path_username=(parsed_profile.path.strip("/").split("/") or [""])[0]
        if path_username.casefold()!=payload.username.casefold():
            raise UnsafeURL("Instagram username must match the profile URL")
        if payload.website_url: validate_url_for_storage(payload.website_url)
        if payload.product_page_url: validate_url_for_storage(payload.product_page_url)
        for item in payload.posts:
            if item.url: validate_url_for_storage(item.url)
            if item.video_url: validate_url_for_storage(item.video_url)
            for url in item.image_urls: validate_url_for_storage(url)
        for url in payload.image_urls: validate_url_for_storage(url)
    except UnsafeURL as exc: raise HTTPException(422,str(exc))
    snapshot=payload.model_dump(mode="json",exclude={"client_request_id"})
    c=Case(title=f"Instagram seller check: @{payload.username}"[:240],mode="pre_purchase",store_url=payload.profile_url,seller_handle=payload.username,product_name=payload.product_name,notes="Instagram public profile assessment; sampled visible page content is unverified.")
    db.add(c);db.flush();ev=save_json_evidence(db,c,"instagram-profile-sample.json",snapshot,payload.profile_url)
    db.add(Finding(case_id=c.id,category="instagram_profile",claim=f"Captured a bounded sample of visible public profile content for @{payload.username}. Values are browser-extracted and unverified; missing fields remain unavailable.",status="observed",confidence=0.5,risk_weight=0,evidence_id=ev.id,source_url=payload.profile_url,evidence_strength="weak"))
    if payload.client_request_id:db.add(InspectionRequest(request_id=str(payload.client_request_id),case_id=c.id))
    db.commit();db.refresh(c)
    return {"case_id":c.id,"evidence_id":ev.id,"message":"Instagram profile sample saved as local unverified evidence."}


@router.post("/inspect",status_code=201)
def inspect_page(payload:PageInspect,db:Session=Depends(get_db)):
    if payload.client_request_id:
        prior=db.get(InspectionRequest,str(payload.client_request_id))
        if prior:
            existing_case=case_or_404(db,prior.case_id)
            first_finding=db.query(Finding).filter_by(case_id=existing_case.id,category="page_metadata").first()
            first_evidence=db.get(Evidence,first_finding.evidence_id) if first_finding and first_finding.evidence_id else None
            return {"case_id":existing_case.id,"case":existing_case,"evidence_id":first_evidence.id if first_evidence else None,"message":"Resumed existing inspection request."}
    try:
        validate_url_for_storage(payload.url)
        for image_url in payload.image_urls: validate_url_for_storage(image_url)
    except UnsafeURL as e: raise HTTPException(422,str(e))
    title=(payload.product_name or payload.title or "Inspected page")[:240]
    c=Case(title=title,mode=payload.mode,store_url=payload.url,product_name=payload.product_name)
    db.add(c); db.flush()
    extracted={"title":payload.title,"product_name":payload.product_name,"price_text":payload.price_text,"seller_text":payload.seller_text,"image_urls":payload.image_urls,"provenance":"browser_extracted_unverified"}
    raw=__import__('json').dumps(extracted,ensure_ascii=False,sort_keys=True).encode("utf-8")
    eid=str(uuid.uuid4()); path=settings.data_dir/"evidence"/c.id/f"{eid}.json";path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
    ev=Evidence(id=eid,case_id=c.id,kind="text",filename="browser-page-metadata.json",storage_path=str(path.resolve()),sha256=hashlib.sha256(raw).hexdigest(),source_url=payload.url,extraction_status="completed")
    db.add(ev);db.flush()
    db.add(Finding(case_id=c.id,category="page_metadata",claim=f"Page metadata extracted by haki from the active tab. Title: {payload.title or '(unavailable)'}. Product, price and seller fields are user-visible page content and remain unverified.",status="observed",confidence=0.5,evidence_id=eid,source_url=payload.url,evidence_strength="weak"))
    if payload.client_request_id: db.add(InspectionRequest(request_id=str(payload.client_request_id),case_id=c.id))
    db.commit();db.refresh(c)
    return {"case_id":c.id,"case":c,"evidence_id":eid,"message":"Page data saved as unverified browser-extracted evidence."}

@router.get("/investigations/{run_id}/findings")
def investigation_findings(run_id:str,db:Session=Depends(get_db)):
    run=db.get(InvestigationRun,run_id)
    if not run: raise HTTPException(404,"Investigation not found")
    return db.query(Finding).filter_by(case_id=run.case_id).order_by(Finding.created_at.asc()).all()

@router.get("/health")
async def health(db: Session=Depends(get_db)):
    try: db.execute(__import__('sqlalchemy').text("SELECT 1")); database="ok"
    except Exception: database="unavailable"
    import httpx
    try:
        async with httpx.AsyncClient(timeout=1,trust_env=False) as client: r=await client.get(settings.ollama_url.rstrip('/')+'/api/tags'); ollama="available" if r.is_success else "unavailable"
    except Exception: ollama="unavailable"
    return {"status":"ok","database":database,"ollama":ollama,"model":settings.ollama_model,"text_model":settings.ollama_text_model,"public_checks_enabled":settings.public_checks_enabled}

@router.post("/cases",status_code=201)
def create_case(payload:CaseCreate,db:Session=Depends(get_db)):
    data=payload.model_dump()
    if data.get("store_url"):
        try: validate_url_for_storage(data["store_url"])
        except UnsafeURL as e: raise HTTPException(422,str(e))
    c=Case(**data); db.add(c); db.commit(); db.refresh(c); return c

@router.get("/cases")
def list_cases(db:Session=Depends(get_db)):
    return db.query(Case).order_by(Case.updated_at.desc()).all()

@router.get("/cases/{case_id}")
def get_case(case_id:str,db:Session=Depends(get_db)):
    c=case_or_404(db,case_id)
    audits=db.query(ToolAudit).filter_by(case_id=c.id).order_by(ToolAudit.created_at.asc()).all()
    stage1=None;stage2=None;stage2_photo=None;discovered_media=None
    for ev in sorted(c.evidence,key=lambda item:item.ingested_at or datetime.min.replace(tzinfo=timezone.utc),reverse=True):
        if ev.filename in {"stage-1-assessment.json","product-video-analysis.json","product-picture-analysis.json","discovered-media-analysis.json"}:
            try:
                payload=json.loads(Path(ev.storage_path).read_text(encoding="utf-8"))
                if ev.filename=="stage-1-assessment.json" and stage1 is None: stage1=payload
                elif ev.filename=="product-video-analysis.json" and stage2 is None: stage2=payload
                elif ev.filename=="product-picture-analysis.json" and stage2_photo is None: stage2_photo=payload
                elif ev.filename=="discovered-media-analysis.json" and discovered_media is None: discovered_media=payload
            except (OSError,ValueError):pass
    current_risk=assess(c.findings,audits)
    return {"case":c,"evidence":c.evidence,"findings":c.findings,"runs":c.runs,"audits":audits,"risk":current_risk,"stage1":stage1,"stage2":stage2,"stage2_photo":stage2_photo,"discovered_media":discovered_media,"final_risk":current_risk}

@router.patch("/cases/{case_id}")
def patch_case(case_id:str,payload:CasePatch,db:Session=Depends(get_db)):
    c=case_or_404(db,case_id); data=payload.model_dump(exclude_unset=True)
    if data.get("store_url"):
        try: validate_url_for_storage(data["store_url"])
        except UnsafeURL as e: raise HTTPException(422,str(e))
    for k,v in data.items(): setattr(c,k,v)
    db.commit(); db.refresh(c); return c

@router.delete("/cases/{case_id}",status_code=204)
def delete_case(case_id:str,db:Session=Depends(get_db)):
    c=case_or_404(db,case_id); root=settings.data_dir.resolve()
    paths=[e.storage_path for e in c.evidence]+[r.storage_path for r in db.query(Report).filter_by(case_id=c.id).all()]
    for raw in paths:
        p=Path(raw).resolve()
        if root not in p.parents: raise HTTPException(500,"Refusing to delete a path outside local data directory")
    db.query(InspectionRequest).filter_by(case_id=c.id).delete(synchronize_session=False)
    for raw in paths:
        try: Path(raw).unlink(missing_ok=True)
        except OSError: pass
    db.delete(c); db.commit(); return None

@router.post("/cases/{case_id}/evidence",status_code=201)
async def upload_evidence(case_id:str,file:UploadFile=File(...),kind:str=Form("document"),source_url:str|None=Form(None),db:Session=Depends(get_db)):
    c=case_or_404(db,case_id)
    if kind not in {"url", "image", "video", "receipt", "document", "text"}: raise HTTPException(422,"Unsupported evidence kind")
    data=await file.read(settings.max_upload_mb*1024*1024+1)
    try: actual=validate_upload(data,file.content_type or "",settings.max_upload_mb*1024*1024)
    except ValueError as e: raise HTTPException(422,str(e))
    if source_url:
        try: validate_url_for_storage(source_url)
        except UnsafeURL as e: raise HTTPException(422,str(e))
    sha=hashlib.sha256(data).hexdigest(); eid=str(uuid.uuid4()); ext={"image/jpeg":"jpg","image/png":"png","image/webp":"webp","video/mp4":"mp4","video/quicktime":"mov","application/pdf":"pdf","text/plain":"txt"}[actual]
    folder=(settings.data_dir/"evidence"/c.id); folder.mkdir(parents=True,exist_ok=True); path=folder/f"{eid}.{ext}"; path.write_bytes(data)
    e=Evidence(id=eid,case_id=c.id,kind=kind,filename=Path(file.filename or "upload").name[:255],storage_path=str(path.resolve()),sha256=sha,source_url=source_url)
    db.add(e); c.status="collecting_evidence"; db.commit(); db.refresh(e); return e

@router.post("/cases/{case_id}/video/verify",status_code=201)
async def verify_product_video(case_id:str,file:UploadFile=File(...),reference_text:str=Form("",max_length=1000),db:Session=Depends(get_db)):
    c=case_or_404(db,case_id); limit=settings.max_video_upload_mb*1024*1024
    data=await file.read(limit+1)
    try:
        actual=detect_type(data)
        if actual not in {"video/mp4","video/quicktime"}: raise ValueError("Upload must contain a supported MP4 or MOV video")
        validate_upload(data,actual,limit)
    except ValueError as exc: raise HTTPException(422,str(exc))
    temp_path=None
    try:
        with tempfile.NamedTemporaryFile(prefix="haki-upload-",suffix=".mov" if actual=="video/quicktime" else ".mp4",delete=False) as handle:
            temp_path=Path(handle.name);handle.write(data)
        metadata=await asyncio.to_thread(inspect_video,temp_path)
        frames=await asyncio.to_thread(extract_frames,temp_path,metadata["duration_seconds"])
    except VideoError as exc:
        raise HTTPException(422,str(exc))
    finally:
        if temp_path:
            try:temp_path.unlink(missing_ok=True)
            except OSError:pass
    folder=settings.data_dir/"evidence"/c.id;folder.mkdir(parents=True,exist_ok=True)
    eid=str(uuid.uuid4());extension="mov" if actual=="video/quicktime" else "mp4";path=folder/f"{eid}.{extension}";path.write_bytes(data)
    video=Evidence(id=eid,case_id=c.id,kind="video",filename=Path(file.filename or f"product-video.{extension}").name[:255],storage_path=str(path.resolve()),sha256=hashlib.sha256(data).hexdigest(),extraction_status="completed")
    db.add(video);db.flush()
    frame_records=[]
    for index,frame in enumerate(frames,1):
        frame_id=str(uuid.uuid4());frame_path=folder/f"{frame_id}.jpg";frame_path.write_bytes(frame["jpeg"])
        frame_ev=Evidence(id=frame_id,case_id=c.id,kind="image",filename=f"video-frame-{index:02d}-at-{frame['timestamp_seconds']:.3f}s.jpg",storage_path=str(frame_path.resolve()),sha256=hashlib.sha256(frame["jpeg"]).hexdigest(),captured_at=datetime.now(timezone.utc),source_url=None,extraction_status="completed")
        db.add(frame_ev);db.flush()
        frame_records.append({"evidence_id":frame_id,"timestamp_seconds":frame["timestamp_seconds"],"sha256":frame_ev.sha256,"difference_hash":frame["difference_hash"]})
    ocr=await asyncio.to_thread(extract_ocr,frames)
    references=[];reference_ids=[]
    for candidate in c.evidence:
        if candidate.kind!="image" or candidate.filename.startswith("video-frame-") or candidate.id==video.id:continue
        candidate_path=Path(candidate.storage_path)
        try:
            if candidate_path.stat().st_size>5*1024*1024:continue
            content=candidate_path.read_bytes()
            if detect_type(content) not in {"image/jpeg","image/png","image/webp"}:continue
            from io import BytesIO
            from PIL import Image
            with Image.open(BytesIO(content)) as image:
                image=image.convert("RGB");image.thumbnail((640,640));buffer=BytesIO();image.save(buffer,format="JPEG",quality=78,optimize=True);references.append(buffer.getvalue())
            reference_ids.append(candidate.id)
        except OSError:continue
        if len(references)>=2:break
    ocr_text=" ".join(sample.get("text","") for sample in ocr.get("samples",[]) if sample.get("text"))
    vision=await describe_video_frames(frames[:4],reference_text,ocr_text,references)
    result={"stage":"product_video_assessment","video_evidence_id":video.id,"video_sha256":video.sha256,"metadata":metadata,"sampled_frame_count":len(frames),"frames":frame_records,"reference_image_evidence_ids":reference_ids,"ocr":ocr,"transcription":{"status":"unavailable","reason":"No local speech-to-text model is configured."},"visual_analysis":{"status":"completed" if vision else "unavailable","model":settings.ollama_model if vision else None,"observations":vision.get("observations",[]) if vision else [],"uncertainties":vision.get("uncertainties",[]) if vision else [],"possible_manipulation_indicators":vision.get("manipulation_indicators",[]) if vision else []},"reference_text_provided":bool(reference_text.strip()),"risk_score_change":0,"limitations":["Video evidence does not prove seller ownership, shipment, or delivery of the same item.","No comparable saved seller/listing photo was available." if not references else "Reference media were sampled from the case evidence and remain unverified.","Absence of detected manipulation indicators does not establish authenticity."]}
    ev=save_json_evidence(db,c,"product-video-analysis.json",result,None)
    for observation in result["visual_analysis"]["observations"]:
        db.add(Finding(case_id=c.id,category="video_product_observation",claim=f"Local Gemma visual observation (unverified): {observation}",status="unverified",confidence=0.0,risk_weight=0,evidence_id=ev.id,evidence_strength="weak"))
    for observation in result["visual_analysis"]["possible_manipulation_indicators"]:
        db.add(Finding(case_id=c.id,category="possible_media_manipulation_indicator",claim=f"Possible manipulation indicator reported by local model; requires manual review: {observation}",status="unverified",confidence=0.0,risk_weight=0,evidence_id=ev.id,evidence_strength="weak"))
    db.add(ToolAudit(case_id=c.id,run_id="user-triggered-video-check",tool_name="local_video_frame_analysis",input_summary=f"Bounded user-uploaded video ({metadata['duration_seconds']} s; {len(frames)} unique sampled frames)",status="completed",result_summary=f"Video metadata and {len(frames)} sampled frames recorded. Ollama visual analysis: {'completed' if vision else 'unavailable'}; OCR {ocr.get('status')}; transcription unavailable. Video analysis adds no automatic risk points."))
    db.commit()
    return {"case_id":c.id,"video_evidence_id":video.id,"analysis_evidence_id":ev.id,"stage2":result,"final_risk":assess(c.findings,db.query(ToolAudit).filter_by(case_id=c.id).all()),"message":"Product video assessment stored. Model observations are unverified and do not affect the deterministic seller risk score."}

@router.post("/cases/{case_id}/product-image/verify",status_code=201)
async def verify_product_image(case_id:str,file:UploadFile=File(...),reference_text:str=Form("",max_length=1000),db:Session=Depends(get_db)):
    c=case_or_404(db,case_id); limit=settings.max_upload_mb*1024*1024
    data=await file.read(limit+1)
    try:
        actual=detect_type(data)
        if actual not in {"image/jpeg","image/png","image/webp"}:
            raise ValueError("Upload must contain a supported JPEG, PNG, or WebP image")
        validate_upload(data,actual,limit)
    except ValueError as exc: raise HTTPException(422,str(exc))

    folder=settings.data_dir/"evidence"/c.id; folder.mkdir(parents=True,exist_ok=True)
    ext="jpg" if actual=="image/jpeg" else "png" if actual=="image/png" else "webp"
    eid=str(uuid.uuid4()); path=folder/f"{eid}.{ext}"; path.write_bytes(data)
    img_hash=difference_hash(path); sha=hashlib.sha256(data).hexdigest()
    image_ev=Evidence(id=eid,case_id=c.id,kind="image",filename=Path(file.filename or f"product-photo.{ext}").name[:255],storage_path=str(path.resolve()),sha256=sha,extraction_status="completed")
    db.add(image_ev); db.flush()

    similar_matches=[]
    for candidate in c.evidence:
        if candidate.id==eid or candidate.kind!="image": continue
        try:
            cand_path=Path(candidate.storage_path)
            cand_hash=difference_hash(cand_path)
            dist=hamming_distance(img_hash,cand_hash)
            if dist<=14:
                similar_matches.append({
                    "evidence_id":candidate.id,
                    "filename":candidate.filename,
                    "hamming_distance":dist,
                    "similarity":"exact_or_near_clone" if dist<=5 else "high_similarity"
                })
        except Exception: continue

    vision=await describe_video_frames([{"jpeg":data,"timestamp_seconds":0}],reference_text,"",[])
    result={
        "stage":"product_picture_assessment",
        "image_evidence_id":eid,
        "sha256":sha,
        "difference_hash":f"{img_hash:016x}",
        "similar_case_images":similar_matches,
        "visual_analysis":{
            "status":"completed" if vision else "unavailable",
            "model":settings.ollama_model if vision else None,
            "observations":vision.get("observations",[]) if vision else [],
            "uncertainties":vision.get("uncertainties",[]) if vision else [],
            "possible_manipulation_indicators":vision.get("manipulation_indicators",[]) if vision else []
        },
        "reference_text":reference_text
    }
    ev=save_json_evidence(db,c,"product-picture-analysis.json",result,None)
    if similar_matches:
        db.add(Finding(case_id=c.id,category="copied_imagery",claim=f"Uploaded product photo closely matches case image '{similar_matches[0]['filename']}' (Hamming distance {similar_matches[0]['hamming_distance']}). Potential stock or reused imagery.",status="observed",confidence=0.7,risk_weight=15,evidence_id=ev.id,evidence_strength="moderate"))
    for obs in result["visual_analysis"]["observations"]:
        db.add(Finding(case_id=c.id,category="product_photo_observation",claim=f"Local Gemma photo observation (unverified): {obs}",status="unverified",confidence=0.0,risk_weight=0,evidence_id=ev.id,evidence_strength="weak"))
    for ind in result["visual_analysis"]["possible_manipulation_indicators"]:
        db.add(Finding(case_id=c.id,category="possible_media_manipulation_indicator",claim=f"Photo manipulation indicator: {ind}",status="unverified",confidence=0.0,risk_weight=0,evidence_id=ev.id,evidence_strength="weak"))
    db.add(ToolAudit(case_id=c.id,run_id="user-product-image-check",tool_name="product_image_analysis",input_summary="User-uploaded product photo compared against listing and profile imagery",status="completed",result_summary=f"Analyzed photo against {len(similar_matches)} similar case image(s)."))
    db.commit()
    return {"case_id":c.id,"image_evidence_id":eid,"stage2_photo":result,"final_risk":assess(c.findings,db.query(ToolAudit).filter_by(case_id=c.id).all()),"message":"Product picture assessment stored."}

@router.delete("/cases/{case_id}/evidence/{evidence_id}",status_code=204)
def delete_evidence(case_id:str,evidence_id:str,db:Session=Depends(get_db)):
    c=case_or_404(db,case_id);ev=db.query(Evidence).filter_by(id=evidence_id,case_id=c.id).first()
    if not ev:raise HTTPException(404,"Evidence not found")
    root=settings.data_dir.resolve();path=Path(ev.storage_path).resolve()
    if root not in path.parents:raise HTTPException(500,"Refusing to delete a path outside local data directory")
    db.query(Finding).filter_by(case_id=c.id,evidence_id=ev.id).delete(synchronize_session=False)
    path.unlink(missing_ok=True);db.delete(ev);db.commit();return None

@router.delete("/cases/{case_id}/video")
def delete_video_artifacts(case_id:str,db:Session=Depends(get_db)):
    c=case_or_404(db,case_id); selected=[e for e in c.evidence if e.filename=="product-video-analysis.json"]
    ids=set()
    for analysis in selected:
        ids.add(analysis.id)
        try: ids.update(frame.get("evidence_id") for frame in json.loads(Path(analysis.storage_path).read_text()).get("frames",[]) if frame.get("evidence_id"))
        except (OSError,ValueError,TypeError):pass
    ids.update(e.id for e in c.evidence if e.kind=="video")
    root=settings.data_dir.resolve()
    for evidence_id in list(ids):
        ev=db.query(Evidence).filter_by(id=evidence_id,case_id=c.id).first()
        if not ev:continue
        path=Path(ev.storage_path).resolve()
        if root not in path.parents:raise HTTPException(500,"Refusing to delete a path outside local data directory")
        db.query(Finding).filter_by(case_id=c.id,evidence_id=ev.id).delete(synchronize_session=False)
        path.unlink(missing_ok=True);db.delete(ev)
    db.commit();return {"deleted_evidence_count":len(ids)}


@router.post("/images/analyze")
async def analyze_images(payload:ImageAnalyze,db:Session=Depends(get_db)):
    c=case_or_404(db,payload.case_id); results=[]
    async with __import__('httpx').AsyncClient(timeout=6.0,follow_redirects=False,trust_env=False,headers={"User-Agent":"haki/0.2 (user-triggered local check)"}) as client:
        for original_url in payload.image_urls[:3]:
            existing_image=db.query(Evidence).filter_by(case_id=c.id,kind="image",source_url=original_url).first()
            if existing_image:
                results.append({"status":"already_saved","evidence_id":existing_image.id,"sha256":existing_image.sha256});continue
            current=original_url; audit_status="unavailable"; summary="Image could not be retrieved safely."
            try:
                for redirect_count in range(4):
                    validate_public_url(current)
                    response=await client.send(client.build_request("GET",current),stream=True)
                    if response.is_redirect:
                        location=response.headers.get("location")
                        if not location: raise ValueError("Redirect lacked a location")
                        from app.security.url_guard import validate_redirect
                        current=validate_redirect(current,location); await response.aclose(); continue
                    if response.status_code >= 400: raise ValueError(f"Image request returned HTTP {response.status_code}")
                    if int(response.headers.get("content-length", "0") or 0) > 5*1024*1024: raise ValueError("Image exceeds 5 MB limit")
                    data=bytearray()
                    async for chunk in response.aiter_bytes():
                        data.extend(chunk)
                        if len(data)>5*1024*1024: raise ValueError("Image exceeds 5 MB limit")
                    await response.aclose()
                    mime=detect_type(bytes(data))
                    if mime not in {"image/jpeg","image/png","image/webp"}: raise ValueError("Unsupported or non-image content")
                    validate_upload(bytes(data),mime,5*1024*1024)
                    eid=str(uuid.uuid4()); ext={"image/jpeg":"jpg","image/png":"png","image/webp":"webp"}[mime]
                    folder=settings.data_dir/"evidence"/c.id;folder.mkdir(parents=True,exist_ok=True);path=folder/f"{eid}.{ext}";path.write_bytes(data)
                    ev=Evidence(id=eid,case_id=c.id,kind="image",filename="page-product-image."+ext,storage_path=str(path.resolve()),sha256=hashlib.sha256(data).hexdigest(),source_url=original_url,extraction_status="completed")
                    db.add(ev);db.flush(); own_hash=difference_hash(path)
                    prior=db.query(Evidence).filter_by(case_id=c.id,kind="image").filter(Evidence.id != eid).all()
                    matches=[]
                    for previous in prior:
                        try:
                            distance=hamming_distance(own_hash,difference_hash(previous.storage_path))
                            if is_visual_candidate(distance): matches.append((previous,distance))
                        except Exception: continue
                    claim=f"User-requested page image saved. SHA-256 {ev.sha256}; difference hash {own_hash:016x}. Similarity is only a within-case visual clue, not proof of copying or fraud."
                    if matches:
                        previous,distance=matches[0]
                        claim+=f" Similar image found: closest saved image {previous.id[:8]} at {previous.source_url or 'user-provided file'} (captured {previous.ingested_at.isoformat() if previous.ingested_at else 'timestamp unavailable'}) has a {distance}/64 difference-hash distance."
                    db.add(Finding(case_id=c.id,category="image_fingerprint",claim=claim,status="observed",confidence=0.5,evidence_id=eid,source_url=current,evidence_strength="weak"))
                    audit_status="completed";summary=f"Validated image; SHA-256 {ev.sha256}; pHash-like dHash {own_hash:016x}; {len(matches)} near matches within case."
                    result={"status":"completed","evidence_id":eid,"sha256":ev.sha256,"difference_hash":f"{own_hash:016x}","near_matches":[{"evidence_id":m.id,"distance":d,"source_url":m.source_url,"captured_at":m.ingested_at.isoformat() if m.ingested_at else None} for m,d in matches]}
                    results.append(result);break
                else: raise ValueError("Redirect limit exceeded")
            except Exception as e:
                summary=str(e)[:300];results.append({"status":"unavailable","url":original_url,"reason":summary})
            db.add(ToolAudit(case_id=c.id,run_id="user-triggered-image-check",tool_name="image_hash",input_summary="User-selected candidate image URL",source_url=current,status=audit_status,result_summary=summary))
    db.commit()
    return {"case_id":c.id,"results":results,"message":"Image similarity is a contextual clue only; it does not establish copied imagery or fraud."}

@router.get("/cases/{case_id}/evidence")
def list_evidence(case_id:str,db:Session=Depends(get_db)):
    case_or_404(db,case_id); return db.query(Evidence).filter_by(case_id=case_id).order_by(Evidence.ingested_at.desc()).all()

@router.get("/cases/{case_id}/evidence/{evidence_id}/content")
@router.get("/cases/{case_id}/evidence/{evidence_id}/download")
def get_evidence_content(case_id: str, evidence_id: str, db: Session = Depends(get_db)):
    c = case_or_404(db, case_id)
    ev = db.query(Evidence).filter_by(id=evidence_id, case_id=c.id).first()
    if not ev:
        raise HTTPException(404, "Evidence artifact not found")
    root = settings.data_dir.resolve()
    path = Path(ev.storage_path).resolve()
    if root not in path.parents and path != root:
        raise HTTPException(403, "Access to evidence outside data directory is prohibited")
    if not path.is_file():
        raise HTTPException(404, "Evidence file is missing on storage")

    suffix = path.suffix.lower()
    media_types = {
        ".json": "application/json",
        ".txt": "text/plain",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".mp4": "video/mp4",
        ".mov": "video/quicktime",
        ".pdf": "application/pdf",
        ".html": "text/html",
    }
    media_type = media_types.get(suffix, "application/octet-stream")
    return FileResponse(path, media_type=media_type, filename=ev.filename)

@router.get("/cases/{case_id}/findings")
def list_findings(case_id:str,db:Session=Depends(get_db)):
    case_or_404(db,case_id); return db.query(Finding).filter_by(case_id=case_id).order_by(Finding.created_at.desc()).all()

@router.post("/cases/{case_id}/findings",status_code=201)
def add_finding(case_id:str,payload:FindingCreate,db:Session=Depends(get_db)):
    c=case_or_404(db,case_id); d=payload.model_dump()
    if d.get("evidence_id") and not db.query(Evidence).filter_by(id=d["evidence_id"],case_id=c.id).first(): raise HTTPException(422,"Evidence must belong to this case")
    if d.get("source_url"):
        try: validate_public_url(d["source_url"])
        except UnsafeURL as e: raise HTTPException(422,str(e))
    f=Finding(case_id=c.id,**d); db.add(f); c.status="collecting_evidence"; db.commit(); db.refresh(f); return f

@router.post("/cases/{case_id}/risk-assessment")
def risk_assessment(case_id:str,db:Session=Depends(get_db)):
    c=case_or_404(db,case_id); return assess(c.findings,db.query(ToolAudit).filter_by(case_id=c.id).all())

@router.post("/cases/{case_id}/investigations",status_code=202)
async def investigate(case_id:str,options:InstagramInvestigationOptions|None=Body(default=None),db:Session=Depends(get_db)):
    c=case_or_404(db,case_id)
    if c.status=="completed":
        prior=db.query(InvestigationRun).filter_by(case_id=c.id).order_by(InvestigationRun.started_at.desc()).first()
        if prior: return {"id":prior.id,"case_id":c.id,"status":prior.status,"steps_used":prior.steps_used,"message":"Existing completed investigation restored."}
    run=InvestigationRun(case_id=c.id,status="running"); db.add(run); c.status="investigating"; db.commit(); db.refresh(run)
    steps=0; options=options or InstagramInvestigationOptions()
    profile_ev=db.query(Evidence).filter_by(case_id=c.id,filename="instagram-profile-sample.json").first()
    profile=None
    if profile_ev:
        try: profile=json.loads(Path(profile_ev.storage_path).read_text(encoding="utf-8"))
        except (OSError,ValueError): profile=None
    if profile:
        from app.services.instagram_assessment import profile_authenticity_metrics
        auth_metrics=profile_authenticity_metrics(profile)
        ev_auth=save_json_evidence(db,c,"instagram-authenticity-metrics.json",auth_metrics,profile.get("profile_url"))
        db.add(ToolAudit(case_id=c.id,run_id=run.id,tool_name="profile_authenticity_analysis",input_summary="Followers, account maturity, and bio link metrics",source_url=profile.get("profile_url"),status="completed",result_summary=json.dumps(auth_metrics,ensure_ascii=False)[:2000]))
        if auth_metrics["account_maturity"]["observations"]:
            db.add(Finding(case_id=c.id,category="account_maturity_anomaly",claim=" ".join(auth_metrics["account_maturity"]["observations"]),status="observed",confidence=0.45,risk_weight=auth_metrics["account_maturity"]["risk_weight"],evidence_id=ev_auth.id,source_url=profile.get("profile_url"),evidence_strength="weak"))
        if auth_metrics["follower_credibility"]["observations"]:
            db.add(Finding(case_id=c.id,category="follower_credibility_anomaly",claim=" ".join(auth_metrics["follower_credibility"]["observations"]),status="observed",confidence=0.45,risk_weight=auth_metrics["follower_credibility"]["risk_weight"],evidence_id=ev_auth.id,source_url=profile.get("profile_url"),evidence_strength="weak"))
        if auth_metrics["website_link"]["observations"]:
            db.add(Finding(case_id=c.id,category="bio_website_anomaly",claim=" ".join(auth_metrics["website_link"]["observations"]),status="observed",confidence=0.45,risk_weight=auth_metrics["website_link"]["risk_weight"],evidence_id=ev_auth.id,source_url=profile.get("profile_url"),evidence_strength="weak"))

        metrics=engagement_metrics(profile)
        db.add(ToolAudit(case_id=c.id,run_id=run.id,tool_name="engagement_sample_analysis",input_summary="Bounded visible sample from Instagram tab",source_url=profile.get("profile_url"),status="completed",result_summary=json.dumps(metrics,ensure_ascii=False)[:2000]))
        if metrics["observations"]:
            ev=save_json_evidence(db,c,"instagram-engagement-metrics.json",metrics,profile.get("profile_url"))
            db.add(Finding(case_id=c.id,category="engagement_anomaly",claim=" ".join(metrics["observations"])+" Repetition includes exact or near-duplicate text. The sample is limited and may not represent the account.",status="observed",confidence=0.35,risk_weight=metrics["risk_weight"],evidence_id=ev.id,source_url=profile.get("profile_url"),evidence_strength="weak"))
        site=profile.get("website_url")
        site_result=None
        if site and options.check_linked_site and settings.public_checks_enabled and steps<settings.max_tool_executions:
            steps+=1
            try: site_result=await asyncio.wait_for(fetch_page(site),timeout=12)
            except Exception as exc: site_result={"status":"unavailable","error":str(exc)[:240],"url":site}
            status=site_result["status"]
            summary=(f"HTTP {site_result.get('http_status')}; HTTPS final={site_result.get('https_final')}; redirects={len(site_result.get('redirect_chain',[]))}; title: {site_result.get('title') or '(none)'}; excerpt: {site_result.get('text_excerpt','')[:500]}" if status=="completed" else site_result.get("error","Unavailable"))
            db.add(ToolAudit(case_id=c.id,run_id=run.id,tool_name="linked_website_fetch",input_summary="User-approved public website linked from Instagram bio",source_url=site_result.get("url",site),status=status,result_summary=summary))
            if status=="completed":
                text=site_result.get("text_excerpt","")
                lowered=text.casefold()
                page_markers={"contact_terms":any(x in lowered for x in ("contact","email","phone","address")),"shipping_terms":any(x in lowered for x in ("shipping","delivery","dispatch")),"refund_return_terms":any(x in lowered for x in ("refund","return","exchange")),"privacy_terms":"privacy" in lowered}
                ev=save_json_evidence(db,c,"linked-website-observation.json",{"retrieved_at":datetime.now(timezone.utc).isoformat(),"requested_url":site_result.get("requested_url"),"url":site_result.get("url"),"https_final":site_result.get("https_final"),"redirect_chain":site_result.get("redirect_chain",[]),"http_status":site_result.get("http_status"),"title":site_result.get("title"),"text_excerpt":text,"visible_policy_contact_terms":page_markers,"image_urls":site_result.get("image_urls",[])},site_result.get("url"))
                db.add(Finding(case_id=c.id,category="website_policy_context",claim="Linked-site excerpt keyword scan (not policy validation): "+", ".join(f"{name}={'found' if found else 'not found in sampled text'}" for name,found in page_markers.items())+f"; final HTTPS={site_result.get('https_final')}; redirects={len(site_result.get('redirect_chain',[]))}.",status="observed",confidence=0.25,risk_weight=0,evidence_id=ev.id,source_url=site_result.get("url"),evidence_strength="weak"))
                db.add(Finding(case_id=c.id,category="storefront_observation",claim=f"Retrieved linked public page titled '{site_result.get('title') or '(no title)'}'. Page content is untrusted; identity consistency is not established by page retrieval alone.",status="observed",confidence=0.5,evidence_id=ev.id,source_url=site_result.get("url"),evidence_strength="weak"))
                identity=compare_profile_site_identity(profile,site_result.get("title"),site_result.get("text_excerpt"))
                if identity["status"]=="possible_difference":
                    db.add(Finding(case_id=c.id,category="profile_business_inconsistency",claim=identity["note"],status="inconclusive",confidence=0.2,risk_weight=0,evidence_id=ev.id,source_url=site_result.get("url"),evidence_strength="weak"))
            else:
                db.add(Finding(case_id=c.id,category="linked_website_unavailable",claim=f"Linked public website could not be checked: {summary}. This is an unknown result, not a negative trust signal.",status="inconclusive",confidence=0,risk_weight=0,source_url=site_result.get("url",site),evidence_strength="weak"))
            from urllib.parse import urlparse, quote
            domain=(urlparse(site_result.get("url") or site).hostname or "").lower()
            checks=[("rdap_domain_registration",f"https://rdap.org/domain/{quote(domain,safe='.-')}"),("wayback_archive_history",f"https://web.archive.org/cdx/search/cdx?url={quote(domain,safe='.-')}&output=json&fl=timestamp,original,statuscode&filter=statuscode:200&limit=10")]
            for name,url in checks:
                if steps>=settings.max_tool_executions: break
                steps+=1; result=await safe_json_get(url); status=result["status"]
                summary=json.dumps(result.get("data",result.get("reason")),ensure_ascii=False)[:1000]
                db.add(ToolAudit(case_id=c.id,run_id=run.id,tool_name=name,input_summary="Bounded public domain-history lookup",source_url=result.get("url",url),status=status,result_summary=summary))
                if status=="completed":
                    ev=save_json_evidence(db,c,f"{name}.json",{"retrieved_at":datetime.now(timezone.utc).isoformat(),**result},result.get("url",url))
                    db.add(Finding(case_id=c.id,category=name,claim=f"Public {name.replace('_',' ')} response saved as context. Registration age or archive presence alone is not proof of seller trustworthiness.",status="observed",confidence=0.4,risk_weight=0,evidence_id=ev.id,source_url=result.get("url",url),evidence_strength="weak"))
        elif site and options.check_linked_site:
            db.add(ToolAudit(case_id=c.id,run_id=run.id,tool_name="linked_website_fetch",input_summary="User-approved public website linked from Instagram bio",source_url=site,status="unavailable",result_summary="Public checks are disabled in local configuration."))
            db.add(Finding(case_id=c.id,category="linked_website_unavailable",claim="Linked public website check was not run because PUBLIC_CHECKS_ENABLED is false. This is unknown, not a negative signal.",status="inconclusive",confidence=0,risk_weight=0,source_url=site,evidence_strength="weak"))
        elif site:
            db.add(ToolAudit(case_id=c.id,run_id=run.id,tool_name="linked_website_fetch",input_summary="Linked website check selection",source_url=site,status="not_requested",result_summary="User did not select the linked website/domain check."))
        elif options.check_linked_site:
            db.add(ToolAudit(case_id=c.id,run_id=run.id,tool_name="linked_website_fetch",input_summary="Bio website link",source_url=profile.get("profile_url"),status="unavailable",result_summary="No public website link was available in the sampled profile."))
        else:
            db.add(ToolAudit(case_id=c.id,run_id=run.id,tool_name="linked_website_fetch",input_summary="Linked website check selection",source_url=profile.get("profile_url"),status="not_requested",result_summary="User did not select the linked website/domain check."))
        if options.check_public_complaints and steps<settings.max_tool_executions:
            from urllib.parse import urlparse
            domain=(urlparse(site).hostname or "") if site else ""
            display_name=profile.get("display_name") or ""
            queries=[f'"{profile.get("username","")}" scam OR fraud OR non-delivery OR complaint']
            if display_name and display_name.casefold()!=str(profile.get("username","")).casefold(): queries.append(f'"{display_name[:120]}" scam OR fraud OR non-delivery OR complaint')
            if domain: queries.append(f'"{domain}" scam OR refund OR complaint')
            collected=[]
            for query in queries:
                if steps>=settings.max_tool_executions: break
                steps+=1; result=await brave_complaint_search(query); status=result["status"]
                db.add(ToolAudit(case_id=c.id,run_id=run.id,tool_name="public_complaint_search",input_summary=query[:300],source_url="https://api.search.brave.com/res/v1/web/search",status=status,result_summary=result.get("reason") or f"{len(result['results'])} result(s)"))
                if status!="completed":
                    db.add(Finding(case_id=c.id,category="public_search_unavailable",claim=f"Public complaint search was unavailable: {result.get('reason','provider unavailable')}. No search conclusion can be drawn.",status="inconclusive",confidence=0,risk_weight=0,source_url="https://api.search.brave.com/res/v1/web/search",evidence_strength="weak"))
                matched=domain if domain and domain in query else display_name if display_name and display_name in query else profile.get("username")
                collected.extend({**item,"matched_identifier":matched} for item in result.get("results",[]))
            from app.services.instagram_assessment import deduplicate_results
            collected=deduplicate_results(collected)
            if collected:
                ev=save_json_evidence(db,c,"public-search-leads.json",{"retrieved_at":datetime.now(timezone.utc).isoformat(),"matched_identifiers":[profile.get("username"),domain or None],"results":collected},profile.get("profile_url"))
                db.add(Finding(case_id=c.id,category="public_complaint_leads",claim=f"Public search returned {len(collected)} deduplicated lead(s). Search snippets can be mistaken, syndicated, or allegations and were not independently verified; no risk points are assigned.",status="observed",confidence=0.25,risk_weight=0,evidence_id=ev.id,source_url="https://api.search.brave.com/res/v1/web/search",evidence_strength="weak"))
                for item in collected:
                    matched=", ".join(item.get("matched_identifiers",[])) or "identifier unavailable"
                    db.add(Finding(case_id=c.id,category="public_complaint_leads",claim=f"Unverified public search lead matched {matched}. {item.get('title','(untitled)')}: {item.get('snippet','')[:800]} Allegation/snippet only; verify the linked source independently.",status="observed",confidence=0.2,risk_weight=0,evidence_id=ev.id,source_url=item.get("url"),evidence_strength="weak"))
        elif options.check_public_complaints:
            db.add(ToolAudit(case_id=c.id,run_id=run.id,tool_name="public_complaint_search",input_summary="User-selected public complaint check",source_url="https://api.search.brave.com/res/v1/web/search",status="not_requested",result_summary="The investigation tool budget was reached before search could run."))
        else:
            db.add(ToolAudit(case_id=c.id,run_id=run.id,tool_name="public_complaint_search",input_summary="Public complaint check selection",source_url=None,status="not_requested",result_summary="User did not select public complaint search."))
        if options.check_images and steps<settings.max_tool_executions:
            profile_images=list(profile.get("image_urls",[]))
            website_images=site_result.get("image_urls",[]) if site_result and site_result.get("status")=="completed" else []
            candidates=(profile_images[:1]+website_images[:2]) if website_images else profile_images[:3]
            candidates=list(dict.fromkeys(candidates))[:3]
            if candidates:
                steps+=1
                image_result=await analyze_images(ImageAnalyze(case_id=c.id,image_urls=candidates),db)
                unavailable=[item for item in image_result.get("results",[]) if item.get("status")=="unavailable"]
                if unavailable:
                    db.add(Finding(case_id=c.id,category="image_check_unavailable",claim=f"{len(unavailable)} opted-in image URL(s) could not be safely retrieved: "+"; ".join(item.get("reason","unknown") for item in unavailable)[:600],status="inconclusive",confidence=0,risk_weight=0,evidence_strength="weak"))
                db.add(ToolAudit(case_id=c.id,run_id=run.id,tool_name="instagram_linked_image_similarity",input_summary="Up to three opted-in visible profile/linked-site image URLs",source_url=profile.get("profile_url"),status="completed",result_summary=f"Submitted {len(candidates)} bounded candidate image(s) to the existing image hash pipeline."))
            else:
                db.add(ToolAudit(case_id=c.id,run_id=run.id,tool_name="instagram_linked_image_similarity",input_summary="Opted-in image check",source_url=profile.get("profile_url"),status="unavailable",result_summary="No candidate profile or linked-site images were available."))
        elif options.check_images:
            db.add(ToolAudit(case_id=c.id,run_id=run.id,tool_name="instagram_linked_image_similarity",input_summary="User-selected image check",source_url=profile.get("profile_url"),status="not_requested",result_summary="The investigation tool budget was reached before image checks could run."))
        else:
            db.add(ToolAudit(case_id=c.id,run_id=run.id,tool_name="instagram_linked_image_similarity",input_summary="Image check selection",source_url=None,status="not_requested",result_summary="User did not select image comparison."))
        product_page=profile.get("product_page_url"); product_result=None
        if product_page:
            if settings.public_checks_enabled and steps<settings.max_tool_executions:
                steps+=1
                try:
                    product_result=await asyncio.wait_for(fetch_page(product_page),timeout=12)
                    status=product_result["status"]
                except Exception as exc: product_result={"status":"unavailable","error":str(exc)[:240],"url":product_page};status="unavailable"
                if status=="completed":
                    product_ev=save_json_evidence(db,c,"product-listing-observation.json",{"retrieved_at":datetime.now(timezone.utc).isoformat(),"requested_url":product_page,"title":product_result.get("title"),"text_excerpt":product_result.get("text_excerpt",""),"image_urls":product_result.get("image_urls",[])},product_result.get("url",product_page))
                    db.add(Finding(case_id=c.id,category="product_listing_observation",claim=f"User-provided product page was safely retrieved: '{product_result.get('title') or '(no title)'}'. Listing claims and media are unverified and are not independently corroborated.",status="observed",confidence=0.4,risk_weight=0,evidence_id=product_ev.id,source_url=product_result.get("url",product_page),evidence_strength="weak"))
                    summary=f"Retrieved listing title: {product_result.get('title') or '(no title)'}; bounded public page excerpt saved."
                else: summary=product_result.get("error","Page unavailable")
                db.add(ToolAudit(case_id=c.id,run_id=run.id,tool_name="product_page_fetch",input_summary="User-selected product listing URL validated by SSRF guard",source_url=product_result.get("url",product_page),status=status,result_summary=summary[:800]))
                if status=="completed" and options.check_images and product_result.get("image_urls") and steps<settings.max_tool_executions:
                    candidates=list(dict.fromkeys(product_result.get("image_urls",[])))[:3];steps+=1
                    await analyze_images(ImageAnalyze(case_id=c.id,image_urls=candidates),db)
                    db.add(ToolAudit(case_id=c.id,run_id=run.id,tool_name="product_listing_image_similarity",input_summary="Opted-in product listing images compared with case images",source_url=product_result.get("url",product_page),status="completed",result_summary=f"Submitted {len(candidates)} safe candidate URL(s) to the local image fingerprint pipeline."))
            else:
                db.add(ToolAudit(case_id=c.id,run_id=run.id,tool_name="product_page_fetch",input_summary="User-selected product listing URL",source_url=product_page,status="unavailable",result_summary="Public checks are disabled or the bounded tool budget was reached."))
    elif c.store_url and settings.public_checks_enabled and steps < settings.max_tool_executions:
        steps+=1
        try:
            result=await asyncio.wait_for(fetch_page(c.store_url),timeout=12)
            status=result["status"]; summary=(f"HTTP {result.get('http_status')}; page title: {result.get('title') or '(none)'}; excerpt: {result.get('text_excerpt','')[:500]}" if status=="completed" else result.get("error","Unavailable"))
            db.add(ToolAudit(case_id=c.id,run_id=run.id,tool_name="safe_page_fetch",input_summary="Validated store URL",source_url=result.get("url"),status=status,result_summary=summary))
            if status=="completed":
                text=result.get("text_excerpt","")
                lowered=text.casefold()
                page_markers={"contact_terms":any(x in lowered for x in ("contact","email","phone","address","customer service")),"shipping_terms":any(x in lowered for x in ("shipping","delivery","dispatch")),"refund_return_terms":any(x in lowered for x in ("refund","return","exchange","replacement")),"privacy_terms":"privacy" in lowered}
                ev=save_json_evidence(db,c,"retrieved-page.json",{"retrieved_at":datetime.now(timezone.utc).isoformat(),"result":result,"policy_terms":page_markers},result.get("url"))
                db.add(Finding(case_id=c.id,category="storefront_observation",claim=f"Retrieved public page titled '{result.get('title') or '(no title)'}'. Policy and contact indicators: "+", ".join(f"{k}={'found' if v else 'not detected'}" for k,v in page_markers.items()),status="observed",confidence=0.5,evidence_id=ev.id,source_url=result.get("url"),evidence_strength="weak"))
                from urllib.parse import urlparse, quote
                domain=(urlparse(result.get("url") or c.store_url).hostname or "").lower()
                if domain:
                    checks=[("rdap_domain_registration",f"https://rdap.org/domain/{quote(domain,safe='.-')}"),("wayback_archive_history",f"https://web.archive.org/cdx/search/cdx?url={quote(domain,safe='.-')}&output=json&fl=timestamp,original,statuscode&filter=statuscode:200&limit=10")]
                    for name,url in checks:
                        if steps>=settings.max_tool_executions: break
                        steps+=1; check_res=await safe_json_get(url); c_status=check_res["status"]
                        c_summary=json.dumps(check_res.get("data",check_res.get("reason")),ensure_ascii=False)[:1000]
                        db.add(ToolAudit(case_id=c.id,run_id=run.id,tool_name=name,input_summary="Store domain lookup",source_url=check_res.get("url",url),status=c_status,result_summary=c_summary))
                        if c_status=="completed":
                            ev_d=save_json_evidence(db,c,f"{name}.json",{"retrieved_at":datetime.now(timezone.utc).isoformat(),**check_res},check_res.get("url",url))
                            db.add(Finding(case_id=c.id,category=name,claim=f"Public {name.replace('_',' ')} response for {domain} saved as context.",status="observed",confidence=0.4,risk_weight=0,evidence_id=ev_d.id,source_url=check_res.get("url",url),evidence_strength="weak"))
        except Exception as e:
            db.add(ToolAudit(case_id=c.id,run_id=run.id,tool_name="safe_page_fetch",input_summary="Validated store URL",source_url=c.store_url,status="unavailable",result_summary=str(e)[:300]))
    run.steps_used=steps; run.status="completed"; run.finished_at=datetime.now(timezone.utc); c.status="completed"; db.flush()
    from app.services.risk_engine import RISK_RULES_VERSION
    stage1=assess(db.query(Finding).filter_by(case_id=c.id).all(),db.query(ToolAudit).filter_by(case_id=c.id).all())
    audit_rows=db.query(ToolAudit).filter_by(case_id=c.id).all()
    profile_has_content=bool(profile and (any(profile.get(key) is not None for key in ("followers","following","post_count")) or any(profile.get(key) for key in ("display_name","bio","posts","website_url"))))
    useful_audit=any(a.status=="completed" and a.tool_name!="engagement_sample_analysis" for a in audit_rows)
    sufficient=profile_has_content or useful_audit
    decision=recommendation(stage1["risk_indicator"],settings.video_verification_threshold,sufficient)
    save_json_evidence(db,c,"stage-1-assessment.json",{"stage":"preliminary_seller_assessment","score":stage1["risk_indicator"],"risk_rules_version":RISK_RULES_VERSION,"threshold":settings.video_verification_threshold,"decision":decision,"score_factors":stage1["factors"],"evidence_strength":stage1["evidence_strength"],"coverage":stage1["coverage"],"calculated_at":datetime.now(timezone.utc).isoformat()},c.store_url)
    discovered_summary=None
    if profile and profile.get("posts") and getattr(options,"auto_discover_media",True):
        from app.services.media_discovery import discover_and_analyze_instagram_media
        discovered_summary=await discover_and_analyze_instagram_media(db,c,profile,options,steps)
        if discovered_summary.get("has_inspected_video") and decision.get("recommend_video"):
            decision["recommend_video"]=False
            decision["status"]="verified_with_discovered_reel"
            decision["message"]="Relevant Instagram Reel was automatically discovered and analyzed. See Stage 2 video assessment."
    db.commit(); db.refresh(run)
    return {"id":run.id,"case_id":c.id,"status":run.status,"steps_used":steps,"stage1_score":stage1["risk_indicator"],"stage1":decision,"discovered_media":discovered_summary,"message":"Checks recorded. Findings remain provisional and source linked."}

@router.get("/investigations/{run_id}")
def get_investigation(run_id:str,db:Session=Depends(get_db)):
    run=db.get(InvestigationRun,run_id)
    if not run: raise HTTPException(404,"Investigation not found")
    return run

@router.get("/investigations/{run_id}/stream")
async def stream_investigation_progress(run_id: str, db: Session = Depends(get_db)):
    run = db.get(InvestigationRun, run_id)
    if not run:
        raise HTTPException(404, "Investigation run not found")

    async def event_generator():
        for _ in range(60):
            db.expire_all()
            current_run = db.get(InvestigationRun, run_id)
            if not current_run:
                break
            audits_count = db.query(ToolAudit).filter_by(case_id=current_run.case_id).count()
            findings_count = db.query(Finding).filter_by(case_id=current_run.case_id).count()
            data = json.dumps({
                "run_id": current_run.id,
                "case_id": current_run.case_id,
                "status": current_run.status,
                "steps_used": current_run.steps_used,
                "audits_count": audits_count,
                "findings_count": findings_count,
            })
            yield f"data: {data}\n\n"
            if current_run.status in {"completed", "failed"}:
                break
            await asyncio.sleep(0.5)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/cases/{case_id}/explain")
async def explain_case(case_id:str,db:Session=Depends(get_db)):
    c=case_or_404(db,case_id); pieces=[]
    for finding in c.findings[:12]:
        source=finding.source_url or "no external source"
        context=f"Finding {finding.id}; category={finding.category}; status={finding.status}; source={source}; claim={finding.claim[:1000]}"
        if finding.evidence_id:
            ev=db.get(Evidence,finding.evidence_id)
            if ev and Path(ev.storage_path).suffix.lower() in {".txt", ".json"}:
                try:
                    with open(ev.storage_path,"r",encoding="utf-8",errors="replace") as evidence_file: derived=evidence_file.read(1600)
                    context+=f"; linked evidence excerpt (untrusted): {derived}"
                except OSError: pass
        pieces.append(context)
    if not pieces: raise HTTPException(422,"Add evidence or findings before requesting a local explanation")
    allowed_ids=[e.id for e in c.evidence]
    explanation=await explain_untrusted_evidence("\n\n".join(pieces)[:6000],allowed_ids)
    if explanation is None: raise HTTPException(503,f"Local summary model {settings.ollama_text_model} did not return a usable response. Check that the model is installed and that the computer has enough free memory, then retry.")
    allowed_set=set(allowed_ids);explanation.evidence_ids=[evidence_id for evidence_id in explanation.evidence_ids if evidence_id in allowed_set]
    raw=explanation.model_dump_json(indent=2).encode("utf-8");eid=str(uuid.uuid4());folder=settings.data_dir/"evidence"/c.id;folder.mkdir(parents=True,exist_ok=True);path=folder/f"{eid}.json";path.write_bytes(raw)
    evidence=Evidence(id=eid,case_id=c.id,kind="text",filename="local-model-interpretation.json",storage_path=str(path.resolve()),sha256=hashlib.sha256(raw).hexdigest(),extraction_status="completed")
    db.add(evidence);db.flush()
    parts=[]
    if explanation.observations: parts.append("Observations: "+" ".join(explanation.observations[:5]))
    if explanation.uncertainties: parts.append("Uncertainties: "+" ".join(explanation.uncertainties[:5]))
    if explanation.next_checks: parts.append("Next checks: "+" ".join(explanation.next_checks[:5]))
    claim="Local Gemma interpretation (unverified): "+(" | ".join(parts) if parts else "No specific patterns detected.")
    db.add(Finding(case_id=c.id,category="model_interpretation",claim=claim[:4000],status="unverified",confidence=0.0,risk_weight=0,evidence_id=eid,evidence_strength="weak"))
    db.commit()
    return {"status":"unverified","model":settings.ollama_text_model,"evidence_id":eid,"evidence_ids":explanation.evidence_ids,"observations":explanation.observations,"uncertainties":explanation.uncertainties,"next_checks":explanation.next_checks,"risk_contribution":0}

@router.post("/cases/{case_id}/report",status_code=201)
@router.post("/cases/{case_id}/reports",status_code=201)
def generate_report(case_id:str,db:Session=Depends(get_db)):
    c=case_or_404(db,case_id); prev=db.query(Report).filter_by(case_id=c.id).count(); rid=str(uuid.uuid4()); audits=db.query(ToolAudit).filter_by(case_id=c.id).all()
    path,digest,risk=create_report(c,c.findings,audits,prev+1,rid)
    r=Report(id=rid,case_id=c.id,version=prev+1,storage_path=str(path.resolve()),risk_level=risk["risk_level"],evidence_snapshot_hash=digest); db.add(r); db.commit(); db.refresh(r)
    return {"id":r.id,"case_id":r.case_id,"version":r.version,"generated_at":r.generated_at,"risk_level":r.risk_level,"evidence_snapshot_hash":r.evidence_snapshot_hash,"download_url":f"/api/v1/reports/{r.id}/download"}

@router.get("/reports/{report_id}")
def report_metadata(report_id:str,db:Session=Depends(get_db)):
    r=db.get(Report,report_id)
    if not r: raise HTTPException(404,"Report not found")
    return {"id":r.id,"case_id":r.case_id,"version":r.version,"generated_at":r.generated_at,"risk_level":r.risk_level,"evidence_snapshot_hash":r.evidence_snapshot_hash,"download_url":f"/api/v1/reports/{r.id}/download"}

@router.get("/reports/{report_id}/download")
def download_report(report_id:str,db:Session=Depends(get_db)):
    r=db.get(Report,report_id)
    if not r: raise HTTPException(404,"Report not found")
    return FileResponse(r.storage_path,media_type="application/pdf",filename=f"haki-report-{r.id[:8]}.pdf")

class ScanPayload(BaseModel):
    store_url: str | None = None
    seller_handle: str | None = None
    product_name: str | None = None
    instagram_url: str | None = None
    user_supplied_bio: str | None = None
    sale_price: float | None = None
    original_price: float | None = None
    reference_price: float | None = None
    products: list[dict] | None = None
    rdap_data: dict | None = None
    complaint_leads: list[dict] | None = None

@router.post("/scan", status_code=201)
async def scan_seller(payload: ScanPayload, db: Session = Depends(get_db)):
    """Orchestrate an investigation using the LangGraph state machine.

    Pipeline:
      validate -> profile -> inspect_site -> [catalog_pricing | domain_identity | complaints]
      -> dedupe -> score -> explain -> report
    """
    store_url = payload.store_url
    if store_url:
        try:
            store_url = validate_url_for_storage(store_url)
        except UnsafeURL as e:
            raise HTTPException(422, f"Unsafe or invalid store URL: {e}")

    seller_handle = payload.seller_handle
    if not seller_handle and payload.instagram_url:
        from urllib.parse import urlparse
        path_parts = urlparse(payload.instagram_url).path.strip("/").split("/")
        if path_parts:
            seller_handle = path_parts[0]

    title = payload.product_name or seller_handle or store_url or "Online Storefront Scan"
    c = Case(
        title=title[:240],
        mode="pre_purchase",
        status="investigating",
        store_url=store_url,
        seller_handle=seller_handle,
        product_name=payload.product_name,
        notes=payload.user_supplied_bio,
    )
    db.add(c)
    db.commit()
    db.refresh(c)

    ig_profile = None
    if seller_handle or payload.user_supplied_bio:
        ig_profile = {
            "username": seller_handle or "",
            "biography": payload.user_supplied_bio or "",
            "external_url": store_url or payload.instagram_url or "",
        }

    state = {
        "case_id": c.id,
        "store_url": store_url,
        "seller_handle": seller_handle,
        "product_name": payload.product_name,
        "user_supplied_bio": payload.user_supplied_bio,
        "sale_price": payload.sale_price,
        "original_price": payload.original_price,
        "reference_price": payload.reference_price,
        "instagram_profile": ig_profile,
        "products": payload.products or [],
        "rdap_data": payload.rdap_data,
        "complaint_leads": payload.complaint_leads or [],
        "is_cancelled": False,
        "findings": [],
        "evidence": [],
        "errors": [],
        "audits": [],
        "retry_counts": {},
        "website_data": None,
        "scoring_result": None,
        "explanation": None,
        "report_summary": None,
    }

    result = await investigation_graph.ainvoke(state)

    # Persist evidence records
    for ev_model in result.get("evidence", []):
        if ev_model.raw_data:
            save_json_evidence(db, c, f"{ev_model.kind}-evidence.json", ev_model.raw_data, ev_model.source_url)

    # Persist findings
    for f in result.get("findings", []):
        weight = SEVERITY_WEIGHTS.get(f.severity, 0) if f.outcome == "positive" else 0
        db.add(Finding(
            case_id=c.id,
            category=f.rule_id,
            claim=f.rationale,
            status="corroborated" if f.outcome == "positive" else "unverified" if f.outcome == "unknown" else "observed",
            confidence=0.8 if f.outcome == "positive" else 0.0,
            risk_weight=weight,
            source_url=f.source,
            evidence_strength="strong" if f.outcome == "positive" else "weak",
        ))

    # Persist audits
    for a in result.get("audits", []):
        db.add(ToolAudit(
            case_id=c.id,
            run_id="langgraph-scan",
            tool_name=a.get("tool_name", "unknown_tool"),
            input_summary=f"Automated graph node inspection for {c.id}",
            source_url=a.get("source_url"),
            status=a.get("status", "completed"),
            result_summary=a.get("result_summary", ""),
        ))

    c.status = "completed"
    db.commit()

    # Generate PDF report
    audits_list = db.query(ToolAudit).filter_by(case_id=c.id).all()
    rid = str(uuid.uuid4())
    path, digest, risk = create_report(c, c.findings, audits_list, 1, rid)
    rep = Report(
        id=rid,
        case_id=c.id,
        version=1,
        storage_path=str(path.resolve()),
        risk_level=risk["risk_level"],
        evidence_snapshot_hash=digest,
    )
    db.add(rep)
    db.commit()

    score_res = result.get("scoring_result") or {}
    explanation = result.get("explanation") or {}

    contradictions = [
        f.rationale for f in result.get("findings", [])
        if f.rule_id in {"policy_conflicts", "brand_domain_mismatch", "instagram_claims_vs_website"}
        and f.outcome == "positive"
    ]

    return {
        "case_id": c.id,
        "risk_score": score_res.get("risk_score", 0),
        "risk_band": score_res.get("risk_band", "low"),
        "confidence": score_res.get("confidence", 0.0),
        "coverage": score_res.get("coverage", {}),
        "reasons": score_res.get("factors", []),
        "limitations": [
            "Instagram data depends on user input; coverage is lower when not provided.",
            "RDAP data is frequently redacted; domain age may be unknown.",
            "All weights are un-calibrated; scores are provisional indicators, not fraud verdicts.",
            "AI media detection is low-confidence observation only.",
        ],
        "contradictions": contradictions,
        "next_steps": explanation.get("next_checks", [
            "Verify payment methods use buyer-protected checkout.",
            "Compare product imagery with manufacturer stock photos.",
        ]),
        "stage2_recommended": (result.get("report_summary") or {}).get("stage2_recommended", False),
        "stage2_threshold": settings.stage2_threshold,
        "explanation": explanation,
        "findings": [f.model_dump() for f in result.get("findings", [])],
        "audits": result.get("audits", []),
        "report_id": rep.id,
        "report_url": f"/api/v1/reports/{rep.id}/download",
    }

@router.post("/scan/{case_id}/video", status_code=201)
async def scan_stage2_video(
    case_id: str,
    file: UploadFile = File(...),
    reference_text: str = Form("", max_length=1000),
    db: Session = Depends(get_db),
):
    """Optional Stage 2 video analysis graph endpoint."""
    return await verify_product_video(case_id, file, reference_text, db)

