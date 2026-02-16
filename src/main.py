"""Main entry point for the Facebook Ads Creative Intelligence actor."""

import asyncio
from collections import defaultdict

from apify import Actor

from .models import ActorInput, AdCreative
from .processors import AdClassifier, TrendAnalyzer
from .scraper import FacebookAdsLibraryScraper


async def main() -> None:
    """Main actor function."""
    async with Actor:
        # Get and validate input
        actor_input = await Actor.get_input() or {}
        config = ActorInput(**actor_input)

        Actor.log.info(f"Starting Facebook Ads Intelligence scraper")
        Actor.log.info(f"Advertisers to monitor: {len(config.advertiser_ids)}")
        Actor.log.info(f"Search terms: {len(config.search_terms)}")
        Actor.log.info(f"Country: {config.country_code}")
        Actor.log.info(f"Ad status filter: {config.ad_status.value}")

        if not config.advertiser_ids and not config.search_terms:
            Actor.log.warning(
                "No advertiser IDs or search terms provided. "
                "Please provide at least one to scrape."
            )
            return

        # Initialize processors
        classifier = AdClassifier()
        analyzer = TrendAnalyzer()

        # Collect all ads
        all_ads: list[AdCreative] = []
        ads_by_advertiser: dict[str, list[AdCreative]] = defaultdict(list)

        async with FacebookAdsLibraryScraper(config) as scraper:
            async for ad in scraper.scrape_all():
                # Classify ad if enabled
                if config.classify_ads:
                    ad = classifier.classify_ad(ad)

                # Store ad
                all_ads.append(ad)
                ads_by_advertiser[ad.advertiser_id].append(ad)

                # Push to dataset
                await Actor.push_data(ad.model_dump(mode="json"))

                Actor.log.info(
                    f"Collected ad {ad.ad_id} from {ad.advertiser_name} "
                    f"(angle: {ad.ad_angle}, hook: {ad.hook_style})"
                )

        Actor.log.info(f"Total ads collected: {len(all_ads)}")

        # Generate advertiser summaries
        advertiser_summaries = []
        for advertiser_id, ads in ads_by_advertiser.items():
            if ads:
                summary = analyzer.generate_advertiser_summary(
                    advertiser_id=advertiser_id,
                    advertiser_name=ads[0].advertiser_name,
                    ads=ads,
                )
                advertiser_summaries.append(summary)

        # Generate weekly summary
        if all_ads:
            weekly_summary = analyzer.generate_weekly_summary(all_ads, advertiser_summaries)

            # Store summary in key-value store for BI tools
            default_store = await Actor.open_key_value_store()
            await default_store.set_value(
                "weekly_summary",
                weekly_summary.model_dump(mode="json"),
            )

            # Also store individual advertiser summaries
            for summary in advertiser_summaries:
                await default_store.set_value(
                    f"advertiser_{summary.advertiser_id}",
                    summary.model_dump(mode="json"),
                )

            Actor.log.info(
                f"Generated weekly summary: {weekly_summary.total_ads_collected} ads, "
                f"{weekly_summary.new_ads_this_week} new this week"
            )

        Actor.log.info("Facebook Ads Intelligence scraper completed successfully")


if __name__ == "__main__":
    asyncio.run(main())
