"""
News Search Service — Google News RSS + Tamil Nadu News Sources

Provides a dedicated news search channel for the fact-checking pipeline.
Uses Google News RSS (free, no API key needed) to search for news articles
that match a claim, with special support for Tamil Nadu news sources.

This service acts as a FALLBACK when Perplexity fails to find relevant results,
ensuring that news articles (which may not be indexed by Perplexity) are still
discovered and used as evidence.
"""

import requests
import re
import xml.etree.ElementTree as ET
from urllib.parse import quote_plus, urlparse
from typing import List, Dict, Optional
from datetime import datetime


class NewsSearchService:
    """
    Searches Google News RSS and Tamil Nadu news portals for articles
    matching a claim. Used as a fallback when Perplexity returns no results.
    """

    def __init__(self):
        self.google_news_rss_url = "https://news.google.com/rss/search"
        self.timeout = 15

        # Tamil Nadu news domains — articles from these are credible evidence
        self.tn_news_domains = {
            # Tamil newspapers (online)
            "dinamalar.com", "dailythanthi.com", "dinamani.com",
            "maalaimalar.com", "vikatan.com", "nakkheeran.in",
            "tamil.thehindu.com", "tamilmurasu.com.sg",
            # Tamil TV news (online portals)
            "puthiyathalaimurai.com", "thanthitv.com",
            "polimernews.com", "news7tamil.live",
            "sunnews.in",
            # English dailies with TN focus
            "dtnext.in", "newindianexpress.com", "thehindu.com",
            "deccanchronicle.com", "deccanherald.com",
            # Online portals
            "tamil.oneindia.com", "tamil.samayam.com",
            "newsglitz.com", "tamilguardian.com",
            # National media (also covers TN)
            "ndtv.com", "indiatoday.in", "timesofindia.indiatimes.com",
            "hindustantimes.com", "news18.com",
            "thequint.com", "scroll.in", "theprint.in",
            "livemint.com", "business-standard.com",
            "thehindubusinessline.com", "financialexpress.com",
            # Wire services
            "pti.in", "ani.in",
            # Government press releases
            "pib.gov.in",
        }

        # Credibility tiers
        self.tier1_domains = {
            "thehindu.com", "tamil.thehindu.com", "ndtv.com",
            "indiatoday.in", "newindianexpress.com", "pib.gov.in",
            "timesofindia.indiatimes.com", "hindustantimes.com",
            "thehindubusinessline.com", "financialexpress.com",
            "reuters.com", "apnews.com",
        }
        self.tier2_domains = {
            "dinamalar.com", "dailythanthi.com", "dinamani.com",
            "maalaimalar.com", "vikatan.com", "dtnext.in",
            "puthiyathalaimurai.com", "news7tamil.live",
            "polimernews.com", "news18.com",
            "thequint.com", "scroll.in", "theprint.in",
            "livemint.com", "business-standard.com",
            "deccanchronicle.com", "deccanherald.com",
        }

    def search_news(self, query: str, structured_claim: dict = None) -> dict:
        """
        Search Google News RSS for articles matching the query.

        Args:
            query: Search query string
            structured_claim: Optional structured claim for context

        Returns:
            dict: {
                "articles_found": int,
                "articles": [{"title", "source", "url", "domain", "date", "snippet", "credibility_tier"}],
                "tn_articles_found": int,
                "summary": str,
                "has_credible_evidence": bool
            }
        """
        articles = []

        # Search 1: English query on Google News
        try:
            english_articles = self._search_google_news_rss(query)
            articles.extend(english_articles)
        except Exception as e:
            print(f"[NewsSearch] Google News RSS error: {e}")

        # Search 2: If claim involves Tamil Nadu, add TN-specific search
        if structured_claim:
            location = structured_claim.get("location", "").lower()
            is_tn = any(term in location for term in [
                "tamil nadu", "chennai", "coimbatore", "madurai", "trichy",
                "salem", "tirunelveli", "erode", "vellore", "thanjavur",
            ])
            if is_tn and "tamil nadu" not in query.lower():
                try:
                    tn_articles = self._search_google_news_rss(f"{query} Tamil Nadu")
                    articles.extend(tn_articles)
                except Exception as e:
                    print(f"[NewsSearch] TN-specific search error: {e}")
                    
            # Search 3: Recent news (last 7 days) for breaking political/event news
            try:
                recency_query = f"{query} Tamil Nadu when:7d" if is_tn else f"{query} when:7d"
                recent_articles = self._search_google_news_rss(recency_query)
                articles.extend(recent_articles)
            except Exception as e:
                print(f"[NewsSearch] Recency search error: {e}")

        # Deduplicate by URL
        seen_urls = set()
        unique_articles = []
        for article in articles:
            url = article.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique_articles.append(article)

        # Count Tamil Nadu specific articles
        tn_count = sum(1 for a in unique_articles
                       if a.get("domain", "") in self.tn_news_domains)

        # Determine if we have credible evidence
        has_credible = any(
            a.get("credibility_tier") in ("tier1", "tier2")
            for a in unique_articles
        )

        # Build summary
        summary = self._build_summary(unique_articles, tn_count)

        return {
            "articles_found": len(unique_articles),
            "articles": unique_articles[:10],  # Top 10 articles
            "tn_articles_found": tn_count,
            "summary": summary,
            "has_credible_evidence": has_credible,
        }

    def _search_google_news_rss(self, query: str) -> List[dict]:
        """
        Search Google News via RSS feed (free, no API key needed).

        Args:
            query: Search query

        Returns:
            List of article dicts
        """
        encoded_query = quote_plus(query)
        url = f"{self.google_news_rss_url}?q={encoded_query}&hl=en-IN&gl=IN&ceid=IN:en"

        print(f"[NewsSearch] Searching Google News RSS: {query[:60]}...")

        response = requests.get(url, timeout=self.timeout, headers={
            "User-Agent": "Mozilla/5.0 (compatible; FactChecker/1.0)"
        })

        if response.status_code != 200:
            print(f"[NewsSearch] Google News RSS error: {response.status_code}")
            return []

        # Parse RSS XML
        articles = []
        try:
            root = ET.fromstring(response.content)
            channel = root.find("channel")
            if channel is None:
                return []

            items = channel.findall("item")
            print(f"[NewsSearch] Found {len(items)} articles from Google News")

            for item in items[:15]:  # Process top 15 items
                title = item.findtext("title", "")
                link = item.findtext("link", "")
                pub_date = item.findtext("pubDate", "")
                description = item.findtext("description", "")
                source_elem = item.find("source")
                source_name = source_elem.text if source_elem is not None else ""
                source_url = source_elem.get("url", "") if source_elem is not None else ""

                # Extract domain
                domain = ""
                try:
                    if source_url:
                        domain = urlparse(source_url).netloc.lower().replace("www.", "")
                    elif link:
                        domain = urlparse(link).netloc.lower().replace("www.", "")
                except:
                    pass

                # Determine credibility tier
                credibility_tier = self._get_credibility_tier(domain)

                # Clean description (remove HTML tags)
                clean_description = re.sub(r'<[^>]+>', '', description).strip()

                # Parse date
                date_short = self._parse_rss_date(pub_date)

                articles.append({
                    "title": title,
                    "source": source_name or domain,
                    "url": link,
                    "domain": domain,
                    "date": date_short,
                    "snippet": clean_description[:300] if clean_description else "",
                    "credibility_tier": credibility_tier,
                })

        except ET.ParseError as e:
            print(f"[NewsSearch] XML parse error: {e}")

        return articles

    def _get_credibility_tier(self, domain: str) -> str:
        """Determine credibility tier of a news domain."""
        if not domain:
            return "unknown"

        if domain in self.tier1_domains:
            return "tier1"

        if domain in self.tier2_domains:
            return "tier2"

        # Check for partial matches (subdomains)
        for d in self.tier1_domains:
            if d in domain:
                return "tier1"
        for d in self.tier2_domains:
            if d in domain:
                return "tier2"

        # Check for government domains
        if domain.endswith(".gov.in") or domain.endswith(".gov"):
            return "tier1"

        return "unknown"

    def _parse_rss_date(self, date_str: str) -> str:
        """Parse RSS date format to YYYY-MM-DD."""
        if not date_str:
            return ""
        try:
            # RSS format: "Thu, 05 Mar 2026 10:30:00 GMT"
            dt = datetime.strptime(date_str.strip(), "%a, %d %b %Y %H:%M:%S %Z")
            return dt.strftime("%Y-%m-%d")
        except:
            try:
                # Try ISO format
                return date_str[:10]
            except:
                return date_str

    def _build_summary(self, articles: List[dict], tn_count: int) -> str:
        """Build a human-readable summary of search results."""
        if not articles:
            return "No news articles found for this claim."

        total = len(articles)
        tier1_count = sum(1 for a in articles if a.get("credibility_tier") == "tier1")
        tier2_count = sum(1 for a in articles if a.get("credibility_tier") == "tier2")

        parts = [f"Found {total} news article(s)."]
        if tier1_count > 0:
            parts.append(f"{tier1_count} from top-tier sources (The Hindu, NDTV, TNIE, TOI, etc.).")
        if tier2_count > 0:
            parts.append(f"{tier2_count} from credible regional/Tamil sources (Dinamalar, Dinathanthi, Vikatan, etc.).")
        if tn_count > 0:
            parts.append(f"{tn_count} specifically from Tamil Nadu news outlets.")

        return " ".join(parts)

    def format_for_verdict(self, news_results: dict) -> str:
        """
        Format news search results as context for the verdict prompt.

        Args:
            news_results: Results from search_news()

        Returns:
            str: Formatted text block for the verdict prompt
        """
        if not news_results or news_results.get("articles_found", 0) == 0:
            return ""

        articles = news_results.get("articles", [])
        if not articles:
            return ""

        lines = [
            "",
            "===============================================================================",
            "NEWS ARTICLE EVIDENCE (Google News Search — independent of Perplexity)",
            "===============================================================================",
            f"Total articles found: {news_results.get('articles_found', 0)}",
            f"Tamil Nadu specific: {news_results.get('tn_articles_found', 0)}",
            "",
        ]

        for i, article in enumerate(articles[:8], 1):
            tier_label = {
                "tier1": "TOP-TIER",
                "tier2": "CREDIBLE",
                "unknown": "OTHER"
            }.get(article.get("credibility_tier", "unknown"), "OTHER")

            lines.append(f"{i}. [{tier_label}] {article.get('title', 'Untitled')}")
            lines.append(f"   Source: {article.get('source', 'Unknown')} ({article.get('date', 'N/A')})")
            if article.get("snippet"):
                lines.append(f"   Preview: {article['snippet'][:150]}...")
            lines.append("")

        lines.append("IMPORTANT: If credible news articles confirm the claim above,")
        lines.append("this IS sufficient evidence for a TRUE verdict — do NOT require")
        lines.append("a government gazette when news outlets have already reported the story.")

        return "\n".join(lines)
