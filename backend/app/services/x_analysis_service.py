"""
X (Twitter) Analysis Service

Analyzes X/Twitter for external source links related to a claim.
This service is used to surface additional context from social media discussions,
specifically focusing on extracting external links to credible sources.

CRITICAL RULES:
- X is NEVER a source of truth
- Only extracts external links (news articles, government portals, official sources)
- Ignores engagement metrics (likes, retweets, replies)
- Returns structured data for Gemini to evaluate as supplementary context
"""

from app.core.config import X_BEARER_TOKEN, X_ANALYSIS_ENABLED, X_SEARCH_LIMIT
import requests
import re
from urllib.parse import urlparse
from typing import List, Dict, Optional


class XAnalysisService:
    """
    Analyzes X (Twitter) for external source links related to a claim.

    This service searches X for posts discussing a claim and extracts
    external links that may provide additional verification sources.
    X itself is never treated as a source of truth.
    """

    def __init__(self):
        self.enabled = X_ANALYSIS_ENABLED
        self.bearer_token = X_BEARER_TOKEN
        self.search_limit = X_SEARCH_LIMIT
        self.base_url = "https://api.twitter.com/2"

        # Credibility tiers for linked domains
        self.primary_sources = {
            # International news agencies
            "reuters.com", "apnews.com", "afp.com",
            # Major broadcasters
            "bbc.com", "bbc.co.uk", "npr.org", "pbs.org",
            # Government and official sources
            "gov", "gov.uk", "gov.in", "europa.eu", "un.org", "who.int",
            # Academic and research
            "edu", "ac.uk", "nature.com", "sciencedirect.com", "pubmed.ncbi.nlm.nih.gov",
        }

        self.secondary_sources = {
            # Major newspapers
            "nytimes.com", "washingtonpost.com", "theguardian.com", "wsj.com",
            "economist.com", "ft.com", "thehindu.com", "indianexpress.com",
            "timesofindia.indiatimes.com", "hindustantimes.com",
            # News networks
            "cnn.com", "nbcnews.com", "abcnews.go.com", "cbsnews.com",
            "ndtv.com", "indiatoday.in",
            # Wire services
            "pti.in", "ani.in",
            # Fact-checkers
            "snopes.com", "factcheck.org", "politifact.com", "altnews.in",
            # Regional Indian news — Tamil Nadu
            "dinamalar.com", "dailythanthi.com", "dinamani.com", "maalaimalar.com",
            "vikatan.com", "news7tamil.live", "puthiyathalaimurai.com",
            "polimernews.com", "dtnext.in",
            # Regional Indian news — other states & national
            "news18.com", "aajtak.in", "dainikbhaskar.com",
            "eenadu.net", "mathrubhumi.com", "manoramaonline.com",
            "deccanherald.com", "deccanchronicle.com",
            "newindianexpress.com", "oneindia.com",
            "thequint.com", "scroll.in", "theprint.in",
            "livemint.com", "business-standard.com",
        }

        if not self.bearer_token and self.enabled:
            print("WARNING: X_BEARER_TOKEN not set. X analysis will use fallback mode.")

    def analyze_claim(self, structured_claim: dict, search_query: str) -> dict:
        """
        Analyze X for posts discussing the claim that contain external links.

        Args:
            structured_claim (dict): Structured claim data with entities, time_period, etc.
            search_query (str): Optimized search query from claim structuring

        Returns:
            dict: Analysis results with external sources and discussion summary
        """
        if not self.enabled:
            return self._disabled_response()

        if not self.bearer_token:
            return self._fallback_analysis(structured_claim, search_query)

        try:
            # Build search query optimized for X
            x_query = self._build_x_search_query(structured_claim, search_query)

            # Search X for recent posts with links
            posts = self._search_posts_with_links(x_query)

            if not posts:
                return self._no_results_response(x_query)

            # Extract and categorize external URLs
            external_sources = self._extract_external_sources(posts)

            # Generate neutral discussion summary
            discussion_summary = self._summarize_discussion(posts, structured_claim)

            # Generate analysis note
            analysis_note = self._generate_analysis_note(external_sources)

            return {
                "has_relevant_posts": True,
                "posts_analyzed": len(posts),
                "external_sources": external_sources,
                "discussion_summary": discussion_summary,
                "analysis_note": analysis_note,
                "search_query_used": x_query
            }

        except requests.exceptions.Timeout:
            print("[X Analysis] API timeout")
            return self._error_response("X API request timed out")
        except requests.exceptions.RequestException as e:
            print(f"[X Analysis] Request error: {str(e)}")
            return self._error_response(f"X API request failed: {str(e)}")
        except Exception as e:
            print(f"[X Analysis] Error: {str(e)}")
            return self._error_response(f"X analysis error: {str(e)}")

    def _build_x_search_query(self, structured_claim: dict, search_query: str) -> str:
        """
        Build an optimized search query for X API.
        Uses top 2 entities for focus and does NOT restrict language,
        since local Indian events are often discussed in regional languages.

        Args:
            structured_claim (dict): Structured claim data
            search_query (str): Base search query

        Returns:
            str: Optimized X search query
        """
        # Extract key entities for focused search
        entities = structured_claim.get("entities", [])
        claim = structured_claim.get("claim", search_query)
        original_input = structured_claim.get("original_input", "")
        geographic_scope = structured_claim.get("geographic_scope", "national")

        # Build query components
        query_parts = []

        # Add main entities (limit to top 2 for broader matching)
        if entities:
            entity_query = " ".join(entities[:2])
            query_parts.append(entity_query)
        else:
            # Use first 4 significant words from claim
            words = [w for w in claim.split() if len(w) > 3][:4]
            query_parts.append(" ".join(words))

        # Combine and add filter for posts with links
        base_query = " ".join(query_parts)

        # For local/district claims with regional language input,
        # extract key regional language terms for better X matching
        if geographic_scope in ("local", "district") and original_input:
            is_regional = any(ord(c) > 127 for c in original_input.replace(' ', ''))
            if is_regional:
                # Extract first few significant words from original language input
                original_words = [w for w in original_input.split() if len(w) > 2][:3]
                if original_words:
                    regional_terms = " ".join(original_words)
                    # Use regional terms as primary query (people tweet in their language)
                    base_query = regional_terms

        # X API search operators:
        # - has:links filters for posts with URLs
        # - -is:retweet excludes retweets
        # - Do NOT add lang:en — local events are discussed in regional languages
        x_query = f"{base_query} has:links -is:retweet"

        # Limit query length for API
        if len(x_query) > 500:
            x_query = x_query[:500]

        return x_query

    def _search_posts_with_links(self, query: str) -> List[dict]:
        """
        Search X API for posts matching the query that contain links.

        Args:
            query (str): Search query

        Returns:
            List[dict]: List of post data
        """
        headers = {
            "Authorization": f"Bearer {self.bearer_token}",
            "Content-Type": "application/json"
        }

        params = {
            "query": query,
            "max_results": min(self.search_limit, 100),  # X API max is 100
            "tweet.fields": "entities,created_at,public_metrics,author_id",
            "expansions": "author_id",
            "user.fields": "verified,verified_type"
        }

        print(f"[X Analysis] Searching for: {query[:80]}...")

        response = requests.get(
            f"{self.base_url}/tweets/search/recent",
            headers=headers,
            params=params,
            timeout=15
        )

        print(f"[X Analysis] Response status: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            tweets = data.get("data", [])
            print(f"[X Analysis] Found {len(tweets)} posts with links")
            return tweets
        elif response.status_code == 401:
            print("[X Analysis] Authentication failed - check bearer token")
            return []
        elif response.status_code == 429:
            print("[X Analysis] Rate limited")
            return []
        else:
            print(f"[X Analysis] API error: {response.status_code}")
            return []

    def _extract_external_sources(self, posts: List[dict]) -> List[dict]:
        """
        Extract and categorize external URLs from posts.

        Args:
            posts (List[dict]): List of post data

        Returns:
            List[dict]: List of external source data
        """
        external_sources = []
        seen_domains = set()

        for post in posts:
            entities = post.get("entities", {})
            urls = entities.get("urls", [])

            for url_entity in urls:
                expanded_url = url_entity.get("expanded_url", "")

                # Skip X/Twitter internal links
                if not expanded_url or "twitter.com" in expanded_url or "x.com" in expanded_url:
                    continue

                # Skip URL shorteners without resolution
                if any(shortener in expanded_url for shortener in ["bit.ly", "t.co", "tinyurl"]):
                    # Use unwound_url if available
                    expanded_url = url_entity.get("unwound_url", expanded_url)

                # Parse domain
                try:
                    parsed = urlparse(expanded_url)
                    domain = parsed.netloc.lower().replace("www.", "")
                except:
                    continue

                # Skip duplicates from same domain
                if domain in seen_domains:
                    continue
                seen_domains.add(domain)

                # Determine credibility tier
                credibility_tier = self._get_credibility_tier(domain)

                # Extract title/context if available
                title = url_entity.get("title", "")
                description = url_entity.get("description", "")

                external_sources.append({
                    "url": expanded_url,
                    "domain": domain,
                    "title": title,
                    "description": description[:200] if description else "",
                    "credibility_tier": credibility_tier
                })

        # Sort by credibility tier (primary first)
        tier_order = {"primary": 0, "secondary": 1, "unknown": 2}
        external_sources.sort(key=lambda x: tier_order.get(x["credibility_tier"], 2))

        # Limit to top sources
        return external_sources[:10]

    def _get_credibility_tier(self, domain: str) -> str:
        """
        Determine the credibility tier of a domain.

        Args:
            domain (str): Domain name

        Returns:
            str: Credibility tier (primary, secondary, unknown)
        """
        # Check for exact match in primary sources
        if domain in self.primary_sources:
            return "primary"

        # Check for TLD-based primary sources (gov, edu)
        for suffix in [".gov", ".edu", ".ac.uk", ".gov.uk", ".gov.in"]:
            if domain.endswith(suffix):
                return "primary"

        # Check for exact match in secondary sources
        if domain in self.secondary_sources:
            return "secondary"

        # Check if domain contains any secondary source
        for source in self.secondary_sources:
            if source in domain:
                return "secondary"

        return "unknown"

    def _summarize_discussion(self, posts: List[dict], structured_claim: dict) -> str:
        """
        Generate a neutral summary of the X discussion.
        Does NOT include opinions or sentiment - only factual observation.

        Args:
            posts (List[dict]): List of posts
            structured_claim (dict): Structured claim data

        Returns:
            str: Neutral discussion summary
        """
        if not posts:
            return "No relevant discussion found on X."

        claim = structured_claim.get("claim", "this topic")
        num_posts = len(posts)

        # Count posts with credible external links
        credible_link_count = 0
        for post in posts:
            entities = post.get("entities", {})
            urls = entities.get("urls", [])
            for url_entity in urls:
                expanded_url = url_entity.get("expanded_url", "")
                if expanded_url:
                    try:
                        parsed = urlparse(expanded_url)
                        domain = parsed.netloc.lower().replace("www.", "")
                        if self._get_credibility_tier(domain) in ["primary", "secondary"]:
                            credible_link_count += 1
                            break
                    except:
                        pass

        summary = f"Found {num_posts} posts on X discussing this topic. "

        if credible_link_count > 0:
            summary += f"{credible_link_count} posts included links to credible news sources or official websites."
        else:
            summary += "No posts contained links to credible news sources."

        return summary

    def _generate_analysis_note(self, external_sources: List[dict]) -> str:
        """
        Generate an analysis note based on the external sources found.

        Args:
            external_sources (List[dict]): List of external sources

        Returns:
            str: Analysis note
        """
        if not external_sources:
            return "No verifiable external sources found via X."

        primary_count = sum(1 for s in external_sources if s["credibility_tier"] == "primary")
        secondary_count = sum(1 for s in external_sources if s["credibility_tier"] == "secondary")

        if primary_count > 0:
            return f"X posts linked to {primary_count} primary source(s) and {secondary_count} secondary source(s) that may corroborate research findings."
        elif secondary_count > 0:
            return f"X posts linked to {secondary_count} secondary news source(s) that may provide additional context."
        else:
            return "X posts contained links to sources of unknown credibility. Exercise caution."

    def _disabled_response(self) -> dict:
        """Return response when X analysis is disabled."""
        return {
            "has_relevant_posts": False,
            "posts_analyzed": 0,
            "external_sources": [],
            "discussion_summary": "",
            "analysis_note": "X analysis is disabled.",
            "search_query_used": ""
        }

    def _no_results_response(self, query: str) -> dict:
        """Return response when no posts are found."""
        return {
            "has_relevant_posts": False,
            "posts_analyzed": 0,
            "external_sources": [],
            "discussion_summary": "No relevant posts found on X for this claim.",
            "analysis_note": "No verifiable external sources found via X.",
            "search_query_used": query
        }

    def _error_response(self, error_message: str) -> dict:
        """Return response when an error occurs."""
        return {
            "has_relevant_posts": False,
            "posts_analyzed": 0,
            "external_sources": [],
            "discussion_summary": "",
            "analysis_note": f"X analysis unavailable: {error_message}",
            "search_query_used": "",
            "error": error_message
        }

    def _fallback_analysis(self, structured_claim: dict, search_query: str) -> dict:
        """
        Fallback analysis when X API is not configured.
        Returns a structured response indicating the limitation.

        Args:
            structured_claim (dict): Structured claim data
            search_query (str): Search query

        Returns:
            dict: Fallback response
        """
        return {
            "has_relevant_posts": False,
            "posts_analyzed": 0,
            "external_sources": [],
            "discussion_summary": "",
            "analysis_note": "X analysis requires API configuration. Proceeding with Perplexity research only.",
            "search_query_used": "",
            "fallback": True
        }
