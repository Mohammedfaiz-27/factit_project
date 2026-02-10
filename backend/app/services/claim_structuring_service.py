from app.core.config import GEMINI_API_KEY, GEMINI_MODEL
from google import genai
import json
import re
import time

class ClaimStructuringService:
    """
    Converts unstructured or vague user input into a clean, structured prompt
    that follows a standardized schema for fact-checking.
    """

    def __init__(self):
        if not GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY environment variable is not set")
        self.client = genai.Client(api_key=GEMINI_API_KEY)
        self.model = GEMINI_MODEL

    def structure_claim(self, claim_text: str, max_retries: int = 3) -> dict:
        """
        Structure any free-form user query or statement into a standardized format.

        For long non-English text (>200 chars), pre-translates to English first
        to prevent hallucinations in entity/location extraction.

        Args:
            claim_text (str): Raw claim or question from user
            max_retries (int): Maximum number of retry attempts for API overload

        Returns:
            dict: Structured claim following the schema
        """
        # For long non-English text, pre-translate to English to prevent
        # Gemini from hallucinating wrong locations/entities from Tamil/Hindi text
        is_non_english = any(ord(c) > 127 for c in claim_text.replace(' ', ''))
        working_text = claim_text
        if is_non_english and len(claim_text) > 200:
            print(f"[Structuring] Pre-translating long non-English text ({len(claim_text)} chars)...")
            translated = self.translate_to_english(claim_text)
            if translated and translated != claim_text:
                working_text = translated
                print(f"[Structuring] Using English translation for structuring ({len(translated)} chars)")

        last_error = None

        for attempt in range(max_retries):
            try:
                chat = self.client.chats.create(model=self.model)

                structuring_prompt = f"""
You are an LLM whose job is to convert unstructured or vague user input into a clean, structured prompt that can be used for fact-checking.

### Your Goal
Take any free-form user query or statement and rewrite it into a standardized structured prompt that follows the schema below.

### Schema
{{
  "task": "fact_check",
  "claim": "<the main factual statement extracted or reformulated>",
  "claim_type": "<one of: protest_arrest, accident_death, government_scheme, heritage_environment, politics, crime, health_science, other>",
  "geographic_scope": "<one of: local, district, state, national, international>",
  "location": "<specific location: city/town, district, state, country>",
  "context": "<any background info, source, or related details>",
  "entities": ["<list of names, organizations, or locations involved>"],
  "time_period": "<specific year or time frame if mentioned>",
  "output_format": "json"
}}

### Claim Type Definitions
- "protest_arrest": Protests, strikes, road blockades, dharnas, arrests, police action, labor disputes
- "accident_death": Road accidents, deaths, injuries, fires, natural disasters, mishaps
- "government_scheme": Government programs, welfare schemes, training programs, subsidies, policy announcements, official orders
- "heritage_environment": Archaeological finds, heritage sites, environmental issues, forest/wildlife, conservation, activism
- "politics": Elections, party activities, political statements, governance decisions
- "crime": Criminal cases, fraud, scams, court verdicts (not protest-related arrests)
- "health_science": Medical claims, scientific discoveries, health advisories, disease outbreaks
- "other": Anything not fitting the above categories

### Geographic Scope Definitions
- "local": Specific town, village, or neighborhood
- "district": District-level event (e.g., Perambalur district, Pudukkottai district)
- "state": State-level event (e.g., Tamil Nadu, Kerala)
- "national": Country-level event
- "international": Multi-country or global event

### Rules
1. Always output **valid JSON** — no extra text or explanation.
2. The `claim` field must be a **clear factual statement**, even if the input was a question.
3. If certain information is not found (e.g., date, entities), leave the field as an empty string or empty list.
4. Never add opinions or assumptions — only reorganize the information logically.
5. The `claim_type` and `geographic_scope` MUST always be filled — infer from context.
6. The `location` field should be as specific as possible (e.g., "Pudukkottai, Tamil Nadu, India").

### Examples

User input: "did elon talk about tesla launching robotaxi next year?"
Output:
{{
  "task": "fact_check",
  "claim": "Elon Musk said Tesla will launch a robotaxi next year.",
  "claim_type": "other",
  "geographic_scope": "international",
  "location": "United States",
  "context": "",
  "entities": ["Elon Musk", "Tesla"],
  "time_period": "next year",
  "output_format": "json"
}}

User input: "புதுக்கோட்டை மாவட்டத்தில் TAHDCO SC-ST இளைஞர்களுக்கு பயிற்சி"
Output:
{{
  "task": "fact_check",
  "claim": "TAHDCO announced skill training programs for SC-ST youth in Pudukkottai district.",
  "claim_type": "government_scheme",
  "geographic_scope": "district",
  "location": "Pudukkottai, Tamil Nadu, India",
  "context": "TAHDCO (Tamil Nadu Adi Dravidar Housing and Development Corporation) training for SC-ST youth",
  "entities": ["TAHDCO", "Pudukkottai"],
  "time_period": "",
  "output_format": "json"
}}

Now convert this user input:
"{working_text}"
"""

                response = chat.send_message(structuring_prompt)
                result_text = response.text.strip()

                # Extract JSON from response (in case there's extra text)
                json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
                if json_match:
                    structured_data = json.loads(json_match.group())

                    # Ensure all required keys are present with proper defaults
                    required_schema = {
                        "task": "fact_check",
                        "claim": claim_text,
                        "claim_type": "other",
                        "geographic_scope": "national",
                        "location": "",
                        "context": "",
                        "entities": [],
                        "time_period": "",
                        "output_format": "json"
                    }

                    # Merge AI response with required schema
                    for key, default_value in required_schema.items():
                        if key not in structured_data or structured_data[key] is None:
                            structured_data[key] = default_value

                    # Store original input for reference
                    structured_data["original_input"] = claim_text

                    return structured_data
                else:
                    # Fallback if JSON parsing fails
                    return self._create_fallback_structure(claim_text)

            except Exception as e:
                last_error = e
                error_msg = str(e)

                # Check if it's a 503 (overload) error
                if "503" in error_msg or "UNAVAILABLE" in error_msg or "overload" in error_msg.lower():
                    if attempt < max_retries - 1:
                        # Exponential backoff: wait 2^attempt seconds
                        wait_time = 2 ** attempt
                        print(f"Gemini API overloaded (attempt {attempt + 1}/{max_retries}). Retrying in {wait_time}s...")
                        time.sleep(wait_time)
                        continue
                    else:
                        print(f"Gemini API overloaded after {max_retries} attempts. Using fallback structure.")
                else:
                    print(f"Claim structuring error: {error_msg}")

                # If last attempt or non-retriable error, use fallback
                if attempt == max_retries - 1:
                    return self._create_fallback_structure(claim_text)

        # If all retries failed, return fallback
        print(f"All {max_retries} attempts failed. Using fallback structure.")
        return self._create_fallback_structure(claim_text)

    def _create_fallback_structure(self, claim_text: str) -> dict:
        """
        Create a basic structure if AI structuring fails.
        """
        return {
            "task": "fact_check",
            "claim": claim_text,
            "claim_type": "other",
            "geographic_scope": "national",
            "location": "",
            "context": "",
            "entities": [],
            "time_period": "",
            "output_format": "json",
            "original_input": claim_text
        }

    def translate_to_english(self, text: str) -> str:
        """
        Translate non-English text to English for better search results.

        Args:
            text (str): Text that may be in any language

        Returns:
            str: English translation or original text if already English
        """
        try:
            # Check if text contains non-ASCII characters (likely non-English)
            if all(ord(char) < 128 for char in text.replace(' ', '').replace('\n', '')):
                return text  # Already English/ASCII

            chat = self.client.chats.create(model=self.model)

            translate_prompt = f"""Translate the following text to English. If it's already in English, return it as-is.
Only output the translation, nothing else.

Text: {text}"""

            response = chat.send_message(translate_prompt)
            translated = response.text.strip()

            # Remove quotes if present
            if translated.startswith('"') and translated.endswith('"'):
                translated = translated[1:-1]

            return translated

        except Exception as e:
            print(f"Translation error: {e}")
            return text  # Return original on error

    def create_search_query(self, structured_claim: dict) -> str:
        """
        Create an optimized search query from structured claim.
        For local/district claims in regional languages, returns a bilingual query
        so Perplexity can match both English and regional language indexed content.

        For long claims (press releases, detailed announcements), builds a focused
        query from key entities + location + action keywords instead of the full text.

        Args:
            structured_claim (dict): Structured claim data with new schema

        Returns:
            str: Optimized search query for Perplexity
        """
        # Extract components from new schema
        claim = structured_claim.get("claim", "")
        entities = structured_claim.get("entities", [])
        context = structured_claim.get("context", "")
        time_period = structured_claim.get("time_period", "")
        geographic_scope = structured_claim.get("geographic_scope", "national")
        claim_type = structured_claim.get("claim_type", "other")
        location = structured_claim.get("location", "")
        original_input = structured_claim.get("original_input", "")

        # For long claims (press releases, detailed announcements), build a focused
        # query from key components instead of using the verbose full claim text
        if len(claim) > 120 and entities:
            english_query = self._build_focused_query(
                entities, location, time_period, claim, claim_type
            )
            print(f"[Search Query] Focused query for long claim: {english_query[:80]}")
        else:
            # Build English query from structured components (short claims)
            query_parts = []

            # Start with the main claim (most important)
            if claim:
                query_parts.append(claim)

            # Add time period if specified and not vague
            if time_period and time_period.lower() not in ["recent", "now", "current"]:
                query_parts.append(time_period)

            # Add context if it provides additional useful information
            if context and len(context) < 100:
                query_parts.append(context)

            # If query is too short, add entities for more context
            english_query = " ".join(query_parts)
            if len(english_query) < 50 and entities:
                entity_text = " ".join(entities[:3])  # Limit to first 3 entities
                english_query = f"{english_query} {entity_text}"

            # If query is too long, use just the claim
            if len(english_query) > 200:
                english_query = claim[:200]

        # Fallback to original input if all else fails
        if not english_query.strip():
            english_query = original_input[:200]

        # Ensure english_query is actually in English
        english_query = self.translate_to_english(english_query.strip())

        # For local/district/state claims with non-English original input,
        # create a bilingual query so Perplexity can match regional language content
        if geographic_scope in ("local", "district", "state") and original_input:
            is_non_english = any(ord(char) > 127 for char in original_input.replace(' ', ''))
            if is_non_english:
                # Extract key terms from original language (significant words only)
                original_words = [w for w in original_input.split() if len(w) > 3][:8]
                original_key_terms = " ".join(original_words)
                # Combine: English query first, then original language key terms
                search_query = f"{english_query} | {original_key_terms}"
                # Cap total length
                if len(search_query) > 400:
                    search_query = search_query[:400]
                print(f"[Search Query] Bilingual query for {geographic_scope} claim")
                return search_query

        return english_query

    def _build_focused_query(self, entities: list, location: str, time_period: str, claim: str, claim_type: str) -> str:
        """
        Build a short, focused search query from key claim components.
        Used when the full claim text is too long for effective search.

        Extracts actual subject-specific terms from the claim text (e.g., "budget",
        "interim", "protest") rather than relying on predefined keyword lists.

        Args:
            entities: Key entities from the claim
            location: Location string (e.g., "Nagapattinam, Tamil Nadu, India")
            time_period: Time period (e.g., "February 2026")
            claim: Full claim text (for keyword extraction)
            claim_type: Type of claim (e.g., "government_scheme")

        Returns:
            str: Focused search query (typically 60-120 chars)
        """
        query_parts = []

        # Add entities (top 3)
        query_parts.extend(entities[:3])

        # Add primary location if not already in entities
        if location:
            primary_location = location.split(",")[0].strip()
            if not any(primary_location.lower() in e.lower() for e in entities):
                query_parts.append(primary_location)

        # Extract key subject terms from the claim text itself
        # This captures domain-specific terms like "budget", "interim", "protest"
        # that predefined keyword lists would miss
        already_included = list(entities[:3])
        if location:
            already_included.append(location.split(",")[0].strip())
        if time_period:
            already_included.append(time_period)
        key_terms = self._extract_key_terms(claim, exclude_terms=already_included)

        # Add top 3 subject terms that aren't already in the query
        added_subject_terms = 0
        for term in key_terms:
            if added_subject_terms >= 3:
                break
            if not any(term.lower() in p.lower() for p in query_parts):
                query_parts.append(term)
                added_subject_terms += 1

        # Add time period
        if time_period and time_period.lower() not in ["recent", "now", "current"]:
            query_parts.append(time_period)

        return " ".join(query_parts)

    def _extract_key_terms(self, text: str, exclude_terms: list = None) -> list:
        """
        Extract key subject terms from text by removing common stopwords.
        Returns the most important remaining words — these are the terms that
        make the claim unique and searchable (e.g., "budget", "interim", "protest").

        Args:
            text: Input text to extract terms from
            exclude_terms: Terms to exclude (e.g., already-added entities/locations)

        Returns:
            list: Key terms ordered by appearance (up to 5)
        """
        stopwords = {
            # Articles, pronouns, determiners
            "the", "a", "an", "this", "that", "these", "those",
            "it", "its", "he", "she", "they", "his", "her", "their",
            "him", "them", "we", "our", "you", "your", "i", "my",
            # Prepositions
            "in", "on", "at", "to", "for", "of", "with", "by", "from",
            "up", "about", "into", "through", "during", "before", "after",
            "above", "below", "between", "under", "over", "out",
            # Conjunctions & misc
            "and", "but", "or", "nor", "not", "so", "yet",
            "if", "then", "than", "too", "very", "just",
            "also", "only", "own", "same", "other", "each", "every",
            "all", "both", "few", "more", "most", "some", "such",
            "no", "any", "many", "much", "several",
            "which", "who", "whom", "what", "where", "when", "how", "why",
            "there", "here", "now", "once",
            # Common verbs (too generic for search)
            "is", "are", "was", "were", "be", "been", "being",
            "have", "has", "had", "do", "does", "did",
            "will", "would", "shall", "should", "may", "might",
            "must", "can", "could",
            "said", "stated", "announced", "declared", "reported",
            "according", "mentioned", "noted",
            # Generic adjectives
            "new", "old", "first", "last", "next",
            "upcoming", "recent", "current", "present",
        }

        exclude_lower = set()
        if exclude_terms:
            for term in exclude_terms:
                for word in term.lower().split():
                    exclude_lower.add(word)

        # Extract English words (alphanumeric, at least 3 chars)
        words = re.findall(r'\b[a-zA-Z][a-zA-Z0-9-]+\b', text)

        key_terms = []
        seen = set()
        for word in words:
            w_lower = word.lower()
            if (w_lower not in stopwords and
                w_lower not in exclude_lower and
                w_lower not in seen and
                len(word) > 2):
                key_terms.append(word)
                seen.add(w_lower)

        return key_terms[:5]

    def create_alternative_query(self, structured_claim: dict) -> str:
        """
        Create a simplified alternative query for retry when the first search fails.
        Uses minimal components for broader matching.

        Args:
            structured_claim (dict): Structured claim data

        Returns:
            str: Simplified search query, or empty string if can't generate one
        """
        entities = structured_claim.get("entities", [])
        location = structured_claim.get("location", "")
        time_period = structured_claim.get("time_period", "")
        original_input = structured_claim.get("original_input", "")
        geographic_scope = structured_claim.get("geographic_scope", "national")

        # For regional language claims, try a purely regional language query
        # (local media publishes in Tamil, not English)
        if original_input and any(ord(c) > 127 for c in original_input.replace(' ', '')):
            key_words = [w for w in original_input.split() if len(w) > 3][:6]
            if key_words:
                alt_query = " ".join(key_words)
                print(f"[Search Query] Alternative regional language query: {alt_query[:60]}")
                return alt_query

        # English fallback: entities + key subject terms + location
        claim = structured_claim.get("claim", "")
        parts = list(entities[:2])

        # Add key subject terms from the claim (fixes missing terms like "budget")
        if claim:
            key_terms = self._extract_key_terms(claim, exclude_terms=entities)
            parts.extend(key_terms[:3])

        if location:
            primary_loc = location.split(",")[0].strip()
            if not any(primary_loc.lower() in p.lower() for p in parts):
                parts.append(primary_loc)
        if time_period:
            parts.append(time_period)

        alt_query = " ".join(parts)
        return alt_query if alt_query.strip() else ""
