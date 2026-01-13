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

        Args:
            claim_text (str): Raw claim or question from user
            max_retries (int): Maximum number of retry attempts for API overload

        Returns:
            dict: Structured claim following the schema:
                {
                    "task": "fact_check",
                    "claim": "<clear factual statement>",
                    "context": "<background info or details>",
                    "entities": ["<names, organizations, locations>"],
                    "time_period": "<specific year or time frame>",
                    "output_format": "json"
                }
        """
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
  "context": "<any background info, source, or related details>",
  "entities": ["<list of names, organizations, or locations involved>"],
  "time_period": "<specific year or time frame if mentioned>",
  "output_format": "json"
}}

### Rules
1. Always output **valid JSON** — no extra text or explanation.
2. The `claim` field must be a **clear factual statement**, even if the input was a question.
3. If certain information is not found (e.g., date, entities), leave the field as an empty string or empty list.
4. Never add opinions or assumptions — only reorganize the information logically.

### Example
User input:
"did elon talk about tesla launching robotaxi next year?"

Output:
{{
  "task": "fact_check",
  "claim": "Elon Musk said Tesla will launch a robotaxi next year.",
  "context": "",
  "entities": ["Elon Musk", "Tesla"],
  "time_period": "next year",
  "output_format": "json"
}}

Now convert this user input:
"{claim_text}"
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
            "context": "",
            "entities": [],
            "time_period": "",
            "output_format": "json",
            "original_input": claim_text
        }

    def create_search_query(self, structured_claim: dict) -> str:
        """
        Create an optimized search query from structured claim.

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

        # Build query by combining relevant components
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
        search_query = " ".join(query_parts)
        if len(search_query) < 50 and entities:
            entity_text = " ".join(entities[:3])  # Limit to first 3 entities
            search_query = f"{search_query} {entity_text}"

        # If query is too long, use just the claim
        if len(search_query) > 200:
            search_query = claim[:200]

        # Fallback to original input if all else fails
        if not search_query.strip():
            search_query = structured_claim.get("original_input", "")[:200]

        return search_query.strip()
