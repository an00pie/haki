from PIL import Image, ImageDraw
from app.tools.image_analysis import difference_hash, hamming_distance, is_visual_candidate

def test_difference_hash_is_reproducible_and_detects_changed_image(tmp_path):
    a=Image.new("RGB",(80,60),"white")
    ImageDraw.Draw(a).rectangle((5,5,40,55),fill="black")
    b=a.copy();ImageDraw.Draw(b).rectangle((41,5,75,55),fill="black")
    pa,pb=tmp_path/"a.png",tmp_path/"b.png";a.save(pa);b.save(pb)
    first=difference_hash(pa)
    assert first==difference_hash(pa)
    assert 0<=hamming_distance(first,difference_hash(pb))<=64
    assert hamming_distance(first,first)==0
    assert is_visual_candidate(0)
    assert not is_visual_candidate(7)
