from pydantic import BaseModel, Field
from typing import Literal, Annotated
from uuid import UUID

class PageInspect(BaseModel):
    url: str = Field(min_length=8, max_length=2048)
    client_request_id: UUID | None = None
    title: str = Field(default="", max_length=500)
    source: Literal["browser_extension"] = "browser_extension"
    mode: Literal["pre_purchase", "post_purchase", "both"] = "pre_purchase"
    product_name: str | None = Field(default=None, max_length=500)
    price_text: str | None = Field(default=None, max_length=160)
    seller_text: str | None = Field(default=None, max_length=1000)
    image_urls: list[str] = Field(default_factory=list, max_length=8)

class ImageAnalyze(BaseModel):
    case_id: str
    image_urls: list[str] = Field(min_length=1, max_length=3)

class InstagramPost(BaseModel):
    url: str | None = Field(default=None, max_length=2048)
    caption: str | None = Field(default=None, max_length=1200)
    timestamp: str | None = Field(default=None, max_length=80)
    likes: int | None = Field(default=None, ge=0)
    comments_count: int | None = Field(default=None, ge=0)
    comment_samples: list[Annotated[str, Field(max_length=300)]] = Field(default_factory=list, max_length=12)
    image_urls: list[Annotated[str, Field(max_length=2048)]] = Field(default_factory=list, max_length=4)
    is_reel: bool = False
    video_url: str | None = Field(default=None, max_length=2048)
    media_type: Literal["image", "video", "carousel", "reel", "unknown"] = "unknown"

class InstagramInspect(BaseModel):
    profile_url: str = Field(min_length=8, max_length=2048)
    client_request_id: UUID | None = None
    username: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9._]+$")
    display_name: str | None = Field(default=None, max_length=240)
    bio: str | None = Field(default=None, max_length=2000)
    website_url: str | None = Field(default=None, max_length=2048)
    product_page_url: str | None = Field(default=None, max_length=2048)
    product_name: str | None = Field(default=None, max_length=240)
    followers: int | None = Field(default=None, ge=0)
    following: int | None = Field(default=None, ge=0)
    post_count: int | None = Field(default=None, ge=0)
    earliest_post_date: str | None = Field(default=None, max_length=120)
    posts: list[InstagramPost] = Field(default_factory=list, max_length=8)
    image_urls: list[Annotated[str, Field(max_length=2048)]] = Field(default_factory=list, max_length=12)

class InstagramInvestigationOptions(BaseModel):
    check_linked_site: bool = True
    check_public_complaints: bool = False
    check_images: bool = False
    auto_discover_media: bool = True
    max_media_candidates: int = Field(default=3, ge=1, le=5)
