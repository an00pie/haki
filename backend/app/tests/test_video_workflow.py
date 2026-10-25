import subprocess
from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app
from app.api import routes
from app.config import settings
from app.services.risk_engine import assess
from app.tools.video_analysis import inspect_video, extract_frames

client=TestClient(app)

def make_clip(path: Path, duration="3"):
    subprocess.run(["ffmpeg","-v","error","-f","lavfi","-i",f"testsrc2=size=160x120:rate=2:duration={duration}","-an","-c:v","mpeg4","-threads","1","-y",str(path)],check=True,timeout=20)
    return path

def test_threshold_cases_and_insufficient_coverage():
    assert routes.recommendation(39,40,True)["status"]=="optional"
    assert routes.recommendation(40,40,True)["recommend_video"] is True
    assert routes.recommendation(41,40,True)["recommend_video"] is True
    assert routes.recommendation(100,40,False)["status"]=="insufficient_evidence"
    assert routes.recommendation(0,40,False)["recommend_video"] is False

def test_workflow_config_is_provisional_default():
    value=client.get("/api/v1/workflow/config").json()
    assert value["video_verification_threshold"]==40
    assert value["supported_video_types"]==["video/mp4","video/quicktime"]

def test_synthetic_video_metadata_and_unique_timestamped_frames(tmp_path):
    video=make_clip(tmp_path/"sample.mp4")
    metadata=inspect_video(video)
    assert metadata["duration_seconds"]==3
    assert metadata["width"]==160 and metadata["height"]==120
    frames=extract_frames(video,metadata["duration_seconds"])
    assert 1<=len(frames)<=settings.max_video_frames
    assert all(0<=frame["timestamp_seconds"]<metadata["duration_seconds"] for frame in frames)
    assert all(frame["jpeg"].startswith(b"\xff\xd8\xff") for frame in frames)

def test_static_synthetic_video_deduplicates_near_identical_frames(tmp_path):
    path=tmp_path/"static.mp4"
    subprocess.run(["ffmpeg","-v","error","-f","lavfi","-i","color=c=red:size=160x120:rate=2:duration=3","-an","-c:v","mpeg4","-threads","1","-y",str(path)],check=True,timeout=20)
    metadata=inspect_video(path)
    frames=extract_frames(path,metadata["duration_seconds"])
    assert len(frames)==1

def test_website_case_without_supported_checks_is_marked_insufficient_and_seller_only_pdf(monkeypatch):
    monkeypatch.setattr(settings,"public_checks_enabled",False)
    case_id=client.post("/api/v1/inspect",json={"url":"https://example.invalid/item","title":"Sample item"}).json()["case_id"]
    client.post(f"/api/v1/cases/{case_id}/investigations")
    detail=client.get(f"/api/v1/cases/{case_id}").json()
    assert detail["stage1"]["decision"]["status"]=="insufficient_evidence"
    assert detail["stage2"] is None
    report=client.post(f"/api/v1/cases/{case_id}/report")
    response=client.get(report.json()["download_url"])
    assert response.status_code==200 and response.headers["content-type"]=="application/pdf"
    assert client.delete(f"/api/v1/cases/{case_id}").status_code==204

def test_rejects_malformed_video_and_size_over_limit(monkeypatch):
    case=client.post("/api/v1/cases",json={"title":"Video fixture"}).json()
    bad=client.post(f"/api/v1/cases/{case['id']}/video/verify",files={"file":("bad.mp4",b"not a video","video/mp4")})
    assert bad.status_code==422
    oversized=b"\x00\x00\x00\x18ftypisom"+b"x"*(1024*1024+16)
    try:
        monkeypatch.setattr(settings,"max_video_upload_mb",1)
        response=client.post(f"/api/v1/cases/{case['id']}/video/verify",files={"file":("large.mp4",oversized,"video/mp4")})
        assert response.status_code==422
        assert "exceeds" in response.json()["detail"].lower()
    finally:
        client.delete(f"/api/v1/cases/{case['id']}")

def test_optional_video_keeps_deterministic_seller_score_and_delete_cleans_frames(tmp_path,monkeypatch):
    case_id=client.post("/api/v1/instagram/inspect",json={"profile_url":"https://www.instagram.com/sample.shop/","username":"sample.shop","display_name":"Sample Shop"}).json()["case_id"]
    client.post(f"/api/v1/cases/{case_id}/investigations",json={"check_linked_site":False,"check_public_complaints":False,"check_images":False})
    stage1=client.get(f"/api/v1/cases/{case_id}").json()["stage1"]
    assert stage1["decision"]["status"]=="optional" and stage1["score"]<stage1["threshold"]
    before=client.get(f"/api/v1/cases/{case_id}").json()["risk"]["risk_indicator"]
    async def no_vision(*_): return None
    monkeypatch.setattr(routes,"describe_video_frames",no_vision)
    clip=make_clip(tmp_path/"product.mp4")
    response=client.post(f"/api/v1/cases/{case_id}/video/verify",files={"file":("product.mp4",clip.read_bytes(),"video/mp4")})
    assert response.status_code==201,response.text
    body=response.json()
    assert body["stage2"]["ocr"]["status"]=="unavailable"
    assert body["stage2"]["transcription"]["status"]=="unavailable"
    assert body["stage2"]["risk_score_change"]==0
    detail=client.get(f"/api/v1/cases/{case_id}").json()
    assert detail["risk"]["risk_indicator"]==before
    assert detail["stage2"]["sampled_frame_count"]>=1
    evidence_ids={e["id"] for e in detail["evidence"]}
    assert body["analysis_evidence_id"] in evidence_ids
    deleted=client.delete(f"/api/v1/cases/{case_id}/video")
    assert deleted.status_code==200
    after=client.get(f"/api/v1/cases/{case_id}").json()
    assert after["stage2"] is None
    assert not any(e["kind"]=="video" or e["filename"].startswith("video-frame-") for e in after["evidence"])
    assert client.delete(f"/api/v1/cases/{case_id}").status_code==204
