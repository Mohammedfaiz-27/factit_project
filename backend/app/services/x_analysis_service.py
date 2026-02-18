"""
X (Twitter) Analysis Service — RapidAPI Twttr API

Analyzes X/Twitter for posts related to a claim using the RapidAPI Twttr API
(twitter241.p.rapidapi.com) Search Twitter V3 endpoint.

Authors are classified by priority:
1. Tamil news channels (highest priority)
2. National news channels
3. Common people (lowest priority)

External links are still extracted for backward compatibility.
"""

from app.core.config import RAPIDAPI_KEY, RAPIDAPI_HOST, X_ANALYSIS_ENABLED, X_SEARCH_LIMIT
import requests
import re
import json
from urllib.parse import urlparse
from typing import List, Dict, Optional


class XAnalysisService:
    """
    Analyzes X (Twitter) for posts discussing a claim.

    Uses RapidAPI Twttr API (Search Twitter V3) instead of official X API.
    Extracts post text, dates, and classifies authors by priority tier.
    Results are fed into Perplexity as research evidence.
    """

    def __init__(self):
        self.enabled = X_ANALYSIS_ENABLED
        self.rapidapi_key = RAPIDAPI_KEY
        self.rapidapi_host = RAPIDAPI_HOST
        self.search_limit = X_SEARCH_LIMIT
        self.base_url = f"https://{self.rapidapi_host}"

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

        if not self.rapidapi_key and self.enabled:
            print("WARNING: RAPIDAPI_KEY not set. X analysis will use fallback mode.")

    def analyze_claim(self, structured_claim: dict, search_query: str) -> dict:
        """
        Analyze X for posts discussing the claim.

        Returns post text, dates, author classifications, and external links.
        """
        if not self.enabled:
            return self._disabled_response()

        if not self.rapidapi_key:
            return self._fallback_analysis(structured_claim, search_query)

        try:
            x_query = self._build_x_search_query(structured_claim, search_query)

            if not x_query:
                return self._no_results_response("")

            tweets = self._search_posts(x_query)

            if not tweets:
                return self._no_results_response(x_query)

            # Extract post content with author classification
            posts_content = self._extract_posts_content(tweets)

            # Extract and categorize external URLs (backward compat)
            external_sources = self._extract_external_sources(tweets)

            # Generate neutral discussion summary
            discussion_summary = self._summarize_discussion(tweets, posts_content, structured_claim)

            # Generate analysis note
            analysis_note = self._generate_analysis_note(external_sources, posts_content)

            return {
                "has_relevant_posts": True,
                "posts_analyzed": len(tweets),
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
        Build an optimized search query for RapidAPI.
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
            words = [w for w in search_query.split() if len(w) > 3][:4]
            query_parts.append(" ".join(words))
        else:
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

        if len(base_query.strip()) < 3:
            print("[X Analysis] Search query too short — skipping X search")
            return ""

        # RapidAPI search — no need for -is:retweet operator (use type=Top for relevance)
        x_query = base_query.strip()

        if len(x_query) > 500:
            x_query = x_query[:500]

        return x_query

    def _search_posts(self, query: str) -> List[dict]:
        """
        Search RapidAPI Twttr API (Search Twitter V3) for posts matching the query.

        Returns a flat list of parsed tweet dicts with keys:
            text, created_at, author_handle, author_name, author_description, urls
        """
        headers = {
            "x-rapidapi-key": self.rapidapi_key,
            "x-rapidapi-host": self.rapidapi_host,
        }

        params = {
            "query": query,
            "type": "Top",
            "count": min(self.search_limit, 20),
        }

        print(f"[X Analysis] Searching RapidAPI for: {query[:80]}...")

        response = requests.get(
            f"{self.base_url}/search-v3",
            headers=headers,
            params=params,
            timeout=15
        )

        print(f"[X Analysis] Response status: {response.status_code}")

        if response.status_code != 200:
            print(f"[X Analysis] API error: {response.status_code} - {response.text[:200]}")
            return []

        data = response.json()

        # Parse the nested Twitter GraphQL-like response
        tweets = self._parse_search_response(data)
        print(f"[X Analysis] Parsed {len(tweets)} tweets from response")
        return tweets

    def _parse_search_response(self, data: dict) -> List[dict]:
        """
        Parse the deeply nested RapidAPI Search V3 response into flat tweet dicts.

        The response structure is:
        {
            result: {
                timeline_response: {
                    timeline: {
                        instructions: [
                            { __typename: "TimelineAddEntries", entries: [...] }
                        ]
                    }
                }
            }
        }

        Each entry contains tweet data at various nesting levels.
        """
        tweets = []

        try:
            result = data.get("result", {})
            timeline_response = result.get("timeline_response", result.get("timeline", {}))
            timeline = timeline_response.get("timeline", timeline_response)
            instructions = timeline.get("instructions", [])

            for instruction in instructions:
                entries = instruction.get("entries", [])
                for entry in entries:
                    tweet = self._extract_tweet_from_entry(entry)
                    if tweet:
                        tweets.append(tweet)

        except Exception as e:
            print(f"[X Analysis] Error parsing response: {e}")
            # Log a snippet of the response structure for debugging
            try:
                keys = list(data.keys()) if isinstance(data, dict) else str(type(data))
                print(f"[X Analysis] Response top-level keys: {keys}")
            except:
                pass

        return tweets

    def _extract_tweet_from_entry(self, entry: dict) -> Optional[dict]:
        """
        Extract tweet data from a timeline entry.

        Handles RapidAPI Twttr v3 response structure:
        - Tweet text in: tweet_result.details.full_text
        - Author info in: tweet_result.core.user_results.result.core (name, screen_name)
        - Author bio in: tweet_result.core.user_results.result.profile_bio.description
        - URLs in: tweet_result.url_entities[]
        - Created at in: tweet_result.details.created_at_ms (epoch ms)
        """
        try:
            content = entry.get("content", entry)

            # Find tweet_result via multiple possible paths
            tweet_result = None

            # Path A: content.itemContent.tweet_results.result (legacy Twitter API)
            item_content = content.get("itemContent", content.get("item", {}).get("itemContent", {}))
            if item_content:
                tweet_result = item_content.get("tweet_results", {}).get("result", {})

            # Path B: content.content.tweet_results.result (RapidAPI Twttr v3)
            if not tweet_result:
                inner_content = content.get("content", {})
                if isinstance(inner_content, dict):
                    tweet_result = inner_content.get("tweet_results", {}).get("result", {})

            if not tweet_result:
                # Path C: content.items[] (for modules/carousels)
                items = content.get("items", [])
                for item in items:
                    tweet = self._extract_tweet_from_entry(item)
                    if tweet:
                        return tweet
                return None

            # Handle "TweetWithVisibilityResults" wrapper
            if tweet_result.get("__typename") == "TweetWithVisibilityResults":
                tweet_result = tweet_result.get("tweet", tweet_result)

            # --- Extract tweet text ---
            # RapidAPI v3: text in details.full_text
            details = tweet_result.get("details", {})
            text = details.get("full_text", "") if isinstance(details, dict) else ""

            # Fallback: legacy.full_text (older API format)
            if not text:
                legacy = tweet_result.get("legacy", {})
                if isinstance(legacy, dict):
                    text = legacy.get("full_text", legacy.get("text", ""))

            if not text:
                return None

            # --- Extract created_at ---
            created_at_ms = details.get("created_at_ms", 0) if isinstance(details, dict) else 0
            if created_at_ms:
                from datetime import datetime, timezone
                dt = datetime.fromtimestamp(created_at_ms / 1000, tz=timezone.utc)
                created_at = dt.strftime("%a %b %d %H:%M:%S %z %Y")
                date_short = dt.strftime("%Y-%m-%d")
            else:
                legacy = tweet_result.get("legacy", {})
                created_at = legacy.get("created_at", "") if isinstance(legacy, dict) else ""
                date_short = self._parse_twitter_date(created_at)

            # --- Extract author info ---
            # RapidAPI v3: core.user_results.result.core (name, screen_name)
            core = tweet_result.get("core", {})
            user_result = core.get("user_results", {}).get("result", {})
            user_core = user_result.get("core", {})

            author_handle = user_core.get("screen_name", "unknown")
            author_name = user_core.get("name", "Unknown")

            # Bio in profile_bio.description (v3) or user_result.legacy.description (older)
            profile_bio = user_result.get("profile_bio", {})
            author_description = profile_bio.get("description", "") if isinstance(profile_bio, dict) else ""
            if not author_description:
                user_legacy = user_result.get("legacy", {})
                if isinstance(user_legacy, dict):
                    author_description = user_legacy.get("description", "")

            verified = user_result.get("verified", False)

            # --- Extract URLs ---
            urls = []
            # RapidAPI v3: url_entities at tweet_result level
            for url_entity in tweet_result.get("url_entities", []):
                expanded = url_entity.get("expanded_url", url_entity.get("url", ""))
                if expanded:
                    urls.append({
                        "expanded_url": expanded,
                        "title": url_entity.get("title", ""),
                        "description": url_entity.get("description", ""),
                    })

            # Fallback: legacy.entities.urls or details.hashtag_entities for URLs
            if not urls:
                legacy = tweet_result.get("legacy", {})
                if isinstance(legacy, dict):
                    entities = legacy.get("entities", {})
                    for url_entity in entities.get("urls", []):
                        expanded = url_entity.get("expanded_url", url_entity.get("url", ""))
                        if expanded:
                            urls.append({
                                "expanded_url": expanded,
                                "title": url_entity.get("title", ""),
                                "description": url_entity.get("description", ""),
                            })

            return {
                "text": text,
                "created_at": created_at,
                "date": date_short,
                "author_handle": author_handle,
                "author_name": author_name,
                "author_description": author_description,
                "verified": verified,
                "urls": urls,
            }

        except Exception as e:
            return None

    def _parse_twitter_date(self, date_str: str) -> str:
        """Parse Twitter date format to YYYY-MM-DD."""
        if not date_str:
            return ""

        # Already ISO format (YYYY-MM-DD...)
        if date_str[:4].isdigit() and len(date_str) >= 10:
            return date_str[:10]

        # Twitter format: "Wed Oct 10 20:19:24 +0000 2018"
        try:
            from datetime import datetime
            dt = datetime.strptime(date_str, "%a %b %d %H:%M:%S %z %Y")
            return dt.strftime("%Y-%m-%d")
        except:
            return date_str[:10] if len(date_str) >= 10 else date_str

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

        if handle_lower in self.tamil_news_handles:
            return "tamil_news", 1

        if handle_lower in self.national_news_handles:
            return "national_news", 2

        if description:
            desc_lower = description.lower()
            news_keywords = [
                "news", "media", "channel", "reporter", "journalist",
                "newspaper", "editor", "correspondent", "செய்தி",
                "நிருபர்", "ஊடகம்",
            ]
            if any(kw in desc_lower for kw in news_keywords):
                tamil_indicators = [
                    "tamil", "tamilnadu", "tamil nadu", "chennai",
                    "தமிழ்", "தமிழ்நாடு",
                ]
                if any(ind in desc_lower for ind in tamil_indicators):
                    return "tamil_news", 1
                return "national_news", 2

        return "common_people", 3

    def _extract_posts_content(self, tweets: List[dict]) -> List[dict]:
        """
        Extract post text, date, and author info with priority classification.

        Limits to top 8 posts: up to 3 Tamil news + 3 National news + 2 Common people.
        """
        categorized = {"tamil_news": [], "national_news": [], "common_people": []}

        for tweet in tweets:
            author_handle = tweet.get("author_handle", "unknown")
            author_description = tweet.get("author_description", "")
            verified = tweet.get("verified", False)

            category, priority = self._classify_author(author_handle, author_description, verified)

            entry = {
                "text": tweet.get("text", ""),
                "date": tweet.get("date", ""),
                "author_name": tweet.get("author_name", "Unknown"),
                "author_handle": author_handle,
                "author_category": category,
                "priority": priority,
            }

            categorized[category].append(entry)

        tamil = categorized["tamil_news"][:3]
        national = categorized["national_news"][:3]
        common = categorized["common_people"][:2]

        result = tamil + national + common
        if len(result) > 8:
            result = result[:8]

        print(f"[X Analysis] Posts by category: Tamil news={len(tamil)}, National news={len(national)}, Common people={len(common)}")

        return result

    def _extract_external_sources(self, tweets: List[dict]) -> List[dict]:
        """Extract and categorize external URLs from tweets."""
        external_sources = []
        seen_domains = set()

        for tweet in tweets:
            for url_entity in tweet.get("urls", []):
                expanded_url = url_entity.get("expanded_url", "")

                if not expanded_url or "twitter.com" in expanded_url or "x.com" in expanded_url:
                    continue

                if any(shortener in expanded_url for shortener in ["bit.ly", "t.co", "tinyurl"]):
                    continue

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

    def _summarize_discussion(self, tweets: List[dict], posts_content: List[dict], structured_claim: dict) -> str:
        """Generate a neutral summary of the X discussion."""
        if not tweets:
            return "No relevant discussion found on X."

        num_posts = len(tweets)
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
            "analysis_note": "X analysis requires RapidAPI configuration. Proceeding with Perplexity research only.",
            "search_query_used": "",
            "fallback": True
        }
