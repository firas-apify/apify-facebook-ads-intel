"""Pydantic models for input configuration and output data."""

from datetime import date, datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, HttpUrl


def utc_now() -> datetime:
    """Return timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


class AdStatus(str, Enum):
    """Facebook Ad status filter."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    ALL = "all"


class MediaType(str, Enum):
    """Ad media type classification."""

    IMAGE = "image"
    VIDEO = "video"
    CAROUSEL = "carousel"
    UNKNOWN = "unknown"


class AdAngle(str, Enum):
    """Classification of ad messaging angle."""

    PROBLEM_SOLUTION = "problem_solution"
    TESTIMONIAL = "testimonial"
    COMPARISON = "comparison"
    URGENCY = "urgency"
    EDUCATIONAL = "educational"
    LIFESTYLE = "lifestyle"
    DISCOUNT = "discount"
    NEW_PRODUCT = "new_product"
    UNKNOWN = "unknown"


class HookStyle(str, Enum):
    """Classification of ad hook/opening style."""

    QUESTION = "question"
    STATISTIC = "statistic"
    BOLD_CLAIM = "bold_claim"
    STORY = "story"
    SOCIAL_PROOF = "social_proof"
    PAIN_POINT = "pain_point"
    BENEFIT = "benefit"
    UNKNOWN = "unknown"


class OfferType(str, Enum):
    """Classification of offer in the ad."""

    PERCENTAGE_OFF = "percentage_off"
    FIXED_DISCOUNT = "fixed_discount"
    FREE_SHIPPING = "free_shipping"
    BOGO = "bogo"
    FREE_TRIAL = "free_trial"
    LIMITED_TIME = "limited_time"
    NO_OFFER = "no_offer"
    UNKNOWN = "unknown"


class ActorInput(BaseModel):
    """Input configuration for the Facebook Ads Intelligence actor."""

    advertiser_ids: list[str] = Field(
        default_factory=list,
        description="List of Facebook Page IDs to monitor",
    )
    search_terms: list[str] = Field(
        default_factory=list,
        description="Keywords to search for in ads",
    )
    country_code: str = Field(
        default="US",
        description="ISO country code for geo-targeting (e.g., US, GB, DE)",
    )
    ad_status: AdStatus = Field(
        default=AdStatus.ACTIVE,
        description="Filter by ad status",
    )
    start_date: Optional[date] = Field(
        default=None,
        description="Start date for ad search range",
    )
    end_date: Optional[date] = Field(
        default=None,
        description="End date for ad search range",
    )
    max_ads_per_advertiser: int = Field(
        default=100,
        ge=1,
        le=1000,
        description="Maximum ads to collect per advertiser",
    )
    include_media_urls: bool = Field(
        default=True,
        description="Whether to extract media URLs",
    )
    classify_ads: bool = Field(
        default=True,
        description="Whether to classify ad angles, hooks, and offers",
    )


class AdCreative(BaseModel):
    """Extracted ad creative data."""

    ad_id: str = Field(description="Unique Facebook ad ID")
    advertiser_id: str = Field(description="Facebook Page ID of advertiser")
    advertiser_name: str = Field(description="Name of the advertiser page")
    ad_text: Optional[str] = Field(default=None, description="Primary ad copy text")
    headline: Optional[str] = Field(default=None, description="Ad headline")
    description: Optional[str] = Field(default=None, description="Ad description")
    cta_text: Optional[str] = Field(default=None, description="Call-to-action button text")
    cta_link: Optional[str] = Field(default=None, description="Call-to-action destination URL")
    landing_page_url: Optional[str] = Field(default=None, description="Final landing page URL")
    media_type: MediaType = Field(default=MediaType.UNKNOWN, description="Type of ad media")
    media_urls: list[str] = Field(default_factory=list, description="URLs of ad media")
    is_active: bool = Field(default=True, description="Whether the ad is currently active")
    started_running: Optional[date] = Field(default=None, description="Date ad started running")
    ended_running: Optional[date] = Field(default=None, description="Date ad stopped running")
    platforms: list[str] = Field(default_factory=list, description="Platforms where ad runs")
    impressions_lower: Optional[int] = Field(default=None, description="Lower bound of impressions")
    impressions_upper: Optional[int] = Field(default=None, description="Upper bound of impressions")
    spend_lower: Optional[float] = Field(default=None, description="Lower bound of spend")
    spend_upper: Optional[float] = Field(default=None, description="Upper bound of spend")
    country_code: str = Field(description="Country where ad was found")
    scraped_at: datetime = Field(default_factory=utc_now, description="Timestamp of scrape")

    # Classification fields
    ad_angle: Optional[AdAngle] = Field(default=None, description="Classified ad angle")
    hook_style: Optional[HookStyle] = Field(default=None, description="Classified hook style")
    offer_type: Optional[OfferType] = Field(default=None, description="Classified offer type")

    # Computed metrics
    days_running: Optional[int] = Field(default=None, description="Number of days ad has been running")


class AdvertiserSummary(BaseModel):
    """Summary statistics for an advertiser."""

    advertiser_id: str
    advertiser_name: str
    total_ads: int = 0
    active_ads: int = 0
    media_type_breakdown: dict[str, int] = Field(default_factory=dict)
    ad_angle_breakdown: dict[str, int] = Field(default_factory=dict)
    hook_style_breakdown: dict[str, int] = Field(default_factory=dict)
    offer_type_breakdown: dict[str, int] = Field(default_factory=dict)
    cta_breakdown: dict[str, int] = Field(default_factory=dict)
    avg_days_running: Optional[float] = None
    new_ads_last_7_days: int = 0
    new_ads_last_30_days: int = 0


class WeeklySummary(BaseModel):
    """Weekly summary for BI tools."""

    report_date: date
    report_week: int
    total_advertisers_monitored: int
    total_ads_collected: int
    new_ads_this_week: int
    ads_stopped_this_week: int
    top_ad_angles: list[tuple[str, int]]
    top_hook_styles: list[tuple[str, int]]
    top_offer_types: list[tuple[str, int]]
    top_ctas: list[tuple[str, int]]
    media_type_trends: dict[str, int]
    advertiser_summaries: list[AdvertiserSummary]
