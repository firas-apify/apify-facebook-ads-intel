"""Facebook Ads Library scraper using Playwright."""

import asyncio
import re
from datetime import date, datetime
from typing import AsyncGenerator, Optional
from urllib.parse import urlencode, urlparse, parse_qs

from playwright.async_api import async_playwright, Browser, Page, TimeoutError as PlaywrightTimeout
from apify import Actor

from .models import ActorInput, AdCreative, AdStatus, MediaType


class FacebookAdsLibraryScraper:
    """Scrapes the Facebook Ads Library for ad creatives."""

    BASE_URL = "https://www.facebook.com/ads/library/"
    API_URL = "https://www.facebook.com/ads/library/async/search_ads/"

    def __init__(self, config: ActorInput):
        self.config = config
        self.browser: Optional[Browser] = None

    async def __aenter__(self):
        """Initialize browser on context entry."""
        playwright = await async_playwright().start()
        self.browser = await playwright.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
            ],
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Close browser on context exit."""
        if self.browser:
            await self.browser.close()

    def _build_search_url(
        self,
        advertiser_id: Optional[str] = None,
        search_term: Optional[str] = None,
    ) -> str:
        """Build the Facebook Ads Library search URL."""
        params = {
            "active_status": self.config.ad_status.value,
            "ad_type": "all",
            "country": self.config.country_code,
            "media_type": "all",
        }

        if advertiser_id:
            params["view_all_page_id"] = advertiser_id

        if search_term:
            params["q"] = search_term

        if self.config.start_date:
            params["start_date[min]"] = self.config.start_date.isoformat()

        if self.config.end_date:
            params["start_date[max]"] = self.config.end_date.isoformat()

        return f"{self.BASE_URL}?{urlencode(params)}"

    def _detect_media_type(self, ad_element_data: dict) -> MediaType:
        """Detect the media type from ad element data."""
        if ad_element_data.get("is_carousel"):
            return MediaType.CAROUSEL
        if ad_element_data.get("has_video"):
            return MediaType.VIDEO
        if ad_element_data.get("has_image"):
            return MediaType.IMAGE
        return MediaType.UNKNOWN

    def _parse_date(self, date_str: Optional[str]) -> Optional[date]:
        """Parse a date string from Facebook Ads Library."""
        if not date_str:
            return None

        # Try common formats
        formats = [
            "%b %d, %Y",  # Dec 25, 2024
            "%B %d, %Y",  # December 25, 2024
            "%Y-%m-%d",  # 2024-12-25
            "%m/%d/%Y",  # 12/25/2024
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue

        return None

    def _parse_impressions(self, text: str) -> tuple[Optional[int], Optional[int]]:
        """Parse impression ranges from text like '1K-5K' or '10K-50K'."""
        if not text:
            return None, None

        def parse_number(s: str) -> int:
            s = s.strip().upper().replace(",", "")
            multipliers = {"K": 1000, "M": 1000000, "B": 1000000000}
            for suffix, mult in multipliers.items():
                if s.endswith(suffix):
                    return int(float(s[:-1]) * mult)
            return int(s) if s.isdigit() else 0

        match = re.search(r"(\d+[KMB]?)\s*[-–]\s*(\d+[KMB]?)", text, re.IGNORECASE)
        if match:
            return parse_number(match.group(1)), parse_number(match.group(2))

        return None, None

    async def _extract_ad_from_element(
        self,
        page: Page,
        ad_container: dict,
        advertiser_id: str,
        advertiser_name: str,
    ) -> Optional[AdCreative]:
        """Extract ad data from a page element."""
        try:
            ad_id = ad_container.get("ad_id", "")
            if not ad_id:
                return None

            # Extract text content
            ad_text = ad_container.get("body_text", "")
            headline = ad_container.get("headline", "")
            description = ad_container.get("description", "")

            # Extract CTA
            cta_text = ad_container.get("cta_text", "")
            cta_link = ad_container.get("cta_link", "")

            # Extract landing page
            landing_page_url = ad_container.get("landing_page", "")
            if not landing_page_url and cta_link:
                landing_page_url = cta_link

            # Extract media
            media_urls = ad_container.get("media_urls", [])
            media_type = self._detect_media_type(ad_container)

            # Extract dates
            started_running = self._parse_date(ad_container.get("start_date"))
            ended_running = self._parse_date(ad_container.get("end_date"))
            is_active = not ended_running

            # Extract platforms
            platforms = ad_container.get("platforms", [])

            # Extract impressions/spend (if available for political ads)
            impressions_lower, impressions_upper = self._parse_impressions(
                ad_container.get("impressions", "")
            )
            spend_lower, spend_upper = self._parse_impressions(
                ad_container.get("spend", "")
            )

            return AdCreative(
                ad_id=ad_id,
                advertiser_id=advertiser_id,
                advertiser_name=advertiser_name,
                ad_text=ad_text or None,
                headline=headline or None,
                description=description or None,
                cta_text=cta_text or None,
                cta_link=cta_link or None,
                landing_page_url=landing_page_url or None,
                media_type=media_type,
                media_urls=media_urls if self.config.include_media_urls else [],
                is_active=is_active,
                started_running=started_running,
                ended_running=ended_running,
                platforms=platforms,
                impressions_lower=impressions_lower,
                impressions_upper=impressions_upper,
                spend_lower=spend_lower,
                spend_upper=spend_upper,
                country_code=self.config.country_code,
            )
        except Exception as e:
            Actor.log.warning(f"Failed to extract ad: {e}")
            return None

    async def _scrape_page(
        self,
        page: Page,
        url: str,
        advertiser_id: str,
        advertiser_name: str,
    ) -> AsyncGenerator[AdCreative, None]:
        """Scrape ads from a single page URL."""
        try:
            await page.goto(url, wait_until="networkidle", timeout=60000)
            await asyncio.sleep(2)  # Allow dynamic content to load

            # Wait for ad containers to appear
            await page.wait_for_selector(
                '[class*="ad-card"], [data-testid="ad_card"], div[class*="_7jyr"]',
                timeout=30000,
            )

            ads_collected = 0
            last_height = 0
            no_new_content_count = 0

            while ads_collected < self.config.max_ads_per_advertiser:
                # Extract visible ads
                ad_elements = await page.evaluate("""
                    () => {
                        const ads = [];
                        const containers = document.querySelectorAll(
                            '[class*="ad-card"], [data-testid="ad_card"], div[class*="_7jyr"]'
                        );

                        containers.forEach((container, index) => {
                            try {
                                const adData = {
                                    ad_id: container.getAttribute('data-ad-id') ||
                                           container.id ||
                                           `ad_${Date.now()}_${index}`,
                                    body_text: '',
                                    headline: '',
                                    description: '',
                                    cta_text: '',
                                    cta_link: '',
                                    landing_page: '',
                                    media_urls: [],
                                    start_date: '',
                                    end_date: '',
                                    platforms: [],
                                    has_video: false,
                                    has_image: false,
                                    is_carousel: false,
                                };

                                // Extract body text
                                const bodyEl = container.querySelector(
                                    '[class*="body"], [class*="_4ik4"], [class*="ad-body"]'
                                );
                                if (bodyEl) adData.body_text = bodyEl.innerText?.trim() || '';

                                // Extract headline
                                const headlineEl = container.querySelector(
                                    'h3, [class*="headline"], [class*="_4ik5"]'
                                );
                                if (headlineEl) adData.headline = headlineEl.innerText?.trim() || '';

                                // Extract CTA
                                const ctaEl = container.querySelector(
                                    'a[class*="cta"], button[class*="cta"], [class*="_4ik7"]'
                                );
                                if (ctaEl) {
                                    adData.cta_text = ctaEl.innerText?.trim() || '';
                                    adData.cta_link = ctaEl.href || '';
                                }

                                // Extract dates
                                const dateEl = container.querySelector(
                                    '[class*="date"], [class*="_7jys"]'
                                );
                                if (dateEl) {
                                    const dateText = dateEl.innerText || '';
                                    const dateMatch = dateText.match(/Started running on (.+)/);
                                    if (dateMatch) adData.start_date = dateMatch[1];
                                }

                                // Check for media
                                const video = container.querySelector('video');
                                const images = container.querySelectorAll('img[src*="scontent"]');
                                const carousel = container.querySelector('[class*="carousel"]');

                                adData.has_video = !!video;
                                adData.has_image = images.length > 0;
                                adData.is_carousel = !!carousel || images.length > 1;

                                // Extract media URLs
                                if (video) {
                                    const src = video.getAttribute('src');
                                    if (src) adData.media_urls.push(src);
                                }
                                images.forEach(img => {
                                    const src = img.getAttribute('src');
                                    if (src && !src.includes('emoji')) {
                                        adData.media_urls.push(src);
                                    }
                                });

                                // Extract platforms
                                const platformEl = container.querySelector(
                                    '[class*="platform"], [class*="_7jyt"]'
                                );
                                if (platformEl) {
                                    const platformText = platformEl.innerText || '';
                                    if (platformText.includes('Facebook')) adData.platforms.push('Facebook');
                                    if (platformText.includes('Instagram')) adData.platforms.push('Instagram');
                                    if (platformText.includes('Messenger')) adData.platforms.push('Messenger');
                                    if (platformText.includes('Audience Network')) {
                                        adData.platforms.push('Audience Network');
                                    }
                                }

                                ads.push(adData);
                            } catch (e) {
                                console.error('Error extracting ad:', e);
                            }
                        });

                        return ads;
                    }
                """)

                for ad_data in ad_elements[ads_collected:]:
                    ad = await self._extract_ad_from_element(
                        page, ad_data, advertiser_id, advertiser_name
                    )
                    if ad:
                        yield ad
                        ads_collected += 1

                    if ads_collected >= self.config.max_ads_per_advertiser:
                        break

                # Scroll for more content
                current_height = await page.evaluate("document.body.scrollHeight")
                if current_height == last_height:
                    no_new_content_count += 1
                    if no_new_content_count >= 3:
                        break  # No more content to load
                else:
                    no_new_content_count = 0

                last_height = current_height
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(2)

        except PlaywrightTimeout:
            Actor.log.warning(f"Timeout while scraping {url}")
        except Exception as e:
            Actor.log.error(f"Error scraping {url}: {e}")

    async def _get_advertiser_name(self, page: Page, advertiser_id: str) -> str:
        """Get the advertiser name from the page."""
        try:
            name_element = await page.query_selector(
                '[class*="page-name"], [class*="_7jyq"], h1'
            )
            if name_element:
                return await name_element.inner_text()
        except Exception:
            pass
        return f"Advertiser {advertiser_id}"

    async def scrape_advertiser(
        self, advertiser_id: str
    ) -> AsyncGenerator[AdCreative, None]:
        """Scrape all ads for a specific advertiser."""
        if not self.browser:
            raise RuntimeError("Browser not initialized. Use async context manager.")

        context = await self.browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        page = await context.new_page()

        try:
            url = self._build_search_url(advertiser_id=advertiser_id)
            await page.goto(url, wait_until="networkidle", timeout=60000)

            advertiser_name = await self._get_advertiser_name(page, advertiser_id)
            Actor.log.info(f"Scraping ads for: {advertiser_name}")

            async for ad in self._scrape_page(page, url, advertiser_id, advertiser_name):
                yield ad

        finally:
            await context.close()

    async def scrape_search_term(
        self, search_term: str
    ) -> AsyncGenerator[AdCreative, None]:
        """Scrape ads matching a search term."""
        if not self.browser:
            raise RuntimeError("Browser not initialized. Use async context manager.")

        context = await self.browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        page = await context.new_page()

        try:
            url = self._build_search_url(search_term=search_term)
            await page.goto(url, wait_until="networkidle", timeout=60000)

            Actor.log.info(f"Scraping ads for search term: {search_term}")

            async for ad in self._scrape_page(page, url, "", f"Search: {search_term}"):
                yield ad

        finally:
            await context.close()

    async def scrape_all(self) -> AsyncGenerator[AdCreative, None]:
        """Scrape ads from all configured sources."""
        # Scrape by advertiser IDs
        for advertiser_id in self.config.advertiser_ids:
            Actor.log.info(f"Processing advertiser: {advertiser_id}")
            async for ad in self.scrape_advertiser(advertiser_id):
                yield ad

        # Scrape by search terms
        for search_term in self.config.search_terms:
            Actor.log.info(f"Processing search term: {search_term}")
            async for ad in self.scrape_search_term(search_term):
                yield ad
