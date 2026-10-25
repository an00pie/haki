from PIL import Image, ImageOps
from pathlib import Path

MAX_SIMILAR_DISTANCE=6

def difference_hash(path: str | Path) -> int:
    """A deterministic 64-bit difference hash, for within-case visual comparison only."""
    with Image.open(path) as source:
        if source.width * source.height > 20_000_000: raise ValueError("Image dimensions exceed 20 megapixels")
        image=ImageOps.exif_transpose(source).convert("L").resize((9,8),Image.Resampling.LANCZOS)
        pixels=list(image.getdata())
    value=0
    for row in range(8):
        for col in range(8):
            value=(value<<1) | int(pixels[row*9+col] > pixels[row*9+col+1])
    return value

def hamming_distance(left: int,right: int)->int:
    return (left^right).bit_count()

def is_visual_candidate(distance:int)->bool:
    """A high precision candidate threshold; a match is a review clue, not provenance proof."""
    return 0<=distance<=MAX_SIMILAR_DISTANCE
