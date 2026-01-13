from app.repository.claim_repository import ClaimRepository
from app.core.config import GEMINI_API_KEY, GEMINI_MODEL
from app.services.text_extraction_service import TextExtractionService
from app.services.url_extraction_service import URLExtractionService
from app.services.professional_fact_check_service import ProfessionalFactCheckService
from google import genai
from google.genai import types
import io
from PIL import Image
import base64
import tempfile
import os
import time

class FactCheckService:
    def __init__(self):
        self.repo = ClaimRepository()
        self.text_extractor = TextExtractionService()
        self.url_extractor = URLExtractionService()
        self.professional_service = ProfessionalFactCheckService()
        if not GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY environment variable is not set")
        self.client = genai.Client(api_key=GEMINI_API_KEY)
        self.model = GEMINI_MODEL

    def check_fact(self, claim_text: str):
        # Create chat session with Gemini model
        chat = self.client.chats.create(model=self.model)
        response = chat.send_message(f"Fact check this claim: {claim_text}")

        verdict = response.text.strip()

        # ✅ Save both prompt and response to DB
        self.repo.save(claim_text, verdict)

        # ✅ Return structured response to API
        return {
            "claim_text": claim_text,
            "response_text": verdict
        }



    def check_multimodal_fact(self, claim_text: str, file_content: bytes, content_type: str, filename: str):
        """
        Handle multimodal fact checking with images, videos, and audio.

        Pipeline:
        1. Extract text from media (OCR for images, speech-to-text for video/audio)
        2. Combine with user's claim text (if provided)
        3. Pass to professional fact-checking service with Perplexity Deep Search
        """
        try:
            print(f"\n{'='*60}")
            print(f"MULTIMODAL FACT-CHECK: {filename} ({content_type})")
            print(f"User claim: {claim_text if claim_text else 'None provided'}")
            print(f"{'='*60}\n")

            # Step 1: Extract text from media
            extracted_data = None
            media_type = None

            if content_type and content_type.startswith("image/"):
                media_type = "image"
                print("[EXTRACTING] Extracting text from image using OCR...")
                extracted_data = self.text_extractor.extract_text_from_image(file_content, filename)

            elif content_type and content_type.startswith("video/"):
                media_type = "video"
                print("[EXTRACTING] Extracting text from video (speech + visual text)...")
                extracted_data = self.text_extractor.extract_text_from_video(file_content, filename)

            elif content_type and content_type.startswith("audio/"):
                media_type = "audio"
                print("[EXTRACTING] Extracting text from audio (speech-to-text)...")
                extracted_data = self.text_extractor.extract_text_from_audio(file_content, filename, content_type)

            else:
                return {
                    "claim_text": claim_text or "Unknown media type",
                    "status": "❌ Error",
                    "explanation": f"Unsupported file type: {content_type}",
                    "sources": [],
                    "media_type": content_type
                }

            # Check if extraction failed
            if extracted_data.get("error"):
                return {
                    "claim_text": claim_text or f"Media file: {filename}",
                    "status": "❌ Error",
                    "explanation": extracted_data["error"],
                    "sources": [],
                    "media_type": content_type
                }

            extracted_text = extracted_data.get("text", "")
            print(f"\n[SUCCESS] Text extraction complete!")
            print(f"Extracted content (preview): {extracted_text[:200]}...\n")

            # Step 2: Combine extracted text with user's claim
            if claim_text:
                # User provided specific claim - use it as primary, extracted text as context
                combined_claim = f"{claim_text}\n\nContext from {media_type}: {extracted_text}"
                print(f"[COMBINING] Using user's claim with {media_type} context")
            else:
                # No user claim - use extracted text
                combined_claim = f"Claims from {media_type}: {extracted_text}"
                print(f"[COMBINING] Using extracted text from {media_type} as claim")

            # Step 3: Pass to professional fact-checking service (includes Perplexity Deep Search)
            print(f"\n[FACT-CHECKING] Starting professional fact-check pipeline with Perplexity Deep Search...")
            result = self.professional_service.check_fact(combined_claim)

            # Add media metadata to result
            result["media_type"] = content_type
            result["media_filename"] = filename
            result["extracted_text"] = extracted_text

            print(f"\n[SUCCESS] Multimodal fact-check complete!")
            print(f"Status: {result.get('status')}")
            print(f"{'='*60}\n")

            return result

        except Exception as e:
            error_msg = f"Error processing {content_type}: {str(e)}"
            print(f"[ERROR] {error_msg}")
            return {
                "claim_text": claim_text or f"Media file: {filename}",
                "status": "❌ Error",
                "explanation": error_msg,
                "sources": [],
                "media_type": content_type,
                "error": str(e)
            }

    def check_url_fact(self, url: str) -> dict:
        """
        Handle fact-checking from a URL/link.

        Pipeline:
        1. Extract article content from URL
        2. Identify main factual claim(s)
        3. Pass to professional fact-checking service with Perplexity Deep Search
        """
        try:
            print(f"\n{'='*60}")
            print(f"URL FACT-CHECK: {url}")
            print(f"{'='*60}\n")

            # Step 1: Extract content from URL
            print("[EXTRACTING] Extracting content from URL...")
            extracted_data = self.url_extractor.extract_from_url(url)

            # Never reject - always proceed with whatever was extracted
            main_claim = extracted_data.get("main_claim", "") or f"Information from URL: {url}"
            article_title = extracted_data.get("title", "")
            article_source = extracted_data.get("source", "")
            article_text = extracted_data.get("text", "")

            print(f"\n[SUCCESS] Content extraction complete!")
            print(f"Title: {article_title}")
            print(f"Source: {article_source}")
            print(f"Main claim: {main_claim[:150]}...\n")

            # Step 2: Construct claim with context
            claim_with_context = f"{main_claim}\n\nSource article: {article_title} ({article_source})"

            # Step 3: Pass to professional fact-checking service (includes Perplexity Deep Search)
            print(f"[FACT-CHECKING] Starting professional fact-check pipeline with Perplexity Deep Search...")
            result = self.professional_service.check_fact(claim_with_context)

            # Add URL metadata to result
            result["url"] = url
            result["article_title"] = article_title
            result["article_source"] = article_source
            result["article_preview"] = article_text[:500] + "..." if len(article_text) > 500 else article_text

            print(f"\n[SUCCESS] URL fact-check complete!")
            # Avoid printing emoji status on Windows console
            status_text = result.get('status', '').encode('ascii', errors='replace').decode('ascii')
            print(f"Status: {status_text}")
            print(f"{'='*60}\n")

            return result

        except Exception as e:
            error_msg = f"Error processing URL: {str(e)}"
            print(f"[ERROR] {error_msg}")
            return {
                "claim_text": f"URL: {url}",
                "status": "[X] Error",
                "explanation": error_msg,
                "sources": [],
                "url": url,
                "error": str(e)
            }
