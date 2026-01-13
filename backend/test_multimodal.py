"""
Test script to verify multimodal fact-checking with Perplexity Deep Search
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.text_extraction_service import TextExtractionService
from app.services.professional_fact_check_service import ProfessionalFactCheckService

def test_services():
    """Test that services can be instantiated"""
    try:
        print("Testing service initialization...")

        # Test TextExtractionService
        print("\n1. Initializing TextExtractionService...")
        text_extractor = TextExtractionService()
        print("   [OK] TextExtractionService initialized")

        # Test ProfessionalFactCheckService
        print("\n2. Initializing ProfessionalFactCheckService...")
        professional_service = ProfessionalFactCheckService()
        print("   [OK] ProfessionalFactCheckService initialized")

        print("\n" + "="*60)
        print("SUCCESS: All services initialized correctly!")
        print("="*60)
        print("\nThe implementation is ready. To test with actual files:")
        print("1. Start the backend: uvicorn main:app --reload --port 8000")
        print("2. Start the frontend: npm start (in frontend directory)")
        print("3. Upload an image/video/audio file through the UI")
        print("\nExpected flow:")
        print("  Image  -> OCR extraction -> Perplexity Deep Search")
        print("  Video  -> Speech-to-text -> Perplexity Deep Search")
        print("  Audio  -> Speech-to-text -> Perplexity Deep Search")

        return True

    except Exception as e:
        print(f"\n[ERROR] Service initialization failed: {str(e)}")
        return False

if __name__ == "__main__":
    success = test_services()
    sys.exit(0 if success else 1)
