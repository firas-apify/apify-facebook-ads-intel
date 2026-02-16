"""Tests for ad classification and processing."""

from datetime import date, timedelta

import pytest

from src.models import AdAngle, AdCreative, HookStyle, MediaType, OfferType
from src.processors import AdClassifier, TrendAnalyzer


class TestAdClassifier:
    """Test cases for AdClassifier."""

    @pytest.fixture
    def classifier(self):
        return AdClassifier()

    def test_classify_problem_solution_angle(self, classifier):
        text = "Tired of struggling with messy cables? Say goodbye to tangled wires!"
        assert classifier.classify_ad_angle(text) == AdAngle.PROBLEM_SOLUTION

    def test_classify_testimonial_angle(self, classifier):
        text = "★★★★★ 5000+ customer reviews! See what people are saying about us."
        assert classifier.classify_ad_angle(text) == AdAngle.TESTIMONIAL

    def test_classify_urgency_angle(self, classifier):
        text = "Limited time offer! Only 5 left in stock. Don't miss out!"
        assert classifier.classify_ad_angle(text) == AdAngle.URGENCY

    def test_classify_discount_angle(self, classifier):
        text = "Save 50% off on all items! Biggest sale of the year."
        assert classifier.classify_ad_angle(text) == AdAngle.DISCOUNT

    def test_classify_question_hook(self, classifier):
        text = "Are you ready to transform your business?"
        assert classifier.classify_hook_style(text) == HookStyle.QUESTION

    def test_classify_statistic_hook(self, classifier):
        text = "87% of marketers say this changed their ROI"
        assert classifier.classify_hook_style(text) == HookStyle.STATISTIC

    def test_classify_pain_point_hook(self, classifier):
        text = "Tired of wasting money on ads that don't convert?"
        assert classifier.classify_hook_style(text) == HookStyle.PAIN_POINT

    def test_classify_percentage_off_offer(self, classifier):
        text = "Get 25% off your first order with code SAVE25"
        assert classifier.classify_offer_type(text) == OfferType.PERCENTAGE_OFF

    def test_classify_free_shipping_offer(self, classifier):
        text = "Free shipping on all orders over $50"
        assert classifier.classify_offer_type(text) == OfferType.FREE_SHIPPING

    def test_classify_free_trial_offer(self, classifier):
        text = "Start your 14-day free trial today"
        assert classifier.classify_offer_type(text) == OfferType.FREE_TRIAL

    def test_classify_no_offer(self, classifier):
        text = "Discover our new collection of premium products"
        assert classifier.classify_offer_type(text) == OfferType.NO_OFFER

    def test_classify_ad_calculates_days_running(self, classifier):
        ad = AdCreative(
            ad_id="123",
            advertiser_id="page_123",
            advertiser_name="Test Advertiser",
            ad_text="Tired of bad products? Try ours!",
            started_running=date.today() - timedelta(days=30),
            country_code="US",
        )
        classified = classifier.classify_ad(ad)
        assert classified.days_running == 30
        assert classified.ad_angle == AdAngle.PROBLEM_SOLUTION


class TestTrendAnalyzer:
    """Test cases for TrendAnalyzer."""

    @pytest.fixture
    def analyzer(self):
        return TrendAnalyzer()

    @pytest.fixture
    def sample_ads(self):
        return [
            AdCreative(
                ad_id="1",
                advertiser_id="page_1",
                advertiser_name="Test Brand",
                ad_text="50% off everything!",
                media_type=MediaType.IMAGE,
                ad_angle=AdAngle.DISCOUNT,
                hook_style=HookStyle.BENEFIT,
                offer_type=OfferType.PERCENTAGE_OFF,
                cta_text="Shop Now",
                is_active=True,
                started_running=date.today() - timedelta(days=5),
                country_code="US",
                days_running=5,
            ),
            AdCreative(
                ad_id="2",
                advertiser_id="page_1",
                advertiser_name="Test Brand",
                ad_text="Are you ready for the best deal?",
                media_type=MediaType.VIDEO,
                ad_angle=AdAngle.URGENCY,
                hook_style=HookStyle.QUESTION,
                offer_type=OfferType.LIMITED_TIME,
                cta_text="Learn More",
                is_active=True,
                started_running=date.today() - timedelta(days=10),
                country_code="US",
                days_running=10,
            ),
        ]

    def test_generate_advertiser_summary(self, analyzer, sample_ads):
        summary = analyzer.generate_advertiser_summary(
            advertiser_id="page_1",
            advertiser_name="Test Brand",
            ads=sample_ads,
        )

        assert summary.advertiser_id == "page_1"
        assert summary.total_ads == 2
        assert summary.active_ads == 2
        assert summary.media_type_breakdown == {"image": 1, "video": 1}
        assert summary.ad_angle_breakdown == {"discount": 1, "urgency": 1}
        assert summary.avg_days_running == 7.5
        assert summary.new_ads_last_7_days == 1

    def test_generate_weekly_summary(self, analyzer, sample_ads):
        advertiser_summaries = [
            analyzer.generate_advertiser_summary("page_1", "Test Brand", sample_ads)
        ]

        summary = analyzer.generate_weekly_summary(sample_ads, advertiser_summaries)

        assert summary.total_advertisers_monitored == 1
        assert summary.total_ads_collected == 2
        assert summary.new_ads_this_week == 1
