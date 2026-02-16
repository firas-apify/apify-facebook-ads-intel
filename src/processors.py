"""Ad classification and processing logic."""

import re
from datetime import date, timedelta
from collections import Counter

from .models import (
    AdAngle,
    AdCreative,
    AdvertiserSummary,
    HookStyle,
    OfferType,
    WeeklySummary,
)


class AdClassifier:
    """Classifies ad creative elements based on text analysis."""

    # Patterns for ad angle classification
    ANGLE_PATTERNS = {
        AdAngle.PROBLEM_SOLUTION: [
            r"tired of",
            r"struggling with",
            r"finally\s+a\s+solution",
            r"say goodbye to",
            r"no more",
            r"stop\s+\w+ing",
        ],
        AdAngle.TESTIMONIAL: [
            r"customer\s+reviews?",
            r"what\s+\w+\s+are\s+saying",
            r"loved\s+by",
            r"rated\s+\d+",
            r"★+",
            r"\d+\s+reviews?",
        ],
        AdAngle.COMPARISON: [
            r"vs\.?",
            r"compared\s+to",
            r"unlike\s+other",
            r"better\s+than",
            r"why\s+choose",
        ],
        AdAngle.URGENCY: [
            r"limited\s+time",
            r"ends?\s+soon",
            r"last\s+chance",
            r"only\s+\d+\s+left",
            r"hurry",
            r"don'?t\s+miss",
            r"act\s+now",
        ],
        AdAngle.EDUCATIONAL: [
            r"how\s+to",
            r"learn\s+",
            r"discover\s+",
            r"guide",
            r"tips?\s+",
            r"secrets?\s+",
        ],
        AdAngle.LIFESTYLE: [
            r"lifestyle",
            r"live\s+your",
            r"dream\s+",
            r"experience\s+",
            r"journey",
        ],
        AdAngle.DISCOUNT: [
            r"\d+%\s*off",
            r"save\s+\$?\d+",
            r"discount",
            r"sale\b",
            r"deal\b",
        ],
        AdAngle.NEW_PRODUCT: [
            r"new\s+",
            r"introducing",
            r"just\s+launched",
            r"now\s+available",
            r"announcing",
        ],
    }

    # Patterns for hook style classification
    HOOK_PATTERNS = {
        HookStyle.QUESTION: [r"^[^.!]*\?", r"^(do|are|is|have|can|will|what|why|how|when|where)\s"],
        HookStyle.STATISTIC: [r"^\d+%", r"^\d+\s+(out\s+of|in)", r"^studies?\s+show"],
        HookStyle.BOLD_CLAIM: [r"^the\s+(best|only|#1|number\s+one)", r"^guaranteed", r"^proven"],
        HookStyle.STORY: [r"^(i|we|my)\s+", r"^when\s+i", r"^last\s+(week|month|year)"],
        HookStyle.SOCIAL_PROOF: [r"^\d+[k+]?\s+(people|customers|users)", r"^join\s+\d+"],
        HookStyle.PAIN_POINT: [r"^tired\s+of", r"^frustrated", r"^sick\s+of", r"^struggling"],
        HookStyle.BENEFIT: [r"^get\s+", r"^achieve\s+", r"^unlock\s+", r"^transform\s+"],
    }

    # Patterns for offer type classification
    OFFER_PATTERNS = {
        OfferType.PERCENTAGE_OFF: [r"\d+%\s*(off|discount)"],
        OfferType.FIXED_DISCOUNT: [r"\$\d+\s*off", r"save\s+\$\d+"],
        OfferType.FREE_SHIPPING: [r"free\s+shipping", r"free\s+delivery"],
        OfferType.BOGO: [r"buy\s+\d+\s+get\s+\d+", r"bogo", r"buy\s+one\s+get\s+one"],
        OfferType.FREE_TRIAL: [r"free\s+trial", r"try\s+(it\s+)?free", r"\d+[\s-]day\s+trial"],
        OfferType.LIMITED_TIME: [r"limited\s+time", r"today\s+only", r"ends?\s+(tonight|today|soon)"],
    }

    def classify_ad_angle(self, text: str) -> AdAngle:
        """Classify the primary angle/approach of the ad."""
        if not text:
            return AdAngle.UNKNOWN

        text_lower = text.lower()
        scores: dict[AdAngle, int] = {}

        for angle, patterns in self.ANGLE_PATTERNS.items():
            score = sum(1 for p in patterns if re.search(p, text_lower))
            if score > 0:
                scores[angle] = score

        if scores:
            return max(scores, key=scores.get)
        return AdAngle.UNKNOWN

    def classify_hook_style(self, text: str) -> HookStyle:
        """Classify the opening hook style of the ad."""
        if not text:
            return HookStyle.UNKNOWN

        # Focus on the first sentence/line
        first_line = text.split("\n")[0].strip()
        first_sentence = re.split(r"[.!?]", first_line)[0].strip()
        text_lower = first_sentence.lower()

        for style, patterns in self.HOOK_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    return style

        return HookStyle.UNKNOWN

    def classify_offer_type(self, text: str) -> OfferType:
        """Classify the type of offer in the ad."""
        if not text:
            return OfferType.UNKNOWN

        text_lower = text.lower()

        for offer_type, patterns in self.OFFER_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    return offer_type

        return OfferType.NO_OFFER

    def classify_ad(self, ad: AdCreative) -> AdCreative:
        """Apply all classifications to an ad creative."""
        full_text = " ".join(
            filter(None, [ad.ad_text, ad.headline, ad.description])
        )

        ad.ad_angle = self.classify_ad_angle(full_text)
        ad.hook_style = self.classify_hook_style(full_text)
        ad.offer_type = self.classify_offer_type(full_text)

        # Calculate days running
        if ad.started_running:
            end_date = ad.ended_running or date.today()
            ad.days_running = (end_date - ad.started_running).days

        return ad


