"""Bounded, local video sampling. Temporary decoded frames are always removed."""
from __future__ import annotations
import json, shutil, subprocess, tempfile
from pathlib import Path
from PIL import Image
from app.config import settings
from app.tools.image_analysis import difference_hash, hamming_distance

class VideoError(ValueError): pass

def _run(args: list[str], timeout: int) -> bytes:
    try:
        result=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=timeout,check=False)
    except (OSError,subprocess.TimeoutExpired) as exc:
        raise VideoError("Video tools are unavailable or exceeded the processing time limit") from exc
    if result.returncode: raise VideoError("Video is malformed or could not be decoded")
    return result.stdout

def inspect_video(path: str | Path) -> dict:
    if not shutil.which("ffprobe") or not shutil.which("ffmpeg"):
        raise VideoError("FFmpeg and ffprobe are required for local video analysis")
    path=Path(path)
    raw=_run(["ffprobe","-v","error","-select_streams","v:0","-show_entries","stream=codec_name,width,height,r_frame_rate:format=duration,format_name","-of","json",str(path)],15)
    try:
        data=json.loads(raw); stream=data["streams"][0]; duration=float(data["format"]["duration"])
        width=int(stream["width"]);height=int(stream["height"])
    except (ValueError,KeyError,IndexError,TypeError) as exc: raise VideoError("Video metadata is missing or invalid") from exc
    if not 0 < duration <= settings.max_video_duration_seconds: raise VideoError(f"Video duration must be at most {settings.max_video_duration_seconds} seconds")
    if width<16 or height<16 or width>8192 or height>8192 or width*height>16_000_000 or max(width,height)/min(width,height)>10: raise VideoError("Video resolution or aspect ratio is invalid or exceeds the local processing limit")
    return {"duration_seconds":round(duration,3),"width":width,"height":height,"frame_rate":stream.get("r_frame_rate"),"codec":stream.get("codec_name"),"container":data.get("format",{}).get("format_name")}

def extract_frames(path: str | Path, duration: float) -> list[dict]:
    max_frames=settings.max_video_frames
    interval=max(1.0,duration/max_frames)
    frames=[]; hashes=[]
    import time
    deadline=time.monotonic()+75
    with tempfile.TemporaryDirectory(prefix="haki-video-") as folder:
        for index in range(max_frames):
            if time.monotonic()>=deadline: break
            timestamp=min(duration-0.05,index*interval)
            if timestamp<0: break
            target=Path(folder)/f"frame-{index:02d}.jpg"
            try:
                _run(["ffmpeg","-v","error","-threads","1","-filter_threads","1","-ss",f"{timestamp:.3f}","-i",str(path),"-frames:v","1","-vf","scale='min(640,iw)':-2","-q:v","4","-y",str(target)],max(1,min(8,int(deadline-time.monotonic()))))
                if not target.exists(): continue
                with Image.open(target) as image:
                    image.verify()
                value=difference_hash(target)
                if any(hamming_distance(value,prior)<=3 for prior in hashes): continue
                hashes.append(value)
                frames.append({"timestamp_seconds":round(timestamp,3),"jpeg":target.read_bytes(),"difference_hash":f"{value:016x}"})
            except (VideoError,OSError,ValueError):
                continue
    if not frames: raise VideoError("No decodable representative frames were found")
    return frames

def extract_ocr(frames:list[dict])->dict:
    executable=shutil.which("tesseract")
    if not executable:return {"status":"unavailable","reason":"Local Tesseract OCR is not installed.","samples":[]}
    samples=[]
    with tempfile.TemporaryDirectory(prefix="haki-ocr-") as folder:
        for index,frame in enumerate(frames[:4]):
            path=Path(folder)/f"frame-{index}.jpg";path.write_bytes(frame["jpeg"])
            try:
                text=_run([executable,str(path),"stdout","--psm","6"],6).decode("utf-8",errors="replace")[:1200].strip()
                samples.append({"timestamp_seconds":frame["timestamp_seconds"],"text":text})
            except VideoError:
                samples.append({"timestamp_seconds":frame["timestamp_seconds"],"text":"","status":"unavailable"})
    return {"status":"completed" if any(item.get("text") for item in samples) else "completed_no_text","engine":"tesseract","samples":samples}
