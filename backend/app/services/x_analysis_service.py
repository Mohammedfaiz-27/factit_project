"""
X (Twitter) Analysis Service

Analyzes X/Twitter for posts related to a claim, extracting post text, dates,
and author information to feed as evidence into Perplexity research.

Authors are classified by priority:
1. Tamil news channels (highest priority)
2. National news channels
3. Common people (lowest priority)

External links are still extracted for backward compatibility.
"""

from app.core.config import X_BEARER_TOKEN, X_ANALYSIS_ENABLED, X_SEARCH_LIMIT
import requests
import re
from urllib.parse import urlparse
from typing import List, Dict, Optional


class XAnalysisService:
    """
    Analyzes X (Twitter) for posts discussing a claim.

    Extracts post text, dates, and classifies authors by priority tier.
    Results are fed into Perplexity as research evidence.
    """

    def __init__(self):
        self.enabled = X_ANALYSIS_ENABLED
        self.bearer_token = X_BEARER_TOKEN
        self.search_limit = X_SEARCH_LIMIT
        self.base_url = "https://api.twitter.com/2"

        # Tamil news X handles (priority 1)
        self.tamil_news_handles = {
            "dinamaborig", "dailythanthi", "news7tamil", "pttvonlinenews",
            "thanthitv", "sunnewstamil", "polimernews", "kaborimedia",
            "aborathamil", "dinamani", "maalaimalar", "vikaborig",
            "paboriyathalaim", "daborext", "news18tamilnadu", "newsaboramil",
            "jaboramilnadu", "caborewstamil", "newsjtamil", "aborpnews",
            "hinduaboramil", "onaboriatamil",
        }

        # National news X handles (priority 2)
        self.national_news_handles = {
            "ndtv", "the_hindu", "indiatoday", "timesofindia",
            "htaborig", "indianexpress", "pti_news", "ani",
            "news18india", "republic", "ababorews", "zeenews",
            "theprint", "scroll_in", "thequint", "livemint",
            "baborandardbiz", "deccanherald", "neaborianexp",
            "oneindia", "firstpost", "outlookindia", "theweek",
            "ndtvindia", "aaborak", "baborbc_india",
        }

        # Credibility tiers for linked domains
        self.primary_sources = {
            "reuters.com", "apnews.com", "afp.com",
            "bbc.com", "bbc.co.uk", "npr.org", "pbs.org",
            "gov", "gov.uk", "gov.in", "europa.eu", "un.org", "who.int",
            "edu", "ac.uk", "nature.com", "sciencedirect.com", "pubmed.ncbi.nlm.nih.gov",
        }

        self.secondary_sources = {
            "nytimes.com", "washingtonpost.com", "theguardian.com", "wsj.com",
            "economist.com", "ft.com", "thehindu.com", "indianexpress.com",
            "timesofindia.indiatimes.com", "hindustantimes.com",
            "cnn.com", "nbcnews.com", "abcnews.go.com", "cbsnews.com",
            "ndtv.com", "indiatoday.in",
            "pti.in", "ani.in",
            "snopes.com", "factcheck.org", "politifact.com", "altnews.in",
            "dinamalar.com", "dailythanthi.com", "dinamani.com", "maalaimalar.com",
            "vikatan.com", "news7tamil.live", "puthiyathalaimurai.com",
            "polimernews.com", "dtnext.in",
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
        Analyze X for posts discussing the claim.

        Returns post text, dates, author classifications, and external links.
        """
        if not self.enabled:
            return self._disabled_response()

        if not self.bearer_token:
            return self._fallback_analysis(structured_claim, search_query)

        try:
            x_query = self._build_x_search_query(structured_claim, search_query)

            if not x_query:
                return self._no_results_response("")

            posts, users_map = self._search_posts(x_query)

            if not posts:
                return self._no_results_response(x_query)

            # Extract post content with author classification
            posts_content = self._extract_posts_content(posts, users_map)

            # Extract and categorize external URLs (backward compat)
            external_sources = self._extract_external_sources(posts)

            # Generate neutral discussion summary
            discussion_summary = self._summarize_discussion(posts, posts_content, structured_claim)

            # Generate analysis note
            analysis_note = self._generate_analysis_note(external_sources, posts_content)

            return {
                "has_relevant_posts": True,
                "posts_analyzed": len(posts),
                "posts_content": posts_content,
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
        No language restriction; no has:links filter (we want ALL posts).
        """
        entities = structured_claim.get("entities", [])
        claim = structured_claim.get("claim", search_query)
        original_input = structured_claim.get("original_input", "")
        geographic_scope = structured_claim.get("geographic_scope", "national")

        query_parts = []

        if entities:
            entity_query = " ".join(entities[:2])
            query_parts.append(entity_query)
        elif search_query:
            # Use the Perplexity search query (already cleaned) as fallback
            # Take first 4 significant words from it
            words = [w for w in search_query.split() if len(w) > 3][:4]
            query_parts.append(" ".join(words))
        else:
            # Last resort: extract words from claim, skipping boilerplate prefixes
            skip_words = {"claims", "from", "image", "image:", "video", "video:", "audio", "audio:", "context"}
            words = [w for w in claim.split() if len(w) > 3 and w.lower().rstrip(":") not in skip_words][:4]
            query_parts.append(" ".join(words))

        base_query = " ".join(query_parts)

        # For local/district claims with regional language input,
        # use regional language terms (people tweet in their language)
        if geographic_scope in ("local", "district") and original_input:
            is_regional = any(ord(c) > 127 for c in original_input.replace(' ', ''))
            if is_regional:
                original_words = [w for w in original_input.split() if len(w) > 2][:3]
                if original_words:
                    regional_terms = " ".join(original_words)
                    base_query = regional_terms

        # Validate base_query has substance before building final query
        if len(base_query.strip()) < 3:
            print("[X Analysis] Search query too short — skipping X search")
            return ""

        # No has:links — we want ALL posts about the claim, not just ones with links
        x_query = f"{base_query} -is:retweet"

        if len(x_query) > 500:
            x_query = x_query[:500]

        return x_query

    def _search_posts(self, query: str) -> tuple:
        """
        Search X API for posts matching the query with author expansion.

        Returns:
            tuple: (list of tweets, dict mapping author_id -> user object)
        """
        headers = {
            "Authorization": f"Bearer {self.bearer_token}",
            "Content-Type": "application/json"
        }

        # Cap at 15 — we only extract max 8 posts (3 Tamil + 3 National + 2 Common)
        # Fetching more is wasted API credits. X API v2 minimum is 10.
        max_results = min(self.search_limit, 15)
        max_results = max(max_results, 10)  # X API minimum

        params = {
            "query": query,
            "max_results": max_results,
            "tweet.fields": "entities,created_at,author_id",
            "expansions": "author_id",
            "user.fields": "name,username,verified,description",
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

            # Build user lookup map from includes
            users_map = {}
            includes = data.get("includes", {})
            for user in includes.get("users", []):
                users_map[user["id"]] = user

            print(f"[X Analysis] Found {len(tweets)} posts, {len(users_map)} unique authors")
            return tweets, users_map
        elif response.status_code == 401:
            print("[X Analysis] Authentication failed - check bearer token")
            return [], {}
        elif response.status_code == 429:
            print("[X Analysis] Rate limited")
            return [], {}
        else:
            print(f"[X Analysis] API error: {response.status_code}")
            return [], {}

    def _classify_author(self, username: str, description: str = "", verified: bool = False) -> tuple:
        """
        Classify an author into a priority tier.

        Returns:
            tuple: (category_name, priority_number)
                   priority 1 = Tamil news (highest)
                   priority 2 = National news
                   priority 3 = Common people (lowest)
        """
        handle_lower = username.lower() if username else ""

        # Check Tamil news handles
        if handle_lower in self.tamil_news_handles:
            return "tamil_news", 1

        # Check national news handles
        if handle_lower in self.national_news_handles:
            return "national_news", 2

        # Secondary signal: check description for news keywords
        if description:
            desc_lower = description.lower()
            news_keywords = [
                "news", "media", "channel", "reporter", "journalist",
                "newspaper", "editor", "correspondent", "செய்தி",
                "நிருபர்", "ஊடகம்",
            ]
            if any(kw in desc_lower for kw in news_keywords):
                # Check for Tamil-specific indicators
                tamil_indicators = [
                    "tamil", "tamilnadu", "tamil nadu", "chennai",
                    "தமிழ்", "தமிழ்நாடு",
                ]
                if any(ind in desc_lower for ind in tamil_indicators):
                    return "tamil_news", 1
                return "national_news", 2

        # Verified accounts with no news keywords are still common people
        return "common_people", 3

    def _extract_posts_content(self, posts: List[dict], users_map: dict) -> List[dict]:
        """
        Extract post text, date, and author info with priority classification.

        Limits to top 15 posts: up to 5 Tamil news + 5 National news + 5 Common people
        (fills from available if a category has fewer).
        """
        categorized = {"tamil_news": [], "national_news": [], "common_people": []}

        for post in posts:
            text = post.get("text", "")
            created_at = post.get("created_at", "")
            author_id = post.get("author_id", "")

            # Look up author info
            user = users_map.get(author_id, {})
            author_name = user.get("name", "Unknown")
            author_handle = user.get("username", "unknown")
            description = user.get("description", "")
            verified = user.get("verified", False)

            category, priority = self._classify_author(author_handle, description, verified)

            # Parse date to just YYYY-MM-DD if full ISO timestamp
            date_short = created_at[:10] if created_at else ""

            entry = {
                "text": text,
                "date": date_short,
                "author_name": author_name,
                "author_handle": author_handle,
                "author_category": category,
                "priority": priority,
            }

            categorized[category].append(entry)

        # Take up to 3 from news categories, 2 from common people
        # (fewer posts = lower Perplexity token cost)
        tamil = categorized["tamil_news"][:3]
        national = categorized["national_news"][:3]
        common = categorized["common_people"][:2]

        result = tamil + national + common
        if len(result) > 8:
            result = result[:8]

        print(f"[X Analysis] Posts by category: Tamil news={len(tamil)}, National news={len(national)}, Common people={len(common)}")

        return result

    def _extract_external_sources(self, posts: List[dict]) -> List[dict]:
        """Extract and categorize external URLs from posts."""
        external_sources = []
        seen_domains = set()

        for post in posts:
            entities = post.get("entities", {})
            urls = entities.get("urls", [])

            for url_entity in urls:
                expanded_url = url_entity.get("expanded_url", "")

                if not expanded_url or "twitter.com" in expanded_url or "x.com" in expanded_url:
                    continue

                if any(shortener in expanded_url for shortener in ["bit.ly", "t.co", "tinyurl"]):
                    expanded_url = url_entity.get("unwound_url", expanded_url)

                try:
                    parsed = urlparse(expanded_url)
                    domain = parsed.netloc.lower().replace("www.", "")
                except:
                    continue

                if domain in seen_domains:
                    continue
                seen_domains.add(domain)

                credibility_tier = self._get_credibility_tier(domain)

                title = url_entity.get("title", "")
                description = url_entity.get("description", "")

                external_sources.append({
                    "url": expanded_url,
                    "domain": domain,
                    "title": title,
                    "description": description[:200] if description else "",
                    "credibility_tier": credibility_tier
                })

        tier_order = {"primary": 0, "secondary": 1, "unknown": 2}
        external_sources.sort(key=lambda x: tier_order.get(x["credibility_tier"], 2))

        return external_sources[:5]

    def _get_credibility_tier(self, domain: str) -> str:
        """Determine the credibility tier of a domain."""
        if domain in self.primary_sources:
            return "primary"

        for suffix in [".gov", ".edu", ".ac.uk", ".gov.uk", ".gov.in"]:
            if domain.endswith(suffix):
                return "primary"

        if domain in self.secondary_sources:
            return "secondary"

        for source in self.secondary_sources:
            if source in domain:
                return "secondary"

        return "unknown"

    def _summarize_discussion(self, posts: List[dict], posts_content: List[dict], structured_claim: dict) -> str:
        """Generate a neutral summary of the X discussion."""
        if not posts:
            return "No relevant discussion found on X."

        num_posts = len(posts)
        tamil_count = sum(1 for p in posts_content if p["author_category"] == "tamil_news")
        national_count = sum(1 for p in posts_content if p["author_category"] == "national_news")
        common_count = sum(1 for p in posts_content if p["author_category"] == "common_people")

        summary = f"Found {num_posts} posts on X discussing this topic"
        parts = []
        if tamil_count > 0:
            parts.append(f"{tamil_count} from Tamil news channels")
        if national_count > 0:
            parts.append(f"{national_count} from national news channels")
        if common_count > 0:
            parts.append(f"{common_count} from public accounts")

        if parts:
            summary += f" ({', '.join(parts)})."
        else:
            summary += "."

        return summary

    def _generate_analysis_note(self, external_sources: List[dict], posts_content: List[dict] = None) -> str:
        """Generate an analysis note based on findings."""
        parts = []

        if posts_content:
            news_count = sum(1 for p in posts_content if p["priority"] <= 2)
            if news_count > 0:
                parts.append(f"{news_count} news channel post(s) extracted as research leads")

        if external_sources:
            primary_count = sum(1 for s in external_sources if s["credibility_tier"] == "primary")
            secondary_count = sum(1 for s in external_sources if s["credibility_tier"] == "secondary")
            if primary_count > 0:
                parts.append(f"{primary_count} primary source link(s)")
            if secondary_count > 0:
                parts.append(f"{secondary_count} secondary source link(s)")

        if parts:
            return "X analysis found: " + ", ".join(parts) + ". This evidence was provided to Perplexity for research."
        else:
            return "No verifiable external sources found via X."

    def _disabled_response(self) -> dict:
        return {
            "has_relevant_posts": False,
            "posts_analyzed": 0,
            "posts_content": [],
            "external_sources": [],
            "discussion_summary": "",
            "analysis_note": "X analysis is disabled.",
            "search_query_used": ""
        }

    def _no_results_response(self, query: str) -> dict:
        return {
            "has_relevant_posts": False,
            "posts_analyzed": 0,
            "posts_content": [],
            "external_sources": [],
            "discussion_summary": "No relevant posts found on X for this claim.",
            "analysis_note": "No verifiable external sources found via X.",
            "search_query_used": query
        }

    def _error_response(self, error_message: str) -> dict:
        return {
            "has_relevant_posts": False,
            "posts_analyzed": 0,
            "posts_content": [],
            "external_sources": [],
            "discussion_summary": "",
            "analysis_note": f"X analysis unavailable: {error_message}",
            "search_query_used": "",
            "error": error_message
        }

    def _fallback_analysis(self, structured_claim: dict, search_query: str) -> dict:
        return {
            "has_relevant_posts": False,
            "posts_analyzed": 0,
            "posts_content": [],
            "external_sources": [],
            "discussion_summary": "",
            "analysis_note": "X analysis requires API configuration. Proceeding with Perplexity research only.",
            "search_query_used": "",
            "fallback": True
        }