class TrendAnalyzer:
    """Analyzes trends and generates summaries."""

    def generate_advertiser_summary(
        self, advertiser_id: str, advertiser_name: str, ads: list[AdCreative]
    ) -> AdvertiserSummary:
        """Generate summary statistics for an advertiser."""
        today = date.today()
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)

        summary = AdvertiserSummary(
            advertiser_id=advertiser_id,
            advertiser_name=advertiser_name,
            total_ads=len(ads),
            active_ads=sum(1 for ad in ads if ad.is_active),
        )

        # Breakdowns
        summary.media_type_breakdown = dict(Counter(ad.media_type.value for ad in ads))
        summary.ad_angle_breakdown = dict(
            Counter(ad.ad_angle.value for ad in ads if ad.ad_angle)
        )
        summary.hook_style_breakdown = dict(
            Counter(ad.hook_style.value for ad in ads if ad.hook_style)
        )
        summary.offer_type_breakdown = dict(
            Counter(ad.offer_type.value for ad in ads if ad.offer_type)
        )
        summary.cta_breakdown = dict(
            Counter(ad.cta_text for ad in ads if ad.cta_text)
        )

        # Average days running
        days_running = [ad.days_running for ad in ads if ad.days_running is not None]
        if days_running:
            summary.avg_days_running = sum(days_running) / len(days_running)

        # New ads tracking
        summary.new_ads_last_7_days = sum(
            1
            for ad in ads
            if ad.started_running and ad.started_running >= week_ago
        )
        summary.new_ads_last_30_days = sum(
            1
            for ad in ads
            if ad.started_running and ad.started_running >= month_ago
        )

        return summary

    def generate_weekly_summary(
        self, ads: list[AdCreative], advertiser_summaries: list[AdvertiserSummary]
    ) -> WeeklySummary:
        """Generate a weekly summary for BI tools."""
        today = date.today()
        week_ago = today - timedelta(days=7)

        # Count new and stopped ads
        new_ads = [ad for ad in ads if ad.started_running and ad.started_running >= week_ago]
        stopped_ads = [
            ad
            for ad in ads
            if ad.ended_running and ad.ended_running >= week_ago
        ]

        # Aggregate statistics
        all_angles = Counter(ad.ad_angle.value for ad in ads if ad.ad_angle)
        all_hooks = Counter(ad.hook_style.value for ad in ads if ad.hook_style)
        all_offers = Counter(ad.offer_type.value for ad in ads if ad.offer_type)
        all_ctas = Counter(ad.cta_text for ad in ads if ad.cta_text)
        all_media = Counter(ad.media_type.value for ad in ads)

        return WeeklySummary(
            report_date=today,
            report_week=today.isocalendar()[1],
            total_advertisers_monitored=len(advertiser_summaries),
            total_ads_collected=len(ads),
            new_ads_this_week=len(new_ads),
            ads_stopped_this_week=len(stopped_ads),
            top_ad_angles=all_angles.most_common(5),
            top_hook_styles=all_hooks.most_common(5),
            top_offer_types=all_offers.most_common(5),
            top_ctas=all_ctas.most_common(10),
            media_type_trends=dict(all_media),
            advertiser_summaries=advertiser_summaries,
        )
