from pathlib import Path
from PIL import Image
import io

ALLOWED = {"image/jpeg": ("jpg", {"image/jpeg"}), "image/png": ("png", {"image/png"}),
           "image/webp": ("webp", {"image/webp"}), "video/mp4": ("mp4", {"video/mp4"}),
           "video/quicktime": ("mov", {"video/quicktime"}),
           "application/pdf": ("pdf", {"application/pdf"}), "text/plain": ("txt", {"text/plain"})}

def detect_type(data: bytes):
    if data.startswith(b"%PDF-"): return "application/pdf"
    if data.startswith(b"\x89PNG\r\n\x1a\n"): return "image/png"
    if data.startswith(b"\xff\xd8\xff"): return "image/jpeg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP": return "image/webp"
    if len(data) > 12 and data[4:8] == b"ftyp":
        brand=data[8:12]
        return "video/quicktime" if brand in {b"qt  ",b"qt\x00\x00"} else "video/mp4"
    try:
        data.decode("utf-8")
        if b"\x00" not in data: return "text/plain"
    except UnicodeDecodeError: pass
    return None

def validate_upload(data: bytes, declared: str, max_bytes: int):
    if not data: raise ValueError("Empty files are not accepted")
    if len(data) > max_bytes: raise ValueError(f"File exceeds {max_bytes // (1024*1024)} MB limit")
    actual = detect_type(data)
    if actual is None or actual != declared: raise ValueError("File content does not match a supported file type")
    if actual.startswith("image/"):
        try:
            with Image.open(io.BytesIO(data)) as img:
                if img.width * img.height > 20_000_000: raise ValueError("Image dimensions exceed 20 megapixels")
                img.verify()
        except Exception as e: raise ValueError("Image file is malformed") from e
    return actual
