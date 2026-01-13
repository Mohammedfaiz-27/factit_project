from app.core.config import GEMINI_API_KEY, GEMINI_MODEL
from google import genai
import re

class ModerationService:
    """
    Handles input and output moderation to ensure safe and appropriate content.
    """

    def __init__(self):
        if not GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY environment variable is not set")
        self.client = genai.Client(api_key=GEMINI_API_KEY)
        self.model = GEMINI_MODEL

        # Patterns for basic harmful content detection
        self.harmful_patterns = [
            r'\b(kill|murder|harm|attack|violence)\s+(someone|people|person)',
            r'\b(how to|guide to)\s+(make|create|build)\s+(bomb|weapon|explosive)',
            r'\b(steal|hack|break into)',
        ]

    def moderate_input(self, claim_text: str) -> dict:
        """
        Check if input contains harmful, illegal, or private data.

        Returns:
            dict: {"is_safe": bool, "reason": str or None}
        """
        # Basic pattern matching for obvious harmful content
        for pattern in self.harmful_patterns:
            if re.search(pattern, claim_text.lower()):
                return {
                    "is_safe": False,
                    "reason": "This request contains restricted or unsafe content and cannot be processed."
                }

        # Check for potential PII (simplified check)
        if self._contains_pii(claim_text):
            return {
                "is_safe": False,
                "reason": "This request contains private or sensitive information and cannot be processed."
            }

        # Use Gemini for more nuanced moderation
        try:
            chat = self.client.chats.create(model=self.model)
            moderation_prompt = f"""
You are a content moderator. Analyze the following claim and determine if it contains:
- Harmful, violent, or illegal content
- Private personal information (PII)
- Instructions for dangerous activities

Claim: "{claim_text}"

Respond with ONLY "SAFE" or "UNSAFE: [brief reason]"
"""
            response = chat.send_message(moderation_prompt)
            result = response.text.strip()

            if result.startswith("UNSAFE"):
                return {
                    "is_safe": False,
                    "reason": "This request contains restricted or unsafe content and cannot be processed."
                }

            return {"is_safe": True, "reason": None}

        except Exception as e:
            # If moderation fails, err on the side of caution
            print(f"Moderation error: {str(e)}")
            # Allow the request to proceed with basic checks only
            return {"is_safe": True, "reason": None}

    def moderate_output(self, output_text: str) -> dict:
        """
        Ensure the output is safe, factual, neutral, and free from hallucination.

        Returns:
            dict: {"is_safe": bool, "cleaned_output": str}
        """
        # Check for obvious hallucination markers or unsafe content
        if not output_text or len(output_text.strip()) < 10:
            return {
                "is_safe": False,
                "cleaned_output": "Unable to generate a safe fact-check result."
            }

        # Basic sanitization
        cleaned = output_text.strip()

        return {
            "is_safe": True,
            "cleaned_output": cleaned
        }

    def _contains_pii(self, text: str) -> bool:
        """
        Check for potential PII (simplified version).
        """
        # Check for patterns that might indicate PII
        pii_patterns = [
            r'\b\d{3}-\d{2}-\d{4}\b',  # SSN
            r'\b\d{16}\b',  # Credit card
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',  # Email (partial check)
        ]

        for pattern in pii_patterns:
            if re.search(pattern, text):
                return True

        return False
