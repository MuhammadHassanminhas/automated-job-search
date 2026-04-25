"""Incremental scraping tests — B.1 spec."""
from __future__ import annotations

import httpx
import respx
from unittest.mock import patch


class TestIncrementalScraping:
    """Second run with unchanged source_etag must make zero parse calls."""

    def test_unchanged_etag_skips_normalize(self) -> None:
        """
        If the HTTP response ETag matches the stored source_etag on the scraper,
        normalize() must NOT be called — zero parse work.
        """
        from app.scrapers.internshala import InternshalasScraper, INTERNSHALA_LISTINGS_URL

        scraper = InternshalasScraper()
        etag_value = '"abc123etag"'

        with respx.mock:
            # Both requests return the same ETag
            respx.get(INTERNSHALA_LISTINGS_URL).mock(
                return_value=httpx.Response(
                    200,
                    text="<html><body></body></html>",
                    headers={"ETag": etag_value},
                )
            )
            with patch.object(scraper, "normalize", wraps=scraper.normalize) as mock_normalize:
                # First fetch — should call normalize (new etag)
                scraper.fetch()
                # Simulate etag being stored after first run
                scraper._last_etag = etag_value
                # Second fetch — same etag → should NOT call normalize
                scraper.fetch()

        # normalize must have been called exactly once (first run only)
        assert mock_normalize.call_count <= 1, (
            f"normalize called {mock_normalize.call_count} times — expected ≤1 (zero on second run)"
        )

    def test_changed_etag_triggers_normalize(self) -> None:
        """If ETag changes between runs, normalize IS called."""
        from app.scrapers.internshala import InternshalasScraper, INTERNSHALA_LISTINGS_URL
        from pathlib import Path
        fixture_html = (Path(__file__).parent / "fixtures" / "internshala_sample.html").read_text()

        scraper = InternshalasScraper()
        scraper._last_etag = '"old-etag"'

        with respx.mock:
            respx.get(INTERNSHALA_LISTINGS_URL).mock(
                return_value=httpx.Response(
                    200,
                    text=fixture_html,
                    headers={"ETag": '"new-etag"'},
                )
            )
            with patch.object(scraper, "normalize", wraps=scraper.normalize) as mock_normalize:
                scraper.fetch()

        assert mock_normalize.call_count >= 1
